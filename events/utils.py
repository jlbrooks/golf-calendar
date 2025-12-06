"""Utility functions for the events app."""
import requests
from django.contrib.gis.geos import Point
from time import sleep


def geocode_address(city, state, country):
    """Geocode an address using Nominatim. Returns Point or None."""
    address_parts = [city]
    if state:
        address_parts.append(state)
    address_parts.append(country)
    address = ', '.join(address_parts)

    url = 'https://nominatim.openstreetmap.org/search'
    params = {
        'q': address,
        'format': 'json',
        'limit': 1
    }
    headers = {
        'User-Agent': 'GolfCalendar/1.0'
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data:
            lat = float(data[0]['lat'])
            lon = float(data[0]['lon'])
            # Point takes (longitude, latitude) order
            return Point(lon, lat, srid=4326)

        return None
    except Exception as e:
        print(f"Geocoding error for '{address}': {e}")
        return None


def geocode_venue(venue, save=True):
    """Geocode a venue and optionally save it. Returns True if successful."""
    if venue.location:
        return True

    location = geocode_address(venue.city, venue.state, venue.country)

    if location:
        venue.location = location
        if save:
            venue.save()
        return True

    return False
