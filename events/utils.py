"""Utility functions for the events app."""
import requests
from django.contrib.gis.geos import Point
from time import sleep


def geocode_address(city, state, country):
    """
    Geocode an address using Nominatim (OpenStreetMap).

    Returns a Point object (longitude, latitude) or None if geocoding fails.
    """
    # Build address string
    address_parts = [city]
    if state:
        address_parts.append(state)
    address_parts.append(country)
    address = ', '.join(address_parts)

    # Use Nominatim API
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
    """
    Geocode a venue and optionally save it.

    Args:
        venue: Venue model instance
        save: Whether to save the venue after geocoding

    Returns:
        True if geocoding was successful, False otherwise
    """
    if venue.location:
        # Already has location
        return True

    location = geocode_address(venue.city, venue.state, venue.country)

    if location:
        venue.location = location
        if save:
            venue.save()
        return True

    return False
