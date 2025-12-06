"""
Django management command to identify and remove duplicate venues.

Duplicates are defined as venues with:
- Similar names (after normalization)
- Same city
- Same country

Usage:
    # Interactive mode (with confirmation prompts)
    python manage.py remove_duplicate_venues

    # Non-interactive mode (automatic removal)
    python manage.py remove_duplicate_venues --non-interactive

    # Dry run (show what would be removed without actually removing)
    python manage.py remove_duplicate_venues --dry-run

    # Verbose mode (detailed logging)
    python manage.py remove_duplicate_venues --verbose --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from events.models import Venue, Event
from collections import defaultdict
import re


class Command(BaseCommand):
    help = 'Identify and remove duplicate venues from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--non-interactive',
            action='store_true',
            help='Remove duplicates without prompting for confirmation',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be removed without actually removing anything',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed logging to help debug duplicate detection',
        )

    def handle(self, *args, **options):
        interactive = not options['non_interactive']
        dry_run = options['dry_run']
        self.verbose = options['verbose']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))

        if self.verbose:
            self.stdout.write(self.style.WARNING('VERBOSE MODE - Detailed logging enabled\n'))

        # Find duplicates
        self.stdout.write('Searching for duplicate venues...\n')
        duplicates = self.find_duplicates()

        if not duplicates:
            self.stdout.write(self.style.SUCCESS('No duplicate venues found!'))
            return

        # Display summary
        total_duplicates = sum(len(group) - 1 for group in duplicates.values())
        self.stdout.write(
            self.style.WARNING(
                f'Found {len(duplicates)} duplicate venue groups with {total_duplicates} venues to merge\n'
            )
        )

        # Process each duplicate group
        merged_count = 0
        kept_count = 0

        for key, duplicate_group in duplicates.items():
            result = self.process_duplicate_group(duplicate_group, interactive, dry_run)
            merged_count += result['merged']
            kept_count += result['kept']

        # Final summary
        self.stdout.write('\n' + '=' * 70)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'DRY RUN COMPLETE: Would merge {merged_count} duplicate venues into {kept_count} venues'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'COMPLETE: Merged {merged_count} duplicate venues into {kept_count} venues'
                )
            )

    def normalize_venue_name(self, name):
        """
        Normalize venue name for comparison by removing common variations.
        More aggressive normalization to catch variations like:
        - "Kapalua Resort - The Plantation Course" vs "Plantation Course at Kapalua"
        - "TPC Scottsdale" vs "TPC Scottsdale (Stadium Course)"
        """
        if not name:
            return ""

        # Convert to lowercase
        normalized = name.lower()

        # Remove content in parentheses (course names, etc.)
        normalized = re.sub(r'\s*\([^)]*\)', '', normalized)

        # Remove punctuation and apostrophes first
        normalized = re.sub(r"[^\w\s]", ' ', normalized)

        # Normalize spacing
        normalized = ' '.join(normalized.split())

        # Remove common noise words (must be done after spacing normalization)
        noise_words = [
            'the', 'at', 'of', 'on', 'in', 'a', 'an',
            'golf', 'course', 'club', 'links', 'resort',
            'country', 'national', 'gc', 'cc'
        ]
        words = normalized.split()
        words = [w for w in words if w not in noise_words]

        # Sort words to handle reordering (e.g., "plantation kapalua" vs "kapalua plantation")
        words.sort()
        normalized = ' '.join(words)

        return normalized.strip()

    def find_duplicates(self):
        """
        Find all duplicate venues grouped by normalized (name, city, country).
        Returns a dictionary where keys are (normalized_name, city, country) tuples
        and values are lists of Venue objects.
        """
        all_venues = Venue.objects.all().order_by('created_at')
        total_venues = all_venues.count()

        if self.verbose:
            self.stdout.write(self.style.NOTICE(f'\nTotal venues in database: {total_venues}\n'))

        # Group venues by normalized (name, city, country)
        groups = defaultdict(list)
        for venue in all_venues:
            normalized_name = self.normalize_venue_name(venue.name)
            city = (venue.city or '').strip().lower()
            country = (venue.country or '').strip().lower()
            key = (normalized_name, city, country)
            groups[key].append(venue)

            if self.verbose:
                self.stdout.write(
                    f'  Venue ID {venue.id:5d}: "{venue.name}" → normalized: "{normalized_name}" | '
                    f'City: {venue.city} | Country: {venue.country} | '
                    f'Events: {venue.events.count()}'
                )

        if self.verbose:
            self.stdout.write(self.style.NOTICE(f'\nGrouping results:'))
            self.stdout.write(f'  Total unique groups: {len(groups)}')

            # Show group statistics
            group_sizes = defaultdict(int)
            for group_venues in groups.values():
                size = len(group_venues)
                group_sizes[size] += 1

            self.stdout.write('\n  Group size distribution:')
            for size in sorted(group_sizes.keys()):
                count = group_sizes[size]
                if size == 1:
                    self.stdout.write(f'    {count} groups with 1 venue (unique)')
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'    {count} groups with {size} venues (DUPLICATES)'
                        )
                    )

            # Show all groups (including non-duplicates) in verbose mode
            self.stdout.write('\n  All groups:')
            for key, group_venues in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
                normalized_name, city, country = key
                count = len(group_venues)
                marker = '  [DUP]' if count > 1 else '       '
                venue_names = ', '.join([f'"{v.name}"' for v in group_venues])
                self.stdout.write(
                    f'{marker} {count}x | "{normalized_name}" | {city}, {country} | {venue_names}'
                )

            self.stdout.write('')  # Empty line for readability

        # Filter to only groups with duplicates (more than 1 venue)
        duplicates = {k: v for k, v in groups.items() if len(v) > 1}

        return duplicates

    @transaction.atomic
    def process_duplicate_group(self, venues, interactive, dry_run):
        """
        Process a group of duplicate venues.
        Keep the one with the most events (or oldest if tied), merge others into it.
        """
        # Sort by number of events (descending), then by created_at (ascending)
        venues = sorted(venues, key=lambda v: (-v.events.count(), v.created_at))
        keep_venue = venues[0]
        merge_venues = venues[1:]

        # Display group information
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(
            self.style.HTTP_INFO(
                f'Duplicate Venue Group: {keep_venue.city}, {keep_venue.country}'
            )
        )

        # Show the venue we're keeping
        self.stdout.write(
            self.style.SUCCESS(
                f'  KEEP   → ID: {keep_venue.id:5d} | Name: "{keep_venue.name}" | '
                f'Events: {keep_venue.events.count()} | '
                f'Created: {keep_venue.created_at.strftime("%Y-%m-%d %H:%M:%S")}'
            )
        )

        # Show venues to be merged
        total_events_to_migrate = 0
        for venue in merge_venues:
            event_count = venue.events.count()
            total_events_to_migrate += event_count
            self.stdout.write(
                self.style.ERROR(
                    f'  MERGE  → ID: {venue.id:5d} | Name: "{venue.name}" | '
                    f'Events: {event_count} | '
                    f'Created: {venue.created_at.strftime("%Y-%m-%d %H:%M:%S")}'
                )
            )

        if total_events_to_migrate > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'  → Will migrate {total_events_to_migrate} events to venue ID {keep_venue.id}'
                )
            )

        # Get confirmation if interactive
        should_merge = True
        if interactive and not dry_run:
            response = input(f'\nMerge {len(merge_venues)} duplicate venue(s)? [y/N]: ')
            should_merge = response.lower() in ['y', 'yes']

        # Merge duplicates
        merged_count = 0
        if should_merge and not dry_run:
            for venue in merge_venues:
                # Move all events to the kept venue
                venue.events.all().update(venue=keep_venue)
                # Delete the duplicate venue
                venue.delete()
                merged_count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'  ✓ Merged {merged_count} duplicate venue(s), migrated {total_events_to_migrate} events'
                )
            )
        elif should_merge and dry_run:
            merged_count = len(merge_venues)
            self.stdout.write(
                self.style.WARNING(
                    f'  [DRY RUN] Would merge {merged_count} venue(s) and migrate {total_events_to_migrate} events'
                )
            )
        else:
            self.stdout.write(self.style.WARNING(f'  ✗ Skipped merge'))

        return {
            'merged': merged_count,
            'kept': 1 if should_merge else 0
        }
