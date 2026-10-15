from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Day, Trip
from .serializers import DaySerializer, TripSerializer
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