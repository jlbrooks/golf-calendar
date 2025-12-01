# Phase 5 Implementation Summary

## Overview
Phase 5 implements data import capabilities for golf events. While automated web scraping of the PGA Tour website proved challenging due to JavaScript rendering, we implemented robust CSV import functionality and created a scraper framework for future enhancement.

## What Was Implemented

### 1. Web Scraping Framework (`events/scrapers.py`)

**PGATourScraper Class**:
- Attempts multiple data sources (API, HTML)
- Handles date parsing from various formats
- Automatically determines event categories (major, regular, playoff)
- Includes error handling and logging
- Ready for enhancement with headless browser support

**Challenges Discovered**:
- PGA Tour website (https://www.pgatour.com/schedule) is JavaScript-rendered using React/Chakra UI
- No publicly accessible API endpoint found
- HTML parsing not effective for dynamic content
- Would require Selenium/Playwright for full automation

### 2. PGA Tour Scraper Command (`events/management/commands/scrape_pga_tour.py`)

**Features**:
- `--dry-run` flag to preview without saving
- `--geocode` flag to automatically geocode venues
- Automatic tour creation/lookup
- Upsert logic (creates new events, updates existing)
- Transaction safety with `@transaction.atomic`
- Detailed progress reporting

**Usage**:
```bash
# Dry run to preview
docker compose exec web uv run python manage.py scrape_pga_tour --dry-run

# Real import with geocoding
docker compose exec web uv run python manage.py scrape_pga_tour --geocode
```

**Current Status**: Framework ready, but needs headless browser implementation for PGA Tour's JavaScript-rendered pages.

### 3. CSV Import Command (`events/management/commands/import_events_csv.py`)

**Fully Functional** - This is the recommended import method currently.

**CSV Format**:
```csv
name,venue_name,city,state,country,start_date,end_date,tour_name,category,external_url
```

**Features**:
- Simple CSV format for easy data entry
- Automatic venue creation and geocoding
- Tour association (optional - leave empty for majors)
- Upsert logic (won't duplicate events)
- `--dry-run` for testing
- `--geocode` for automatic venue location lookup

**Usage**:
```bash
# Preview import
docker compose exec web uv run python manage.py import_events_csv sample_events.csv --dry-run

# Import with geocoding
docker compose exec web uv run python manage.py import_events_csv sample_events.csv --geocode

# Import without geocoding (faster)
docker compose exec web uv run python manage.py import_events_csv events.csv
```

### 4. Sample Data File (`sample_events.csv`)

Pre-populated with 10 2025 PGA Tour events:
- The Sentry (Hawaii)
- Sony Open
- American Express
- Farmers Insurance Open
- WM Phoenix Open
- Genesis Invitational
- The Masters (major)
- PGA Championship (major)
- U.S. Open (major)
- The Open Championship (major)

## Files Created/Modified

```
events/
├── scrapers.py                        # Web scraping framework
└── management/commands/
    ├── scrape_pga_tour.py            # PGA Tour scraper (needs enhancement)
    └── import_events_csv.py          # CSV import (fully functional)

sample_events.csv                      # Sample event data
pyproject.toml                         # Added beautifulsoup4, lxml
uv.lock                                # Updated dependencies
```

## Dependencies Added

- `beautifulsoup4==4.14.2` - HTML parsing
- `lxml==6.0.2` - Fast XML/HTML parser
- `soupsieve==2.8` - CSS selector library (dependency)

## CSV Import Format Details

### Required Fields:
- `name` - Event name
- `venue_name` - Golf course name
- `city` - City
- `country` - Country
- `start_date` - Format: YYYY-MM-DD
- `end_date` - Format: YYYY-MM-DD

### Optional Fields:
- `state` - State/Province (empty for countries without states)
- `tour_name` - Tour affiliation (empty for independent events/majors)
- `category` - major|regular|playoff|qualifier|team|other (defaults to 'regular')
- `external_url` - Official event website

### Examples:

**PGA Tour Event**:
```csv
Farmers Insurance Open,Torrey Pines Golf Course,San Diego,California,USA,2025-01-22,2025-01-25,PGA Tour,regular,https://www.pgatour.com
```

**Major Championship (no tour)**:
```csv
The Masters Tournament,Augusta National Golf Club,Augusta,Georgia,USA,2025-04-10,2025-04-13,,major,https://www.masters.com
```

**International Event**:
```csv
The Open Championship,Royal Portrush Golf Club,Portrush,,Northern Ireland,2025-07-17,2025-07-20,,major,https://www.theopen.com
```

## Testing

### Test 1: CSV Import
```bash
docker compose exec web uv run python manage.py import_events_csv sample_events.csv --geocode
```

**Result**: ✅ Successfully imported 10 events with geocoded venues

### Test 2: View on Website
Navigate to http://localhost:8000

**Result**: ✅ All 14 events displayed (4 original + 10 new)

### Test 3: Filtering
- Filter by tour: "PGA Tour" → Shows 6 events
- Filter by category: "Major Championship" → Shows 4 majors
- Filter by location: "California, USA" with 100-mile radius → Shows California events

**Result**: ✅ All filters working correctly

## Upsert Logic

The import commands are idempotent - running twice won't create duplicates.

**Event Matching**:
Events are matched by:
1. Event name
2. Venue
3. Year

If a match is found, the event is **updated** with new data.
If no match, a new event is **created**.

**Example**:
```bash
# First run: Creates 10 events
docker compose exec web uv run python manage.py import_events_csv sample_events.csv

# Second run: Updates the same 10 events (no duplicates)
docker compose exec web uv run python manage.py import_events_csv sample_events.csv
```

## Future Enhancements

### For Automated Web Scraping:

1. **Add Selenium/Playwright**:
   ```bash
   uv add selenium
   ```
   - Render JavaScript pages
   - Extract data from React components
   - Handle dynamic content

2. **Alternative Data Sources**:
   - ESPN Golf API (if available)
   - Golf Channel RSS feeds
   - Official World Golf Ranking data
   - Tour-specific APIs

3. **Scheduled Jobs**:
   - Use Celery + Redis for periodic scraping
   - Cron job to run weekly
   - Update existing events, add new ones

4. **Additional Tours**:
   - DP World Tour scraper
   - LPGA Tour scraper
   - LIV Golf scraper
   - Korn Ferry Tour

### For CSV Import:

1. **Bulk Upload UI**:
   - Django admin action for CSV upload
   - Web form for file upload
   - Validation and preview

2. **Excel Support**:
   ```bash
   uv add openpyxl
   ```
   - Import from .xlsx files
   - Multiple sheets for different tours

3. **Google Sheets Integration**:
   - Read from shared Google Sheet
   - Community-maintained event calendar

## Recommended Workflow

**Current Best Practice**:

1. **Manual Data Entry**:
   - Use Django admin at http://localhost:8000/admin
   - Add events one by one with full control

2. **Bulk Import via CSV**:
   - Create CSV file with tour schedules
   - Import using `import_events_csv` command
   - Geocode venues automatically

3. **Periodic Updates**:
   - Re-run CSV import with updated file
   - Events get updated, not duplicated
   - New events added automatically

**Example Annual Workflow**:
```bash
# January: Import full year schedule
docker compose exec web uv run python manage.py import_events_csv pga_2025.csv --geocode

# Throughout year: Update as needed
docker compose exec web uv run python manage.py import_events_csv pga_2025_updates.csv
```

## Data Sources for Manual Import

Where to find tour schedules:
- PGA Tour: https://www.pgatour.com/schedule
- DP World Tour: https://www.dpworldtour.com/tournament-calendar
- LPGA Tour: https://www.lpga.com/tournaments
- LIV Golf: https://www.livgolf.com/schedule

Convert to CSV format and import!

## Summary

Phase 5 delivers:
- ✅ Robust CSV import system (fully working)
- ✅ Web scraper framework (needs enhancement for PGA Tour)
- ✅ Sample data with 10 real events
- ✅ Automatic geocoding integration
- ✅ Upsert logic to prevent duplicates
- ✅ Dry-run testing capabilities

**Recommendation**: Use CSV import for now, enhance web scraping with Selenium/Playwright in future iteration if automated updates are needed.
