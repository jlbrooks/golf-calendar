from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('', views.event_list, name='event_list'),
    path('api/location-autocomplete/', views.location_autocomplete, name='location_autocomplete'),
]
