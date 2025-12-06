# AGENTS.md

Guidance for AI assistants and contributors working in this repo.

## Expectations for AI helpers
- Favor existing commands/scripts; avoid long-running/watch processes.
- Do not revert user changes; avoid destructive operations (`reset --hard`, dropping DB).
- Respect service limits (Nominatim 1 req/sec) and privacy (no secrets/PII in logs).
- Prefer minimal, reversible edits; add brief comments only when code isn’t obvious.

## Project overview
Golf Calendar is a Django 5.2 / Python 3.12 app for tracking pro and amateur golf events. It uses PostGIS for geo queries, HTMX for dynamic filtering, Tailwind for styling, and Playwright scrapers for schedule imports.

## Quick start (Docker first)
```bash
docker compose up --build
docker compose exec web uv run python manage.py migrate
docker compose exec web uv run python manage.py createsuperuser
docker compose exec web uv run python manage.py runserver 0.0.0.0:8000
```

Local (no Docker):
```bash
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

## Key paths
- `config/`: Django settings and root URLs
- `events/`: models, views, business logic, management commands
- `templates/events/`: HTMX partials and full pages
- `static/`: Tailwind build output
- `events/utils.py`: geocoding helpers
- `events/views.py`: filtering and distance queries
- `events/scrapers.py`: Playwright PGA Tour scraper

## Coding & testing
- Python style: use f-strings, type hints where helpful, keep functions small.
- Run tests before proposing changes: `uv run python manage.py test` (or `uv run pytest` if configured).
- Keep dependencies consistent with `uv`; prefer existing patterns before adding libs.

## Migrations
- One logical change set per migration; never edit historical migrations.
- Commands:
  - Docker: `docker compose exec web uv run python manage.py makemigrations && docker compose exec web uv run python manage.py migrate`
  - Local: `uv run python manage.py makemigrations && uv run python manage.py migrate`

## HTMX and templates
- When `HX-Request` is set, return partial `templates/events/_event_table.html`; otherwise render `templates/events/event_list.html`.
- Rebuild Tailwind after template changes: `./build-tailwind.sh` (uses bundled CLI; input `static/css/input.css`, output `static/css/output.css`).

## Geocoding & PostGIS
- Nominatim: include `User-Agent: 'GolfCalendar/1.0'`, respect 1 req/sec; `geocode_venues` has `--delay` (default 1.0s) and `--all` for re-geocode.
- Distance filtering uses `venue__location__distance_lte=(point, D(mi=radius_miles))`; city-level queries require PostGIS.
- Default DB URLs: local `postgis://postgres:postgres@localhost:5432/golf_calendar`; Docker `postgis://postgres:postgres@db:5432/golf_calendar`. Container exposes 5435:5432 on host. Health check: `pg_isready -U postgres`.

## Scraping
- `PGATourScraper` (Playwright) pulls Next.js `__NEXT_DATA__`; use context manager `with PGATourScraper()`.
- Be gentle: custom UA, avoid unnecessary page hits, and keep delays if pages resist automation.

## Data handling & secrets
- Use `.env` for secrets; required: `DATABASE_URL`, `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`.
- Do not log secrets or PII; redact when copying logs into conversations.

## Management commands (examples)
```bash
# Seed sample data
docker compose exec web uv run python manage.py load_sample_data

# Geocode venues
docker compose exec web uv run python manage.py geocode_venues
docker compose exec web uv run python manage.py geocode_venues --all --delay 2.0

# Import events CSV (geocode during import)
docker compose exec web uv run python manage.py import_events_csv sample_events.csv --geocode

# Scrape PGA Tour schedule
docker compose exec web uv run python manage.py scrape_pga_tour
```

## Cookbook tasks
- Add tour/event: create Tour, Venue, geocode if missing, then Event linked to both.
- Import CSV: ensure header `name,venue_name,city,state,country,start_date,end_date,tour_name,category,external_url`; dates YYYY-MM-DD.
- Tailwind update: edit templates or CSS, run `./build-tailwind.sh`.
- Geocode all venues with slower pace: `geocode_venues --all --delay 2.0`.

## Deployment notes
- Build assets before deploy: `./build-tailwind.sh`.
- Set `DEBUG=False`, real `SECRET_KEY`, and production `ALLOWED_HOSTS`.
- Ensure PostGIS available on target DB; match port mapping if using Docker.

## When in doubt
- Reuse existing patterns (HTMX partials, PostGIS queries, management commands).
- Prefer small, reversible changes and add tests when behavior changes.
- Avoid destructive DB actions; if cleanup needed, do it narrowly.
