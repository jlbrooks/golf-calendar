"""Management command to import events from CSV file."""
from django.core.management.base import BaseCommand
from django.db import transaction
from events.models import Tour, Venue, Event
from events.utils import geocode_venue
from datetime import datetime
import csv
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '''Import events from CSV file.

    CSV Format:
    name,venue_name,city,state,country,start_date,end_date,tour_name,category,external_url

    Example:
    The Masters,Augusta National Golf Club,Augusta,Georgia,USA,2025-04-10,2025-04-13,PGA Tour,major,https://www.masters.com
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to CSV file'
        )
        parser.add_argument(
            '--geocode',
            action='store_true',
            help='Geocode venues after import',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview import without saving',
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        should_geocode = options['geocode']
        dry_run = options['dry_run']

        self.stdout.write(f'Importing events from {csv_file}...')

        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                events_data = list(reader)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {csv_file}'))
            return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading CSV: {e}'))
            return

        self.stdout.write(f'Found {len(events_data)} events in CSV')

        created_count = 0
        updated_count = 0
        error_count = 0

        for row in events_data:
            try:
                if dry_run:
                    self.stdout.write(f'  [DRY RUN] Would import: {row["name"]}')
                    continue

                result = self._import_event(row, should_geocode)

                if result == 'created':
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {row["name"]}'))
                elif result == 'updated':
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(f'  ↻ Updated: {row["name"]}'))

            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {row.get("name", "unknown")}: {e}'))
                logger.exception(f'Failed to import row: {row}')

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Import complete!'))
        self.stdout.write(f'  Created: {created_count}')
        self.stdout.write(f'  Updated: {updated_count}')
        self.stdout.write(f'  Errors:  {error_count}')

    @transaction.atomic
    def _import_event(self, row: dict, should_geocode: bool) -> str:
        """Import a single event from CSV row."""

        # Parse dates
        start_date = datetime.strptime(row['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(row['end_date'], '%Y-%m-%d').date()

        # Get or create tour
        tour = None
        if row.get('tour_name'):
            tour, _ = Tour.objects.get_or_create(
                name=row['tour_name'].strip()
            )

        # Get or create venue
        venue, venue_created = Venue.objects.get_or_create(
            name=row['venue_name'].strip(),
            city=row['city'].strip(),
            country=row['country'].strip(),
            defaults={'state': row.get('state', '').strip()}
        )

        # Geocode if needed
        if (venue_created or not venue.location) and should_geocode:
            if geocode_venue(venue, save=True):
                logger.info(f'Geocoded venue: {venue}')

        # Check if event exists
        event_year = start_date.year
        existing_events = Event.objects.filter(
            name=row['name'].strip(),
            venue=venue,
            start_date__year=event_year
        )

        category = row.get('category', 'regular').strip()
        if category not in dict(Event.CATEGORY_CHOICES):
            category = 'regular'

        if existing_events.exists():
            # Update
            event = existing_events.first()
            event.start_date = start_date
            event.end_date = end_date
            event.category = category
            if row.get('external_url'):
                event.external_url = row['external_url'].strip()
            event.save()

            if tour and tour not in event.tours.all():
                event.tours.add(tour)

            return 'updated'
        else:
            # Create
            event = Event.objects.create(
                name=row['name'].strip(),
                venue=venue,
                start_date=start_date,
                end_date=end_date,
                category=category,
                status='scheduled',
                external_url=row.get('external_url', '').strip(),
            )

            if tour:
                event.tours.add(tour)

            return 'created'
