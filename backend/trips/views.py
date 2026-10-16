from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.decorators import api_view
from rest_framework.response import Response

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