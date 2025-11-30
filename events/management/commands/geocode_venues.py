"""Management command to geocode venues."""
from django.core.management.base import BaseCommand
from events.models import Venue
from events.utils import geocode_venue
from time import sleep


class Command(BaseCommand):
    help = 'Geocode venues that do not have location data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Geocode all venues, even those with existing locations',
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=1.0,
            help='Delay in seconds between geocoding requests (default: 1.0)',
        )

    def handle(self, *args, **options):
        if options['all']:
            venues = Venue.objects.all()
            self.stdout.write('Geocoding all venues...')
        else:
            venues = Venue.objects.filter(location__isnull=True)
            self.stdout.write('Geocoding venues without location data...')

        total = venues.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No venues to geocode.'))
            return

        success_count = 0
        failure_count = 0

        for i, venue in enumerate(venues, 1):
            self.stdout.write(f'[{i}/{total}] Geocoding: {venue}')

            # Clear location if --all flag is used
            if options['all']:
                venue.location = None

            if geocode_venue(venue, save=True):
                success_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  ✓ Success: {venue.latitude}, {venue.longitude}')
                )
            else:
                failure_count += 1
                self.stdout.write(self.style.ERROR('  ✗ Failed to geocode'))

            # Rate limiting
            if i < total:
                sleep(options['delay'])

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Geocoding complete: {success_count} succeeded, {failure_count} failed'
        ))
