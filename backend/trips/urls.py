from django.urls import path

from . import views

urlpatterns = [
    path("trips/", views.TripListCreate.as_view()),
    path("trips/<int:pk>/", views.TripDetail.as_view()),
    path("trips/<int:pk>/days/", views.trip_days),
]