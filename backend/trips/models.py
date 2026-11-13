from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class User(AbstractUser):
    """My user model (login and trip owners arrive in HW4)."""


class Country(models.Model):
    """A country of trips. Created automatically when the city of a trip is geocoded."""

    code = models.CharField(max_length=2, unique=True)        
    name = models.CharField(max_length=80)
    visa_free = models.BooleanField(default=False)           
    visa_free_days = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(365)]
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"

    def __str__(self):
        return f"{self.name} ({self.code})"


class Trip(models.Model):
    title = models.CharField(max_length=120)
    city = models.CharField(max_length=120)
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name="trips", null=True, blank=True
    )
    latitude = models.FloatField()
    longitude = models.FloatField()
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_date", "id"]

    def __str__(self):
        return f"{self.title} ({self.start_date} – {self.end_date})"

    def date_range(self):
        """All dates of the trip: 19, 20, ... 28 October."""
        count = (self.end_date - self.start_date).days + 1
        return [self.start_date + timedelta(days=i) for i in range(count)]

    def sync_days(self):
        """Make Day rows match the trip dates: add missing days, delete days outside the dates."""
        wanted = set(self.date_range())
        self.days.exclude(date__in=wanted).delete()
        existing = set(self.days.values_list("date", flat=True))
        Day.objects.bulk_create([Day(trip=self, date=d) for d in sorted(wanted - existing)])


class Day(models.Model):
    class WeatherSource(models.TextChoices):
        FORECAST = "forecast", "Forecast"
        LAST_YEAR = "last_year", "Same dates last year"
        ACTUAL = "actual", "Actual (past date)"

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="days")
    date = models.DateField()
    note = models.CharField(max_length=200, blank=True)

    weather_code = models.PositiveSmallIntegerField(null=True, blank=True)
    temp_max = models.FloatField(null=True, blank=True)
    temp_min = models.FloatField(null=True, blank=True)
    weather_source = models.CharField(max_length=10, choices=WeatherSource.choices, blank=True)
    weather_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(fields=["trip", "date"], name="unique_day_per_trip"),
        ]

    def __str__(self):
        return f"{self.trip.title}: {self.date}"


class Place(models.Model):
    """A real place on the map. Stored once and reused by every trip that visits it."""

    class Category(models.TextChoices):
        SIGHT = "sight", "Sight"
        MUSEUM = "museum", "Museum"
        FOOD = "food", "Food"
        WALK = "walk", "Walk"
        SHOPPING = "shopping", "Shopping"
        OTHER = "other", "Other"

    name = models.CharField(max_length=120)
    address = models.CharField(max_length=300, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.SIGHT)
    
    osm_id = models.CharField(max_length=40, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    days = models.ManyToManyField(Day, through="Visit", related_name="places")

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Visit(models.Model):
    """A place planned for a day: the link between Day and Place, with its own data."""

    day = models.ForeignKey(Day, on_delete=models.CASCADE, related_name="visits")
    place = models.ForeignKey(Place, on_delete=models.PROTECT, related_name="visits")
    time = models.TimeField(null=True, blank=True)
    visited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [models.F("time").asc(nulls_last=True), "id"]
        constraints = [
            models.UniqueConstraint(fields=["day", "place"], name="unique_place_per_day"),
        ]

    def __str__(self):
        return f"{self.place.name} on {self.day.date}"