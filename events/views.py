from django.shortcuts import render
from django.db.models import Q
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from .models import Event, Tour, Venue
from .utils import geocode_address


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
        if len(parts) == 3:
            city, state, country = parts
        elif len(parts) == 2:
            city, country = parts
            state = ''
        else:
            city = parts[0]
            state = ''
            country = 'USA'

        point = geocode_address(city, state, country)
        if point and radius:
            try:
                radius_miles = float(radius)
                events = events.filter(
                    venue__location__distance_lte=(point, D(mi=radius_miles))
                )
            except (ValueError, TypeError):
                pass

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
        }
    }

    # If HTMX request, return only the table partial
    if request.headers.get('HX-Request'):
        return render(request, 'events/_event_table.html', context)

    return render(request, 'events/event_list.html', context)
