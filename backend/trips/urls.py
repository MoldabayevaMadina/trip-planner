from django.urls import path

from . import views

urlpatterns = [
    path("trips/", views.TripListCreate.as_view()),
    path("trips/<int:pk>/", views.TripDetail.as_view()),
    path("trips/<int:pk>/days/", views.trip_days),
    path("trips/<int:pk>/places/", views.TripPlaces.as_view(), name="trip-places"),

    path("days/<int:pk>/", views.DayDetail.as_view()),
    path("days/<int:pk>/places/", views.DayPlaces.as_view()),

    path("places/", views.PlaceList.as_view(), name="place-list"),
    path("places/<int:pk>/", views.PlaceDetail.as_view(), name="place-detail"),

    path("geocode/", views.geocode_search, name="geocode"),   
    path("health/", views.health, name="health"), 
]