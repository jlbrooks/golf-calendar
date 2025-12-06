from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Q
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.utils import timezone
from .models import Event, Tour, Venue
from .utils import geocode_address, autocomplete_location


def event_list(request):
    """Main event listing page with filters."""
    events = Event.objects.select_related('venue').prefetch_related('tours').all()

    tour_id = request.GET.get('tour')
    category = request.GET.get('category')
    status = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    location = request.GET.get('location')
    radius = request.GET.get('radius', '50')
    show_past_events = request.GET.get('show_past_events') == 'true'

    # Filter out past events by default
    if not show_past_events:
        today = timezone.now().date()
        events = events.filter(end_date__gte=today)

    if tour_id:
        events = events.filter(tours__id=tour_id)

    if category:
        events = events.filter(category=category)

    if status:
        events = events.filter(status=status)

    if start_date:
        events = events.filter(start_date__gte=start_date)

    if end_date:
        events = events.filter(end_date__lte=end_date)

    if location and location.strip():
        parts = [p.strip() for p in location.split(',')]

        # Parse location parts
        if len(parts) == 3:
            city, state, country = parts
        elif len(parts) == 2:
            # Could be "City, Country" or "State, Country"
            first, second = parts
            # Common country variations
            country_names = ['USA', 'US', 'UNITED STATES', 'UNITED STATES OF AMERICA',
                           'UK', 'UNITED KINGDOM', 'SCOTLAND', 'ENGLAND', 'WALES', 'IRELAND',
                           'SPAIN', 'FRANCE', 'GERMANY', 'ITALY', 'AUSTRALIA', 'CANADA']

            # Check if second part is a known country
            if second.upper() in country_names:
                # Check if first part is likely a state (common US states)
                us_states = ['CALIFORNIA', 'TEXAS', 'FLORIDA', 'NEW YORK', 'ARIZONA', 'GEORGIA',
                           'NORTH CAROLINA', 'SOUTH CAROLINA', 'NEVADA', 'HAWAII', 'MICHIGAN',
                           'PENNSYLVANIA', 'OHIO', 'ILLINOIS', 'VIRGINIA', 'COLORADO', 'OREGON',
                           'WASHINGTON', 'MASSACHUSETTS', 'TENNESSEE', 'MARYLAND', 'WISCONSIN']
                if first.upper() in us_states:
                    city = ''
                    state = first
                    country = second
                else:
                    city = first
                    state = ''
                    country = second
            else:
                city = first
                state = ''
                country = second
        else:
            city = parts[0]
            state = ''
            country = 'USA'

        # Smart location filtering:
        # 1. If it's a broad search (state/country without city), use text matching
        # 2. If it's a specific city, use distance-based search

        if not city and state:
            # State-level search: match venues by state
            events = events.filter(
                Q(venue__state__icontains=state) |
                Q(venue__city__icontains=state)  # In case state name is in city field
            )
            # Only filter by country if it's not a US variant (since state already implies USA)
            us_variants = ['USA', 'US', 'UNITED STATES', 'UNITED STATES OF AMERICA']
            if country and country.upper() not in us_variants:
                events = events.filter(venue__country__icontains=country)

        elif not city and not state and country:
            # Country-level search: match venues by country
            events = events.filter(venue__country__icontains=country)

        else:
            # City-level or specific location: use distance-based search
            point = geocode_address(city, state, country)
            if point:
                try:
                    # Use provided radius or default to 50 miles for city searches
                    radius_miles = float(radius) if radius else 50
                    events = events.filter(
                        venue__location__distance_lte=(point, D(mi=radius_miles))
                    )
                except (ValueError, TypeError):
                    # If radius is invalid, try text matching as fallback
                    if city:
                        events = events.filter(venue__city__icontains=city)
                    if state:
                        events = events.filter(venue__state__icontains=state)

    events = events.order_by('start_date', 'name').distinct()
    tours = Tour.objects.all()

    context = {
        'events': events,
        'tours': tours,
        'categories': Event.CATEGORY_CHOICES,
        'statuses': Event.STATUS_CHOICES,
        'filters': {
            'tour': tour_id,
            'category': category,
            'status': status,
            'start_date': start_date,
            'end_date': end_date,
            'location': location,
            'radius': radius,
            'show_past_events': show_past_events,
        }
    }

    # If HTMX request, return only the table partial
    if request.headers.get('HX-Request'):
        return render(request, 'events/_event_table.html', context)

    return render(request, 'events/event_list.html', context)


def location_autocomplete(request):
    """API endpoint for location autocomplete suggestions."""
    query = request.GET.get('q', '').strip()

    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    results = autocomplete_location(query, limit=8)
    return JsonResponse({'results': results})
