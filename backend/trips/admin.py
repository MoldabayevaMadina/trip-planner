from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Country, Day, Place, Profile, Trip, User, Visit

admin.site.register(User, UserAdmin)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "visa_free", "visa_free_days"]
    list_filter = ["visa_free"]
    search_fields = ["name", "code"]


class DayInline(admin.TabularInline):
    model = Day
    fields = ["date", "note"]
    extra = 0


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ["title", "city", "country", "start_date", "end_date"]
    list_filter = ["country"]
    search_fields = ["title", "city"]
    inlines = [DayInline]
    list_display = ["title", "owner", "city", "country", "start_date", "end_date"]
    list_filter = ["country", "owner"] 


class VisitInline(admin.TabularInline):
    model = Visit
    fields = ["place", "time", "visited"]
    extra = 0


@admin.register(Day)
class DayAdmin(admin.ModelAdmin):
    list_display = ["trip", "date", "note"]
    list_filter = ["trip"]
    inlines = [VisitInline]


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "latitude", "longitude"]
    list_filter = ["category"]
    search_fields = ["name", "address"]


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ["place", "day", "time", "visited"]
    list_filter = ["visited"]

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "home_city", "updated_at"]
    search_fields = ["user__username", "home_city"]