from django.urls import path

from . import views

urlpatterns = [
    # Trips
    path("trips/", views.TripListCreate.as_view(), name="trip-list"),
    path("trips/<int:pk>/", views.TripDetail.as_view(), name="trip-detail"),
    path("trips/<int:pk>/days/", views.trip_days, name="trip-days"),
    path("trips/<int:pk>/places/", views.TripPlaces.as_view(), name="trip-places"),
    path("trips/<int:pk>/stats/", views.trip_stats, name="trip-stats"),
    path("trips/<int:pk>/copy/", views.trip_copy, name="trip-copy"),
    path("cities/", views.cities, name="cities"),
    path("dates/<str:date>/trips/", views.TripsOnDate.as_view(), name="trips-on-date"),

    # Days
    path("days/<int:pk>/", views.DayDetail.as_view(), name="day-detail"),
    path("days/<int:pk>/visits/", views.DayVisits.as_view(), name="day-visits"),
    path("days/<int:pk>/places/", views.DayPlaces.as_view(), name="day-places"),

    # Visits (a place planned for a day)
    path("visits/", views.VisitList.as_view(), name="visit-list"),
    path("visits/<int:pk>/", views.VisitDetail.as_view(), name="visit-detail"),

    # Places (shared catalog)
    path("places/", views.PlaceList.as_view(), name="place-list"),
    path("places/popular/", views.PopularPlaces.as_view(), name="places-popular"),
    path("places/<int:pk>/", views.PlaceDetail.as_view(), name="place-detail"),
    path("places/<int:pk>/trips/", views.PlaceTrips.as_view(), name="place-trips"),
    path("places/<int:pk>/days/", views.PlaceDays.as_view(), name="place-days"),

    # Countries
    path("countries/", views.CountryList.as_view(), name="country-list"),
    path("countries/<int:pk>/", views.CountryDetail.as_view(), name="country-detail"),
    path("countries/<int:pk>/trips/", views.CountryTrips.as_view(), name="country-trips"),
    path("countries/<int:pk>/places/", views.CountryPlaces.as_view(), name="country-places"),

    # Service
    path("geocode/", views.geocode_search, name="geocode"),
    path("health/", views.health, name="health"),
]