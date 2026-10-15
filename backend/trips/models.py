from django.db import models
from django.contrib.auth.models import AbstractUser
from datetime import timedelta

class User(AbstractUser):
    """My user model"""

class Trip(models.Model):
    title = models.CharField(max_length=120)
    city = models.CharField(max_length=120)
    country = models.CharField(max_length=80, blank=True)
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
    class Category(models.TextChoices):
        SIGHT = "sight", "Sight"
        MUSEUM = "museum", "Museum"
        FOOD = "food", "Food"
        WALK = "walk", "Walk"
        SHOPPING = "shopping", "Shopping"
        OTHER = "other", "Other"

    day = models.ForeignKey(Day, on_delete=models.CASCADE, related_name="places")
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=300, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    time = models.TimeField(null=True, blank=True)
    category = models.CharField(max_length=10, choices=Category.choices, default=Category.SIGHT)
    visited = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = [models.F("time").asc(nulls_last=True), "id"]

    def __str__(self):
        return self.name

    