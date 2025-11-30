"""Management command to load sample golf events data."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from events.models import Tour, Venue, Event
from events.utils import geocode_venue


class Command(BaseCommand):
    help = 'Load sample golf events data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Loading sample data...')

        # Create tours
        pga_tour, _ = Tour.objects.get_or_create(
            name='PGA Tour',
            defaults={'website_url': 'https://www.pgatour.com'}
        )
        dp_world_tour, _ = Tour.objects.get_or_create(
            name='DP World Tour',
            defaults={'website_url': 'https://www.dpworldtour.com'}
        )
        lpga_tour, _ = Tour.objects.get_or_create(
            name='LPGA Tour',
            defaults={'website_url': 'https://www.lpga.com'}
        )
        self.stdout.write(self.style.SUCCESS('✓ Created tours'))

        # Create venues
        augusta, _ = Venue.objects.get_or_create(
            name='Augusta National Golf Club',
            city='Augusta',
            state='Georgia',
            country='USA'
        )

        st_andrews, _ = Venue.objects.get_or_create(
            name='The Old Course at St Andrews',
            city='St Andrews',
            state='',
            country='Scotland'
        )

        pebble_beach, _ = Venue.objects.get_or_create(
            name='Pebble Beach Golf Links',
            city='Pebble Beach',
            state='California',
            country='USA'
        )

        gullane, _ = Venue.objects.get_or_create(
            name='Renaissance Club',
            city='Gullane',
            state='Scotland',
            country='UK'
        )

        self.stdout.write(self.style.SUCCESS('✓ Created venues'))

        # Geocode venues
        self.stdout.write('Geocoding venues...')
        for venue in [augusta, st_andrews, pebble_beach, gullane]:
            if not venue.location:
                if geocode_venue(venue):
                    self.stdout.write(f'  ✓ Geocoded: {venue.name}')
                else:
                    self.stdout.write(self.style.WARNING(f'  ! Failed to geocode: {venue.name}'))

        # Create events
        today = timezone.now().date()

        # The Masters
        masters, _ = Event.objects.get_or_create(
            name='The Masters',
            venue=augusta,
            defaults={
                'category': 'major',
                'status': 'scheduled',
                'start_date': today + timedelta(days=120),
                'end_date': today + timedelta(days=123),
                'external_url': 'https://www.masters.com',
                'notes': 'One of golf\'s four major championships'
            }
        )
        # Majors have no tour affiliation

        # Scottish Open
        scottish_open, _ = Event.objects.get_or_create(
            name='Genesis Scottish Open',
            venue=gullane,
            defaults={
                'category': 'regular',
                'status': 'scheduled',
                'start_date': today + timedelta(days=200),
                'end_date': today + timedelta(days=203),
                'external_url': 'https://www.dpworldtour.com',
                'notes': 'Co-sanctioned by PGA Tour and DP World Tour'
            }
        )
        scottish_open.tours.add(pga_tour, dp_world_tour)

        # AT&T Pebble Beach Pro-Am
        pebble_beach_event, _ = Event.objects.get_or_create(
            name='AT&T Pebble Beach Pro-Am',
            venue=pebble_beach,
            defaults={
                'category': 'regular',
                'status': 'scheduled',
                'start_date': today + timedelta(days=60),
                'end_date': today + timedelta(days=63),
                'external_url': 'https://www.pgatour.com',
            }
        )
        pebble_beach_event.tours.add(pga_tour)

        # Past event
        past_event, _ = Event.objects.get_or_create(
            name='The Open Championship',
            venue=st_andrews,
            defaults={
                'category': 'major',
                'status': 'completed',
                'start_date': today - timedelta(days=100),
                'end_date': today - timedelta(days=97),
                'external_url': 'https://www.theopen.com',
                'notes': 'The oldest major championship'
            }
        )

        self.stdout.write(self.style.SUCCESS('✓ Created events'))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Sample data loaded successfully!'))
        self.stdout.write(f'  Tours: {Tour.objects.count()}')
        self.stdout.write(f'  Venues: {Venue.objects.count()}')
        self.stdout.write(f'  Events: {Event.objects.count()}')
