from django.db import transaction, DatabaseError, connection
from django.db.models import F
from django.shortcuts import get_object_or_404, render
from rest_framework import generics, status, serializers
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.decorators import api_view
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from dataclasses import asdict

from .models import Day, Place, Trip
from .serializers import DaySerializer, PlaceMoveSerializer, PlaceSerializer, TripSerializer
from .services import ExternalServiceError, geocode, refresh_weather

class ServiceUnavailable(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "External service is unavailable, try again later."


def geocode_or_error(query, field):
    """Geocode or stop the request with a clear error for the client."""
    try:
        result = geocode(query)
    except ExternalServiceError:
        raise ServiceUnavailable("Geocoding service is unavailable. Try again later.")
    if result is None:
        raise ValidationError({field: f'Couldn\'t find "{query}" on the map.'})
    return result


class TripListCreate(generics.ListCreateAPIView):
    """GET /api/trips/ — list of trips. POST /api/trips/ — create a trip (city is geocoded, days are created)."""

    queryset = Trip.objects.all()
    serializer_class = TripSerializer

    @transaction.atomic
    def perform_create(self, serializer):
        city = serializer.validated_data["city"]
        geo = geocode_or_error(city, "city")
        title = serializer.validated_data.get("title") or city
        trip = serializer.save(title=title, latitude=geo.latitude, longitude=geo.longitude, country=geo.country)
        trip.sync_days()


class TripDetail(generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH / PUT / DELETE /api/trips/<id>/ — one trip."""

    queryset = Trip.objects.all()
    serializer_class = TripSerializer

    @transaction.atomic
    def perform_update(self, serializer):
        extra = {}
        new_city = serializer.validated_data.get("city")
        if new_city and new_city != serializer.instance.city:
            geo = geocode_or_error(new_city, "city")
            extra = {"latitude": geo.latitude, "longitude": geo.longitude, "country": geo.country}
        trip = serializer.save(**extra)
        trip.sync_days()


@extend_schema(
    summary="Days of a trip with places and weather",
    responses=inline_serializer(
        name="TripDaysResponse",
        fields={
            "trip": TripSerializer(),
            "weather_available": serializers.BooleanField(),
            "days": DaySerializer(many=True),
        },
    ),
)


@api_view(["GET"])
def trip_days(request, pk):
    """GET /api/trips/<id>/days/ — days with places and weather. Stale weather is refreshed here."""
    trip = get_object_or_404(Trip, pk=pk)
    weather_ok = refresh_weather(trip)
    days = trip.days.prefetch_related("places")
    return Response({
        "trip": TripSerializer(trip).data,
        "weather_available": weather_ok,
        "days": DaySerializer(days, many=True).data,
    })

class DayDetail(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/days/<id>/ — one day, e.g. to set a note: {"note": "museum day"}."""

    queryset = Day.objects.prefetch_related("places")
    serializer_class = DaySerializer


class DayPlaces(generics.ListCreateAPIView):
    """GET /api/days/<id>/places/ — places of a day. POST — add a place (found by name if no coordinates)."""

    serializer_class = PlaceSerializer

    def get_day(self):
        return get_object_or_404(Day.objects.select_related("trip"), pk=self.kwargs["pk"])

    def get_queryset(self):
        return Place.objects.filter(day=self.get_day())

    def perform_create(self, serializer):
        day = self.get_day()
        data = serializer.validated_data
        extra = {}
        if "latitude" not in data:
            # search near the trip's city: "Galata Tower, Istanbul"
            geo = geocode_or_error(f"{data['name']}, {day.trip.city}", "name")
            extra = {"latitude": geo.latitude, "longitude": geo.longitude, "address": geo.address}
        serializer.save(day=day, **extra)


class PlaceDetail(generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH / DELETE /api/places/<id>/ — mark visited, move to another day, delete."""

    queryset = Place.objects.select_related("day")
    serializer_class = PlaceMoveSerializer


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
        return Response({"status": "error", "db": "unreachable"},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({"status": "ok", "db": "connected"})


@extend_schema(
    summary="Preview a place search before adding it",
    parameters=[OpenApiParameter("q", str, required=True,
                                 description='What to search, e.g. "Galata Tower, Istanbul"')],
    responses={200: inline_serializer(name="GeocodeResponse", fields={
        "latitude": serializers.FloatField(), "longitude": serializers.FloatField(),
        "name": serializers.CharField(), "address": serializers.CharField(),
        "country": serializers.CharField()})},
)
@api_view(["GET"])
def geocode_search(request):
    """GET /api/geocode/?q=... — find coordinates without saving anything."""
    query = request.query_params.get("q", "").strip()
    if len(query) < 2:
        raise ValidationError({"q": 'Send at least 2 characters, e.g. ?q=Galata Tower, Istanbul'})
    result = geocode_or_error(query, "q")      # 400 if not found, 503 if Nominatim is down
    return Response(asdict(result))


class TripPlaces(generics.ListAPIView):
    """GET /api/trips/{id}/places/ — all places of a trip, across all its days."""

    serializer_class = PlaceSerializer

    def get_queryset(self):
        trip = get_object_or_404(Trip, pk=self.kwargs["pk"])
        return (Place.objects.filter(day__trip=trip)
                .select_related("day")
                .order_by("day__date", F("time").asc(nulls_last=True), "id"))


TRUE_VALUES, FALSE_VALUES = {"true", "1"}, {"false", "0"}


@extend_schema(parameters=[
    OpenApiParameter("trip", int, description="Only places of this trip"),
    OpenApiParameter("visited", bool, description="true / false"),
    OpenApiParameter("category", str, enum=Place.Category.values, description="Place category"),
])
class PlaceList(generics.ListAPIView):
    """GET /api/places/?trip=&visited=&category= — all places with optional filters."""

    serializer_class = PlaceSerializer

    def get_queryset(self):
        params = self.request.query_params
        qs = Place.objects.select_related("day").order_by("day__date", F("time").asc(nulls_last=True), "id")

        trip = params.get("trip")
        if trip:
            if not trip.isdigit():
                raise ValidationError({"trip": "Must be a trip id (a number)."})
            qs = qs.filter(day__trip_id=int(trip))

        visited = params.get("visited")
        if visited:
            if visited.lower() in TRUE_VALUES:
                qs = qs.filter(visited=True)
            elif visited.lower() in FALSE_VALUES:
                qs = qs.filter(visited=False)
            else:
                raise ValidationError({"visited": "Use true or false."})

        category = params.get("category")
        if category:
            if category not in Place.Category.values:
                raise ValidationError({"category": f"Use one of: {', '.join(Place.Category.values)}."})
            qs = qs.filter(category=category)

        return qs


def index(request):
    """The web page with the map. It loads all data from our own API with JavaScript."""
    return render(request, "trips/index.html")