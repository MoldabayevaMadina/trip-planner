from django.urls import path

from . import views

urlpatterns = [
    path("trips/", views.TripListCreate.as_view()),
    path("trips/<int:pk>/", views.TripDetail.as_view()),
    path("trips/<int:pk>/days/", views.trip_days),
    path("days/<int:pk>/", views.DayDetail.as_view()),
    path("days/<int:pk>/places/", views.DayPlaces.as_view()),
    path("places/<int:pk>/", views.PlaceDetail.as_view()),
]