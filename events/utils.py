"""Utility functions for the events app."""
import requests
from django.contrib.gis.geos import Point
from time import sleep


def autocomplete_location(query, limit=8):
    """
    Autocomplete location search using Nominatim.
    Returns list of dicts with formatted location info.
    Filters to golf-relevant countries and location types.
    """
    if not query or len(query) < 2:
        return []

    # Golf-relevant countries
    ALLOWED_COUNTRIES = {
        'United States', 'USA', 'United States of America',
        'United Kingdom', 'UK', 'Great Britain',
        'Scotland', 'England', 'Wales', 'Northern Ireland', 'Ireland',
        'Spain', 'United Arab Emirates', 'UAE', 'Australia',
        'South Africa', 'Canada', 'Mexico', 'Japan', 'South Korea',
        'France', 'Germany', 'Netherlands', 'Sweden', 'Denmark',
        'Portugal', 'Italy', 'Switzerland', 'New Zealand'
    }

    # Exclude these location types (too specific or not useful)
    EXCLUDED_TYPES = {
        'county', 'suburb', 'neighbourhood', 'district', 'borough',
        'quarter', 'road', 'street', 'hamlet', 'isolated_dwelling',
        'farm', 'building', 'house', 'residential'
    }

    url = 'https://nominatim.openstreetmap.org/search'
    params = {
        'q': query,
        'format': 'json',
        'limit': limit * 3,  # Get extra to filter
        'addressdetails': 1
    }
    headers = {
        'User-Agent': 'GolfCalendar/1.0'
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = []
        seen_locations = set()  # Avoid duplicates

        for item in data:
            if len(results) >= limit:
                break

            # Get address components
            address = item.get('address', {})
            location_type = item.get('type', '')
            osm_type = item.get('osm_type', '')
            addresstype = item.get('addresstype', '')  # More reliable than type

            # Skip excluded types
            if location_type in EXCLUDED_TYPES:
                continue

            # Extract location parts
            city = (address.get('city') or
                   address.get('town') or
                   address.get('village') or
                   address.get('municipality') or '')

            state = (address.get('state') or '')

            country = address.get('country', '')

            # Filter by allowed countries
            if country and country not in ALLOWED_COUNTRIES:
                continue

            # Use addresstype to determine the level of the result
            # For county/state level results, we don't want to show a city
            if addresstype == 'county':
                # This is a county result, skip it (too broad and not useful for golf searches)
                continue
            elif addresstype == 'state':
                # This is a state-level result, clear the city
                city = ''
            elif addresstype == 'country':
                # Country-level result
                city = ''
                state = ''

            # Build clean display name
            parts = []
            if city:
                parts.append(city)
            if state and state != city:  # Don't repeat if same
                parts.append(state)
            if country:
                # Simplify country names
                country_display = country
                if country in ['United States', 'United States of America']:
                    country_display = 'USA'
                elif country == 'United Kingdom':
                    country_display = 'UK'
                parts.append(country_display)

            if not parts:
                continue

            display_name = ', '.join(parts)

            # Avoid duplicates
            location_key = display_name.lower()
            if location_key in seen_locations:
                continue
            seen_locations.add(location_key)

            # Format type nicely - use addresstype for better labels
            if addresstype:
                type_display = addresstype.replace('_', ' ').title()
            elif location_type:
                type_display = location_type.replace('_', ' ').title()
            elif city:
                type_display = 'City'
            elif state:
                type_display = 'State'
            else:
                type_display = 'Country'

            results.append({
                'display_name': display_name,
                'lat': item.get('lat', ''),
                'lon': item.get('lon', ''),
                'type': type_display,
                'city': city,
                'state': state,
                'country': country
            })

        return results
    except Exception as e:
        print(f"Autocomplete error for '{query}': {e}")
        return []


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
