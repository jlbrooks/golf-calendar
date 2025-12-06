"""
Django management command to identify and remove duplicate events.

Duplicates are defined as events with:
- Same name
- Same venue
- Same year (based on start_date)

Usage:
    # Interactive mode (with confirmation prompts)
    python manage.py remove_duplicates

    # Non-interactive mode (automatic removal)
    python manage.py remove_duplicates --non-interactive

    # Dry run (show what would be removed without actually removing)
    python manage.py remove_duplicates --dry-run

    # Verbose mode (detailed logging for debugging)
    python manage.py remove_duplicates --verbose --dry-run
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Min
from events.models import Event
from collections import defaultdict
import re


class Command(BaseCommand):
    help = 'Identify and remove duplicate events from the database'

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
        self.stdout.write('Searching for duplicate events...\n')
        duplicates = self.find_duplicates()

        if not duplicates:
            self.stdout.write(self.style.SUCCESS('No duplicates found!'))
            return

        # Display summary
        total_duplicates = sum(len(group) - 1 for group in duplicates.values())
        self.stdout.write(
            self.style.WARNING(
                f'Found {len(duplicates)} duplicate groups with {total_duplicates} events to remove\n'
            )
        )

        # Process each duplicate group
        removed_count = 0
        kept_count = 0

        for key, duplicate_group in duplicates.items():
            result = self.process_duplicate_group(duplicate_group, interactive, dry_run)
            removed_count += result['removed']
            kept_count += result['kept']

        # Final summary
        self.stdout.write('\n' + '=' * 70)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'DRY RUN COMPLETE: Would remove {removed_count} duplicates, keeping {kept_count} events'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'COMPLETE: Removed {removed_count} duplicates, kept {kept_count} events'
                )
            )

    def normalize_event_name(self, name):
        """
        Normalize event name for comparison by removing common variations.
        """
        if not name:
            return ""

        # Convert to lowercase
        normalized = name.lower()

        # Remove "the" prefix
        normalized = re.sub(r'^the\s+', '', normalized)

        # Remove common suffixes
        normalized = re.sub(r'\s+(tournament|championship|classic|open|invitational)$', '', normalized)

        # Remove "presented by", "at", etc.
        normalized = re.sub(r'\s+presented\s+by\s+.*$', '', normalized)
        normalized = re.sub(r'\s+at\s+.*$', '', normalized)

        # Normalize spacing
        normalized = ' '.join(normalized.split())

        # Remove punctuation except apostrophes
        normalized = re.sub(r"[^\w\s']", '', normalized)

        return normalized.strip()

    def find_duplicates(self):
        """
        Find all duplicate events grouped by (name, venue, year).
        Returns a dictionary where keys are (name, venue_id, year) tuples
        and values are lists of Event objects.
        """
        all_events = Event.objects.select_related('venue').order_by('created_at')
        total_events = all_events.count()

        if self.verbose:
            self.stdout.write(self.style.NOTICE(f'\nTotal events in database: {total_events}\n'))

        # Group events by (normalized_name, venue_id, year)
        groups = defaultdict(list)
        for event in all_events:
            year = event.start_date.year
            venue_id = event.venue.id if event.venue else None
            venue_name = event.venue.name if event.venue else "NO VENUE"
            normalized_name = self.normalize_event_name(event.name)
            key = (normalized_name, venue_id, year)
            groups[key].append(event)

            if self.verbose:
                self.stdout.write(
                    f'  Event ID {event.id:5d}: "{event.name}" → normalized: "{normalized_name}" | '
                    f'Venue: "{venue_name}" (ID: {venue_id}) | '
                    f'Year: {year} | '
                    f'Dates: {event.start_date} to {event.end_date}'
                )

        if self.verbose:
            self.stdout.write(self.style.NOTICE(f'\nGrouping results:'))
            self.stdout.write(f'  Total unique groups: {len(groups)}')

            # Show group statistics
            group_sizes = defaultdict(int)
            for group_events in groups.values():
                size = len(group_events)
                group_sizes[size] += 1

            self.stdout.write('\n  Group size distribution:')
            for size in sorted(group_sizes.keys()):
                count = group_sizes[size]
                if size == 1:
                    self.stdout.write(f'    {count} groups with 1 event (unique)')
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'    {count} groups with {size} events (DUPLICATES)'
                        )
                    )

            # Show all groups (including non-duplicates) in verbose mode
            self.stdout.write('\n  All groups:')
            for key, group_events in sorted(groups.items(), key=lambda x: len(x[1]), reverse=True):
                normalized_name, venue_id, year = key
                count = len(group_events)
                marker = '  [DUP]' if count > 1 else '       '
                # Show original names in the group
                original_names = ', '.join([f'"{e.name}"' for e in group_events])
                self.stdout.write(
                    f'{marker} {count}x | normalized: "{normalized_name}" | '
                    f'Venue ID: {venue_id} | Year: {year} | '
                    f'Original names: {original_names}'
                )

            self.stdout.write('')  # Empty line for readability

        # Filter to only groups with duplicates (more than 1 event)
        duplicates = {k: v for k, v in groups.items() if len(v) > 1}

        return duplicates

    def process_duplicate_group(self, events, interactive, dry_run):
        """
        Process a group of duplicate events.
        Keep the oldest (by created_at), remove the rest.
        """
        # Sort by created_at to keep the oldest
        events = sorted(events, key=lambda e: e.created_at)
        keep_event = events[0]
        remove_events = events[1:]

        # Display group information
        self.stdout.write('\n' + '-' * 70)
        self.stdout.write(
            self.style.HTTP_INFO(
                f'Duplicate Group: {keep_event.name} at {keep_event.venue.name if keep_event.venue else "Unknown Venue"} ({keep_event.start_date.year})'
            )
        )

        # Show the event we're keeping
        self.stdout.write(
            self.style.SUCCESS(
                f'  KEEP   → ID: {keep_event.id:5d} | Created: {keep_event.created_at.strftime("%Y-%m-%d %H:%M:%S")} | '
                f'Dates: {keep_event.start_date} to {keep_event.end_date}'
            )
        )

        # Show events to be removed
        for event in remove_events:
            self.stdout.write(
                self.style.ERROR(
                    f'  REMOVE → ID: {event.id:5d} | Created: {event.created_at.strftime("%Y-%m-%d %H:%M:%S")} | '
                    f'Dates: {event.start_date} to {event.end_date}'
                )
            )

        # Get confirmation if interactive
        should_remove = True
        if interactive and not dry_run:
            response = input(f'\nRemove {len(remove_events)} duplicate(s)? [y/N]: ')
            should_remove = response.lower() in ['y', 'yes']

        # Remove duplicates
        removed_count = 0
        if should_remove and not dry_run:
            for event in remove_events:
                event.delete()
                removed_count += 1
            self.stdout.write(self.style.SUCCESS(f'  ✓ Removed {removed_count} duplicate(s)'))
        elif should_remove and dry_run:
            removed_count = len(remove_events)
            self.stdout.write(self.style.WARNING(f'  [DRY RUN] Would remove {removed_count} duplicate(s)'))
        else:
            self.stdout.write(self.style.WARNING(f'  ✗ Skipped removal'))

        return {
            'removed': removed_count,
            'kept': 1 if should_remove else 0
        }
