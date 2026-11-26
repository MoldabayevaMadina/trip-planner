from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Country, Day, Place, Trip, Visit
from .services import describe_weather, is_rainy

MAX_TRIP_DAYS = 30


# ---------- Countries ----------

class CountryShortSerializer(serializers.ModelSerializer):
    """Country inside a trip."""

    class Meta:
        model = Country
        fields = ["id", "code", "name", "visa_free"]


class CountrySerializer(serializers.ModelSerializer):
    trips_count = serializers.IntegerField(read_only=True) 

    class Meta:
        model = Country
        fields = ["id", "code", "name", "visa_free", "visa_free_days", "trips_count"]
        
        read_only_fields = ["code", "name"]

    def validate(self, attrs):
        visa_free = attrs.get("visa_free", getattr(self.instance, "visa_free", False))
        if not visa_free:
            if attrs.get("visa_free_days"):
                raise serializers.ValidationError(
                    {"visa_free_days": "Only a visa-free country can have visa-free days."}
                )
            attrs["visa_free_days"] = None   
        return attrs


# ---------- Places and visits ----------

class PlaceSerializer(serializers.ModelSerializer):
    """A place from the shared catalog."""

    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)

    class Meta:
        model = Place
        fields = ["id", "name", "address", "latitude", "longitude", "category", "osm_id", "created_at"]
        read_only_fields = ["address", "osm_id", "created_at"]


class PopularPlaceSerializer(PlaceSerializer):
    """A place with how often it is planned (numbers come from .annotate() in the view)."""

    trips_count = serializers.IntegerField(read_only=True)
    visits_count = serializers.IntegerField(read_only=True)

    class Meta(PlaceSerializer.Meta):
        fields = PlaceSerializer.Meta.fields + ["trips_count", "visits_count"]


class VisitSerializer(serializers.ModelSerializer):
    """A place planned for a day. Place fields are shown flat, so a visit is easy to draw on the map."""

    day = serializers.PrimaryKeyRelatedField(queryset=Day.objects.all(), required=False)
    place = serializers.PrimaryKeyRelatedField(read_only=True)
    name = serializers.CharField(source="place.name", read_only=True)
    address = serializers.CharField(source="place.address", read_only=True)
    latitude = serializers.FloatField(source="place.latitude", read_only=True)
    longitude = serializers.FloatField(source="place.longitude", read_only=True)
    category = serializers.CharField(source="place.category", read_only=True)

    class Meta:
        model = Visit
        fields = ["id", "day", "place", "name", "address", "latitude", "longitude",
                  "category", "time", "visited", "created_at"]
        read_only_fields = ["created_at"]

    def validate_day(self, value):
        """PATCH {"day": id} moves a visit: only to a day of the same trip, and not twice into one day."""
        if self.instance:
            if value.trip_id != self.instance.day.trip_id:
                raise serializers.ValidationError("A visit can only be moved to a day of the same trip.")
            if value != self.instance.day and Visit.objects.filter(day=value, place=self.instance.place).exists():
                raise serializers.ValidationError("This place is already planned for that day.")
        return value


class VisitCreateSerializer(serializers.Serializer):
    """
    Body of POST /api/days/{id}/visits/. Ways to add a place to a day:
    1. an existing place:            {"place": 7}
    2. a new place by name:          {"name": "Galata Tower"}           (found on the map near the trip's city)
    3. a new place with coordinates: {"name": "Our hotel", "latitude": 41.03, "longitude": 28.98}
    4. a picked suggestion:          {"name": "Starbucks", "latitude": ..., "longitude": ...,
                                      "address": "...", "osm_id": "node/123"}   (stored once per osm_id)
    """

    place = serializers.PrimaryKeyRelatedField(queryset=Place.objects.all(), required=False)
    name = serializers.CharField(max_length=120, required=False)
    category = serializers.ChoiceField(choices=Place.Category.choices, required=False)
    latitude = serializers.FloatField(required=False, min_value=-90, max_value=90)
    longitude = serializers.FloatField(required=False, min_value=-180, max_value=180)
    address = serializers.CharField(max_length=300, required=False, allow_blank=True)
    osm_id = serializers.CharField(max_length=40, required=False, allow_blank=True)
    time = serializers.TimeField(required=False, allow_null=True)
    visited = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        if "place" not in attrs and not attrs.get("name"):
            raise serializers.ValidationError("Send an existing place id in `place`, or a `name` of a new place.")
        if "place" in attrs and ("name" in attrs or "latitude" in attrs):
            raise serializers.ValidationError("Send either `place` or a new place (`name`), not both.")
        if ("latitude" in attrs) != ("longitude" in attrs):
            raise serializers.ValidationError("Send both latitude and longitude, or neither.")
        if attrs.get("osm_id") and "latitude" not in attrs:
            raise serializers.ValidationError("A suggested place (`osm_id`) must come with latitude and longitude.")
        return attrs


# ---------- Days ----------

class WeatherSerializer(serializers.Serializer):
    """Shape of the "weather" field in a day (used only for API docs)."""

    icon = serializers.CharField()
    text = serializers.CharField()
    temp_max = serializers.FloatField(allow_null=True)
    temp_min = serializers.FloatField(allow_null=True)
    rainy = serializers.BooleanField()
    source = serializers.CharField()


class DaySerializer(serializers.ModelSerializer):
    visits = VisitSerializer(many=True, read_only=True)
    weather = serializers.SerializerMethodField()

    class Meta:
        model = Day
        fields = ["id", "trip", "date", "note", "weather", "visits"]
        read_only_fields = ["trip", "date"]

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


class DayShortSerializer(serializers.ModelSerializer):
    """A day with its trip, for lists like "days when this place is visited"."""

    trip_title = serializers.CharField(source="trip.title", read_only=True)
    city = serializers.CharField(source="trip.city", read_only=True)

    class Meta:
        model = Day
        fields = ["id", "date", "trip", "trip_title", "city", "note"]


# ---------- Trips ----------

class TripSerializer(serializers.ModelSerializer):
    country = CountryShortSerializer(read_only=True)
    owner = serializers.CharField(source="owner.username", read_only=True)
    places_count = serializers.SerializerMethodField()

    class Meta:
        model = Trip
        fields = ["id", "title", "city", "country", "owner" "latitude", "longitude",
                  "start_date", "end_date", "places_count", "created_at"]
        read_only_fields = ["latitude", "longitude", "created_at"]
        extra_kwargs = {"title": {"required": False, "allow_blank": True}}

    def get_places_count(self, obj) -> int:
        annotated = getattr(obj, "visits_count", None)
        return annotated if annotated is not None else Visit.objects.filter(day__trip=obj).count()

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end:
            if end < start:
                raise serializers.ValidationError({"end_date": "End date can't be before start date."})
            if (end - start).days + 1 > MAX_TRIP_DAYS:
                raise serializers.ValidationError({"end_date": f"A trip can be at most {MAX_TRIP_DAYS} days long."})
        return attrs


class TripCopySerializer(serializers.Serializer):
    """Body of POST /api/trips/{id}/copy/: new dates (the length stays the same) and an optional title."""

    start_date = serializers.DateField()
    title = serializers.CharField(max_length=120, required=False, allow_blank=True)