"""Management command to scrape PGA Tour schedule."""
from django.core.management.base import BaseCommand
from django.db import transaction
from events.models import Tour, Venue, Event
from events.scrapers import PGATourScraper
from events.utils import geocode_venue
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Scrape and import PGA Tour schedule'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without saving to database',
        )
        parser.add_argument(
            '--geocode',
            action='store_true',
            help='Geocode venues after import',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        should_geocode = options['geocode']

        self.stdout.write('Starting PGA Tour scrape...')

        # Get or create PGA Tour
        if not dry_run:
            tour, created = Tour.objects.get_or_create(
                name='PGA Tour',
                defaults={'website_url': 'https://www.pgatour.com'}
            )
            if created:
                self.stdout.write(self.style.SUCCESS('Created PGA Tour'))
        else:
            tour = None

        # Scrape events using context manager
        try:
            with PGATourScraper() as scraper:
                events_data = scraper.fetch_schedule()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch schedule: {e}'))
            logger.exception('Scraper error')
            return

        if not events_data:
            self.stdout.write(self.style.WARNING('No events found'))
            return

        self.stdout.write(f'Found {len(events_data)} events')

        # Import events
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for event_data in events_data:
            try:
                if dry_run:
                    self.stdout.write(f'  [DRY RUN] Would import: {event_data["name"]}')
                    continue

                result = self._import_event(event_data, tour, should_geocode)

                if result == 'created':
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {event_data["name"]}'))
                elif result == 'updated':
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ↻ Updated: {event_data["name"]}'))
                else:
                    skipped_count += 1
                    self.stdout.write(f'  - Skipped: {event_data["name"]}')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✗ Error importing {event_data.get("name", "unknown")}: {e}'))
                logger.exception(f'Failed to import event: {event_data}')

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Import complete!'))
        self.stdout.write(f'  Created: {created_count}')
        self.stdout.write(f'  Updated: {updated_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')

    @transaction.atomic
    def _import_event(self, event_data: dict, tour: Tour, should_geocode: bool) -> str:
        """
        Import a single event.

        Returns 'created', 'updated', or 'skipped'
        """
        # Get or create venue
        venue, venue_created = Venue.objects.get_or_create(
            name=event_data['venue'],
            city=event_data['city'],
            country=event_data['country'],
            defaults={'state': event_data.get('state', '')}
        )

        # Geocode if needed
        if venue_created or (not venue.location and should_geocode):
            if geocode_venue(venue, save=True):
                logger.info(f'Geocoded venue: {venue}')

        # Check if event already exists (by name, venue, and year)
        event_year = event_data['start_date'].year
        existing_events = Event.objects.filter(
            name=event_data['name'],
            venue=venue,
            start_date__year=event_year
        )

        if existing_events.exists():
            # Update existing event
            event = existing_events.first()
            event.start_date = event_data['start_date']
            event.end_date = event_data['end_date']
            event.category = event_data.get('category', 'regular')
            event.status = 'scheduled'
            if event_data.get('external_url'):
                event.external_url = event_data['external_url']
            event.save()

            # Add tour if not already associated
            if tour and tour not in event.tours.all():
                event.tours.add(tour)

            return 'updated'
        else:
            # Create new event
            event = Event.objects.create(
                name=event_data['name'],
                venue=venue,
                start_date=event_data['start_date'],
                end_date=event_data['end_date'],
                category=event_data.get('category', 'regular'),
                status='scheduled',
                external_url=event_data.get('external_url', ''),
            )

            # Add tour
            if tour:
                event.tours.add(tour)

            return 'created'
