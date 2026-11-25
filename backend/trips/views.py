from dataclasses import asdict
from datetime import timedelta

from django.db import DatabaseError, connection, transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response

from . import filters
from .models import Country, Day, Place, Trip, Visit
from .serializers import (CountrySerializer, DaySerializer, DayShortSerializer, PlaceSerializer,
                          PopularPlaceSerializer, TripCopySerializer, TripSerializer,
                          VisitCreateSerializer, VisitSerializer)
from .services import ExternalServiceError, geocode, refresh_weather, suggest_places


class ServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "External service is unavailable, try again later."


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The object is used by other objects and can't be deleted."


def geocode_or_error(query, field):
    """Geocode or stop the request with a clear error for the client."""
    try:
        result = geocode(query)
    except ExternalServiceError:
        raise ServiceUnavailable("Geocoding service is unavailable. Try again later.")
    if result is None:
        raise ValidationError({field: f'Couldn\'t find "{query}" on the map.'})
    return result


def country_from(geo):
    """Find the country of a geocoding result in our table, or create it the first time."""
    if not geo.country_code:
        return None
    country, _ = Country.objects.get_or_create(code=geo.country_code, defaults={"name": geo.country})
    return country


TRIP_STATUSES = ["upcoming", "current", "past"]
TRIP_ORDERING = ["start_date", "-start_date", "title", "-title", "city", "-city", "created_at", "-created_at"]


def trips_queryset():
    """Trips with their country (JOIN) and the number of planned places (COUNT) in one query."""
    return (Trip.objects.select_related("country")
            .annotate(visits_count=Count("days__visits"))
            .order_by("start_date", "id"))


# ---------- Trips ----------

@extend_schema(parameters=[
    OpenApiParameter("city", str, description="City contains the text, e.g. ist"),
    OpenApiParameter("country", str, description="Country ISO code, e.g. TR"),
    OpenApiParameter("visa_free", bool, description="Only trips to visa-free (true) or visa (false) countries"),
    OpenApiParameter("date", str, description="Trips that go on this date, YYYY-MM-DD"),
    OpenApiParameter("date_from", str, description="Period start, YYYY-MM-DD: trips that end on or after it"),
    OpenApiParameter("date_to", str, description="Period end, YYYY-MM-DD: trips that start on or before it"),
    OpenApiParameter("search", str, description="Search in title and city"),
    OpenApiParameter("status", str, enum=TRIP_STATUSES, description="Compared with today"),
    OpenApiParameter("ordering", str, enum=TRIP_ORDERING, description="Sort order, - means descending"),
])
class TripListCreate(generics.ListCreateAPIView):
    """GET /api/trips/ — trips with filters. POST — create a trip (the city is geocoded, days are created)."""

    serializer_class = TripSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = trips_queryset()

        city = params.get("city")
        if city:
            qs = qs.filter(city__icontains=city)

        country = params.get("country")
        if country:
            qs = qs.filter(country__code__iexact=country)

        visa_free = filters.get_bool(params, "visa_free")
        if visa_free is not None:
            qs = qs.filter(country__visa_free=visa_free)

        on_date = filters.get_date(params, "date")
        if on_date:
            qs = qs.filter(start_date__lte=on_date, end_date__gte=on_date)

        # a period: trips that overlap it at least partly
        date_from = filters.get_date(params, "date_from")
        date_to = filters.get_date(params, "date_to")
        if date_from and date_to and date_from > date_to:
            raise ValidationError({"date_from": "date_from can't be after date_to."})
        if date_from:
            qs = qs.filter(end_date__gte=date_from)    # not finished before the period starts
        if date_to:
            qs = qs.filter(start_date__lte=date_to)    # starts before the period ends

        search = params.get("search")
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(city__icontains=search))

        trip_status = filters.get_choice(params, "status", TRIP_STATUSES)
        if trip_status:
            today = timezone.localdate()
            if trip_status == "upcoming":
                qs = qs.filter(start_date__gt=today)
            elif trip_status == "current":
                qs = qs.filter(start_date__lte=today, end_date__gte=today)
            else:  # past
                qs = qs.filter(end_date__lt=today)

        ordering = filters.get_choice(params, "ordering", TRIP_ORDERING)
        if ordering:
            qs = qs.order_by(ordering, "id")

        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        city = serializer.validated_data["city"]
        geo = geocode_or_error(city, "city")
        title = serializer.validated_data.get("title") or city
        trip = serializer.save(title=title, latitude=geo.latitude, longitude=geo.longitude,
                               country=country_from(geo))
        trip.sync_days()


class TripDetail(generics.RetrieveUpdateDestroyAPIView):
    """GET / PUT / PATCH / DELETE /api/trips/{id}/ — one trip."""

    serializer_class = TripSerializer

    def get_queryset(self):
        return trips_queryset()

    @transaction.atomic
    def perform_update(self, serializer):
        extra = {}
        new_city = serializer.validated_data.get("city")
        if new_city and new_city != serializer.instance.city:
            geo = geocode_or_error(new_city, "city")
            extra = {"latitude": geo.latitude, "longitude": geo.longitude, "country": country_from(geo)}
        trip = serializer.save(**extra)
        trip.sync_days()
        if extra: 
            trip.days.update(weather_updated_at=None)


@extend_schema(
    summary="Days of a trip with visits and weather",
    responses=inline_serializer(name="TripDaysResponse", fields={
        "trip": TripSerializer(),
        "weather_available": serializers.BooleanField(),
        "days": DaySerializer(many=True),
    }),
)
@api_view(["GET"])
def trip_days(request, pk):
    """GET /api/trips/{id}/days/ — days with visits and weather. Stale weather is refreshed here."""
    trip = get_object_or_404(trips_queryset(), pk=pk)
    weather_ok = refresh_weather(trip)
    days = trip.days.prefetch_related("visits__place")
    return Response({
        "trip": TripSerializer(trip).data,
        "weather_available": weather_ok,
        "days": DaySerializer(days, many=True).data,
    })


@extend_schema(
    summary="Statistics of a trip",
    responses=inline_serializer(name="TripStats", fields={
        "trip": serializers.IntegerField(),
        "title": serializers.CharField(),
        "days": serializers.IntegerField(),
        "planned_visits": serializers.IntegerField(),
        "unique_places": serializers.IntegerField(),
        "visited": serializers.IntegerField(),
        "visited_percent": serializers.IntegerField(),
        "rainy_days": serializers.IntegerField(),
        "by_category": serializers.DictField(child=serializers.IntegerField()),
        "by_day": inline_serializer(name="TripStatsDay", many=True, fields={
            "date": serializers.DateField(),
            "planned": serializers.IntegerField(),
            "visited": serializers.IntegerField(),
        }),
    }),
)
@api_view(["GET"])
def trip_stats(request, pk):
    """GET /api/trips/{id}/stats/ — numbers of a trip, counted by the database (aggregate / annotate)."""
    trip = get_object_or_404(Trip, pk=pk)
    visits = Visit.objects.filter(day__trip=trip)

    totals = visits.aggregate(
        planned=Count("id"),
        visited=Count("id", filter=Q(visited=True)),
        places=Count("place", distinct=True),
    )
    by_category = {
        row["place__category"]: row["count"]
        for row in visits.values("place__category").annotate(count=Count("id")).order_by("place__category")
    }
    days = trip.days.annotate(
        planned=Count("visits"),
        visited_count=Count("visits", filter=Q(visits__visited=True)),
    ).order_by("date")
    by_day = [{"date": d.date, "planned": d.planned, "visited": d.visited_count} for d in days]
    rainy_days = trip.days.filter(weather_code__gte=51).count()  

    planned = totals["planned"]
    return Response({
        "trip": trip.id,
        "title": trip.title,
        "days": len(by_day),
        "planned_visits": planned,
        "unique_places": totals["places"],
        "visited": totals["visited"],
        "visited_percent": round(100 * totals["visited"] / planned) if planned else 0,
        "rainy_days": rainy_days,
        "by_category": by_category,
        "by_day": by_day,
    })


@extend_schema(request=TripCopySerializer, responses={201: TripSerializer})
@api_view(["POST"])
def trip_copy(request, pk):
    """POST /api/trips/{id}/copy/ — a new trip with the same city and plan, starting on another date."""
    source = get_object_or_404(Trip.objects.select_related("country"), pk=pk)
    data_in = TripCopySerializer(data=request.data)
    data_in.is_valid(raise_exception=True)
    data = data_in.validated_data

    start = data["start_date"]
    length = (source.end_date - source.start_date).days
    with transaction.atomic():
        trip = Trip.objects.create(
            title=data.get("title") or f"{source.title} (copy)"[:120],
            city=source.city, country=source.country,
            latitude=source.latitude, longitude=source.longitude,
            start_date=start, end_date=start + timedelta(days=length),
        )
        trip.sync_days()
        old_days = source.days.prefetch_related("visits").order_by("date")
        new_days = trip.days.order_by("date")
        Visit.objects.bulk_create([
            Visit(day=new_day, place_id=visit.place_id, time=visit.time)
            for old_day, new_day in zip(old_days, new_days)
            for visit in old_day.visits.all()
        ])
    return Response(TripSerializer(trips_queryset().get(pk=trip.pk)).data, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Cities of all trips",
    parameters=[OpenApiParameter("country", str, description="Country ISO code, e.g. TR")],
    responses=inline_serializer(name="City", many=True, fields={
        "city": serializers.CharField(),
        "country": serializers.CharField(allow_null=True),
        "country_code": serializers.CharField(allow_null=True),
        "trips_count": serializers.IntegerField(),
    }),
)
@api_view(["GET"])
def cities(request):
    """GET /api/cities/ — every city we travel to, with the number of trips (GROUP BY city)."""
    rows = (Trip.objects.values("city", "country__name", "country__code")
            .annotate(trips_count=Count("id"))
            .order_by("city"))
    country = request.query_params.get("country")
    if country:
        rows = rows.filter(country__code__iexact=country)
    return Response([
        {"city": r["city"], "country": r["country__name"], "country_code": r["country__code"],
         "trips_count": r["trips_count"]}
        for r in rows
    ])


class TripPlaces(generics.ListAPIView):
    """GET /api/trips/{id}/places/ — places planned in this trip (each place once)."""

    serializer_class = PlaceSerializer

    def get_queryset(self):
        trip = get_object_or_404(Trip, pk=self.kwargs["pk"])
        return Place.objects.filter(visits__day__trip=trip).distinct()


class TripsOnDate(generics.ListAPIView):
    """GET /api/dates/{YYYY-MM-DD}/trips/ — trips that go on this date."""

    serializer_class = TripSerializer

    def get_queryset(self):
        on_date = filters.parse_date(self.kwargs["date"])
        return trips_queryset().filter(start_date__lte=on_date, end_date__gte=on_date)


# ---------- Days ----------

class DayDetail(generics.RetrieveUpdateAPIView):
    """GET / PUT / PATCH /api/days/{id}/ — one day, e.g. to set a note: {"note": "museum day"}."""

    queryset = Day.objects.prefetch_related("visits__place")
    serializer_class = DaySerializer


class DayPlaces(generics.ListAPIView):
    """GET /api/days/{id}/places/ — places of a day (through the many-to-many link)."""

    serializer_class = PlaceSerializer

    def get_queryset(self):
        day = get_object_or_404(Day, pk=self.kwargs["pk"])
        return day.places.all()


@extend_schema(request=VisitCreateSerializer, responses={201: VisitSerializer})
class DayVisits(generics.ListCreateAPIView):
    """GET /api/days/{id}/visits/ — the plan of a day. POST — add a place to the day."""

    serializer_class = VisitSerializer

    def get_day(self):
        return get_object_or_404(Day.objects.select_related("trip"), pk=self.kwargs["pk"])

    def get_queryset(self):
        return Visit.objects.filter(day=self.get_day()).select_related("place")

    def create(self, request, *args, **kwargs):
        day = self.get_day()
        data_in = VisitCreateSerializer(data=request.data)
        data_in.is_valid(raise_exception=True)
        data = data_in.validated_data

        geo = None
        if "place" not in data and "latitude" not in data:
            # a new place by name: search near the trip's city before opening the transaction
            geo = geocode_or_error(f"{data['name']}, {day.trip.city}", "name")

        with transaction.atomic():
            place = data.get("place") or self.find_or_create_place(data, geo)
            if Visit.objects.filter(day=day, place=place).exists():
                raise ValidationError({"place": "This place is already planned for this day."})
            visit = Visit.objects.create(day=day, place=place, time=data.get("time"),
                                         visited=data.get("visited", False))
        return Response(VisitSerializer(visit).data, status=status.HTTP_201_CREATED)

    @staticmethod
    def find_or_create_place(data, geo):
        category = data.get("category", Place.Category.SIGHT)
        if geo is None:
            # coordinates came from the client: a click on the map or a picked suggestion
            fields = {
                "name": data["name"],
                "address": data.get("address", ""),
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "category": category,
            }
            if data.get("osm_id"):  # a picked suggestion: the same real place is stored only once
                place, _ = Place.objects.get_or_create(osm_id=data["osm_id"], defaults=fields)
                return place
            return Place.objects.create(**fields)  # a click on the map: always a new place
        defaults = {"name": data["name"], "address": geo.address, "latitude": geo.latitude,
                    "longitude": geo.longitude, "category": category}
        if geo.osm_id:  # the same real place is stored only once
            place, _ = Place.objects.get_or_create(osm_id=geo.osm_id, defaults=defaults)
            return place
        return Place.objects.create(**defaults)


# ---------- Visits ----------

@extend_schema(parameters=[
    OpenApiParameter("trip", int, description="Only visits of this trip"),
    OpenApiParameter("date", str, description="Only visits on this date, YYYY-MM-DD"),
    OpenApiParameter("visited", bool, description="true / false"),
    OpenApiParameter("category", str, enum=Place.Category.values, description="Category of the place"),
])
class VisitList(generics.ListAPIView):
    """GET /api/visits/?trip=&date=&visited=&category= — all planned places with filters."""

    serializer_class = VisitSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = Visit.objects.select_related("place", "day").order_by("day__date", "time", "id")

        trip = filters.get_int(params, "trip")
        if trip is not None:
            qs = qs.filter(day__trip_id=trip)

        on_date = filters.get_date(params, "date")
        if on_date:
            qs = qs.filter(day__date=on_date)

        visited = filters.get_bool(params, "visited")
        if visited is not None:
            qs = qs.filter(visited=visited)

        category = filters.get_choice(params, "category", Place.Category.values)
        if category:
            qs = qs.filter(place__category=category)

        return qs


class VisitDetail(generics.RetrieveUpdateDestroyAPIView):
    """GET / PUT / PATCH / DELETE /api/visits/{id}/ — mark visited, change time, move to another day."""

    queryset = Visit.objects.select_related("place", "day")
    serializer_class = VisitSerializer


# ---------- Places (shared catalog) ----------

@extend_schema(parameters=[
    OpenApiParameter("category", str, enum=Place.Category.values, description="Category of the place"),
    OpenApiParameter("search", str, description="Name contains the text"),
    OpenApiParameter("trip", int, description="Only places planned in this trip"),
])
class PlaceList(generics.ListAPIView):
    """GET /api/places/?category=&search=&trip= — all places of the catalog."""

    serializer_class = PlaceSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = Place.objects.all()

        category = filters.get_choice(params, "category", Place.Category.values)
        if category:
            qs = qs.filter(category=category)

        search = params.get("search")
        if search:
            qs = qs.filter(name__icontains=search)

        trip = filters.get_int(params, "trip")
        if trip is not None:
            qs = qs.filter(visits__day__trip_id=trip).distinct()

        return qs


@extend_schema(parameters=[
    OpenApiParameter("limit", int, description="How many places, 1–50 (default 10)"),
])
class PopularPlaces(generics.ListAPIView):
    """GET /api/places/popular/ — places planned in the most trips."""

    serializer_class = PopularPlaceSerializer

    def get_queryset(self):
        limit = filters.get_int(self.request.query_params, "limit") or 10
        if not 1 <= limit <= 50:
            raise ValidationError({"limit": "Use a number from 1 to 50."})
        return (Place.objects
                .annotate(trips_count=Count("visits__day__trip", distinct=True), visits_count=Count("visits"))
                .filter(trips_count__gt=0)
                .order_by("-trips_count", "-visits_count", "name")[:limit])


class PlaceDetail(generics.RetrieveUpdateDestroyAPIView):
    """GET / PUT / PATCH / DELETE /api/places/{id}/. A place that is planned in some day can't be deleted (409)."""

    queryset = Place.objects.all()
    serializer_class = PlaceSerializer

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise Conflict(f"The place is planned in {instance.visits.count()} visit(s). Remove the visits first.")


class PlaceTrips(generics.ListAPIView):
    """GET /api/places/{id}/trips/ — trips that visit this place."""

    serializer_class = TripSerializer

    def get_queryset(self):
        place = get_object_or_404(Place, pk=self.kwargs["pk"])
        return trips_queryset().filter(id__in=Trip.objects.filter(days__visits__place=place))


class PlaceDays(generics.ListAPIView):
    """GET /api/places/{id}/days/ — days (of any trip) when this place is planned."""

    serializer_class = DayShortSerializer

    def get_queryset(self):
        place = get_object_or_404(Place, pk=self.kwargs["pk"])
        return place.days.select_related("trip").order_by("date", "id")


# ---------- Countries ----------

def countries_queryset():
    return Country.objects.annotate(trips_count=Count("trips")).order_by("name")


@extend_schema(parameters=[
    OpenApiParameter("visa_free", bool, description="Only visa-free (true) or visa (false) countries"),
])
class CountryList(generics.ListAPIView):
    """GET /api/countries/ — countries of all trips (created automatically when a city is geocoded)."""

    serializer_class = CountrySerializer

    def get_queryset(self):
        qs = countries_queryset()
        visa_free = filters.get_bool(self.request.query_params, "visa_free")
        if visa_free is not None:
            qs = qs.filter(visa_free=visa_free)
        return qs


class CountryDetail(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/countries/{id}/ — e.g. mark a country visa-free: {"visa_free": true, "visa_free_days": 30}."""

    serializer_class = CountrySerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return countries_queryset()


class CountryPlaces(generics.ListAPIView):
    """GET /api/countries/{id}/places/ — places planned in trips to this country."""

    serializer_class = PlaceSerializer

    def get_queryset(self):
        country = get_object_or_404(Country, pk=self.kwargs["pk"])
        return Place.objects.filter(visits__day__trip__country=country).distinct()


class CountryTrips(generics.ListAPIView):
    """GET /api/countries/{id}/trips/ — all trips to this country."""

    serializer_class = TripSerializer

    def get_queryset(self):
        country = get_object_or_404(Country, pk=self.kwargs["pk"])
        return trips_queryset().filter(country=country)


# ---------- Service ----------

@extend_schema(
    summary="Backend and database status",
    responses={200: inline_serializer(name="HealthResponse", fields={
        "status": serializers.CharField(), "db": serializers.CharField()})},
)
@api_view(["GET"])
def health(request):
    """GET /api/health/ — is the backend up and can it reach the database?"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return Response({"status": "error", "db": "unreachable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({"status": "ok", "db": "connected"})


@extend_schema(
    summary="Preview a place search before adding it",
    parameters=[OpenApiParameter("q", str, required=True, description='What to search, e.g. "Galata Tower, Istanbul"')],
    responses={200: inline_serializer(name="GeocodeResponse", fields={
        "latitude": serializers.FloatField(), "longitude": serializers.FloatField(),
        "name": serializers.CharField(), "address": serializers.CharField(),
        "country": serializers.CharField(), "country_code": serializers.CharField(),
        "osm_id": serializers.CharField()})},
)

@extend_schema(
    summary="Place suggestions while typing",
    parameters=[
        OpenApiParameter("q", str, required=True, description="What the user is typing, at least 3 characters"),
        OpenApiParameter("trip", int, description="Places near this trip's city come first; other countries are hidden"),
    ],
    responses={200: inline_serializer(name="PlaceSuggestion", many=True, fields={
        "name": serializers.CharField(),
        "address": serializers.CharField(),
        "latitude": serializers.FloatField(),
        "longitude": serializers.FloatField(),
        "country": serializers.CharField(),
        "country_code": serializers.CharField(),
        "osm_id": serializers.CharField(),
    })},
)
@api_view(["GET"])
def place_suggestions(request):
    """GET /api/places/suggest/?q=starb&trip=5 — up to 6 places for the dropdown. Nothing is saved."""
    query = request.query_params.get("q", "").strip()
    if len(query) < 3:
        return Response([])            # too short to search: no request to the external service

    trip = None
    trip_id = filters.get_int(request.query_params, "trip")
    if trip_id:
        trip = get_object_or_404(Trip.objects.select_related("country"), pk=trip_id)

    try:
        results = suggest_places(query, trip.latitude if trip else None, trip.longitude if trip else None)
    except ExternalServiceError:
        raise ServiceUnavailable("Place search is unavailable. Try again later.")

    if trip and trip.country:          # a café in another country is never what the user wants
        results = [r for r in results if not r.country_code or r.country_code == trip.country.code]
    return Response([asdict(r) for r in results[:6]])

@api_view(["GET"])
def geocode_search(request):
    """GET /api/geocode/?q=... — find coordinates without saving anything."""
    query = request.query_params.get("q", "").strip()
    if len(query) < 2:
        raise ValidationError({"q": "Send at least 2 characters, e.g. ?q=Galata Tower, Istanbul"})
    return Response(asdict(geocode_or_error(query, "q")))


def index(request):
    return render(request, "trips/index.html")