from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Day, Place, Trip, User

admin.site.register(User, UserAdmin)


class DayInline(admin.TabularInline):
    model = Day
    extra = 0


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ["title", "city", "country", "start_date", "end_date"]
    search_fields = ["title", "city"]
    inlines = [DayInline]


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ["name", "day", "time", "category", "visited"]
    list_filter = ["category", "visited"]
    search_fields = ["name"]