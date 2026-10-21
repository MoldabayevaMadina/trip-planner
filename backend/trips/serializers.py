from rest_framework import serializers

from .models import Day, Place, Trip
from .services import describe_weather, is_rainy
from drf_spectacular.utils import extend_schema_field

MAX_TRIP_DAYS = 30


class PlaceSerializer(serializers.ModelSerializer):
    """Coordinates are optional: if they are missing, the server finds them by the place name."""
    latitude = serializers.FloatField(required=False, min_value=-90, max_value=90)
    longitude = serializers.FloatField(required=False, min_value=-180, max_value=180)

    class Meta:
        model = Place
        fields = ["id", "day", "name", "address", "latitude", "longitude", "time", "category", "visited"]
        read_only_fields = ["day", "address"]

    def validate(self, attrs):
        if ("latitude" in attrs) != ("longitude" in attrs):
            raise serializers.ValidationError("Send both latitude and longitude, or neither.")
        return attrs


class PlaceMoveSerializer(PlaceSerializer):
    """Like PlaceSerializer, but `day` can be changed: move a place to another day of the same trip."""

    day = serializers.PrimaryKeyRelatedField(queryset=Day.objects.all(), required=False)

    class Meta(PlaceSerializer.Meta):
        read_only_fields = ["address"]

    def validate_day(self, value):
        if self.instance and value.trip_id != self.instance.day.trip_id:
            raise serializers.ValidationError("A place can only be moved to a day of the same trip.")
        return value

class WeatherSerializer(serializers.Serializer):
    """Shape of the "weather" field in a day (used only for API docs)."""
    icon = serializers.CharField()
    text = serializers.CharField()
    temp_max = serializers.FloatField(allow_null=True)
    temp_min = serializers.FloatField(allow_null=True)
    rainy = serializers.BooleanField()
    source = serializers.CharField()

class DaySerializer(serializers.ModelSerializer):
    places = PlaceSerializer(many=True, read_only=True)
    weather = serializers.SerializerMethodField()

    class Meta:
        model = Day
        fields = ["id", "date", "note", "weather", "places"]
        read_only_fields = ["date"]

    @extend_schema_field(WeatherSerializer(allow_null=True))
    def get_weather(self, obj):
        if obj.weather_code is None and obj.temp_max is None:
            return None
        icon, text = describe_weather(obj.weather_code)
        return {
            "icon": icon,
            "text": text,
            "temp_max": obj.temp_max,
            "temp_min": obj.temp_min,
            "rainy": is_rainy(obj.weather_code),
            "source": obj.weather_source,
        }


class TripSerializer(serializers.ModelSerializer):
    places_count = serializers.SerializerMethodField()
    class Meta:
        model = Trip
        fields = ["id", "title", "city", "country", "latitude", "longitude",
                  "start_date", "end_date", "places_count", "created_at"]
        # coordinates and country are found by the server, not sent by the client
        read_only_fields = ["country", "latitude", "longitude", "created_at"]
        extra_kwargs = {"title": {"required": False, "allow_blank": True}}

    def get_places_count(self, obj) -> int:
        return Place.objects.filter(day__trip=obj).count()

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end:
            if end < start:
                raise serializers.ValidationError({"end_date": "End date can't be before start date."})
            if (end - start).days + 1 > MAX_TRIP_DAYS:
                raise serializers.ValidationError({"end_date": f"A trip can be at most {MAX_TRIP_DAYS} days long."})
        return attrs