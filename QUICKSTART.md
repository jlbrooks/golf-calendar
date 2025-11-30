# Quick Start Guide

Get the Golf Calendar application running in under 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Git (to clone the repository)

## Steps

### 1. Start the Application

```bash
# Start Docker containers
docker compose up -d

# Wait for database to be ready (about 10 seconds)
```

### 2. Run Database Migrations

```bash
# Create and apply migrations
docker compose exec web uv run python manage.py makemigrations
docker compose exec web uv run python manage.py migrate
```

### 3. Create Admin User

```bash
docker compose exec web uv run python manage.py createsuperuser
```

Follow the prompts to create your admin account.

### 4. Load Sample Data

```bash
docker compose exec web uv run python manage.py load_sample_data
```

This creates:
- 3 golf tours (PGA Tour, DP World Tour, LPGA Tour)
- 4 venues with geocoded locations
- 4 sample events (The Masters, Scottish Open, etc.)

### 5. Access the Application

Open your browser and visit:

**Main Event Listing**: http://localhost:8000
- View all golf events
- Filter by tour, category, status, dates, location
- Dynamic filtering with HTMX (no page reload)

**Admin Interface**: http://localhost:8000/admin
- Manage tours, venues, and events
- Add new events manually
- View venues on interactive map
- Login with the superuser credentials you created

## Usage Examples

### Filter by Location
1. Go to http://localhost:8000
2. In the "Location" field, enter: `Augusta, GA, USA`
3. Set "Radius (miles)" to: `50`
4. Table updates automatically to show events near Augusta

### Filter by Tour
1. Select "PGA Tour" from the Tour dropdown
2. Table updates to show only PGA Tour events

### Filter by Date Range
1. Set "From Date" to upcoming date
2. Set "To Date" to future date
3. See only events in that range

### Add New Event (Admin)
1. Go to http://localhost:8000/admin
2. Click "Events" → "Add Event"
3. Fill in event details
4. Select venue (or create new one)
5. Choose tours (can select multiple for co-sanctioned events)
6. Save

## Stopping the Application

```bash
docker compose down
```

To remove all data (including database):
```bash
docker compose down -v
```

## Rebuilding Tailwind CSS

If you modify templates and need to rebuild CSS:

```bash
./build-tailwind.sh
```

## Viewing Logs

```bash
# All logs
docker compose logs

# Follow logs
docker compose logs -f

# Just web server logs
docker compose logs -f web
```

## Troubleshooting

**Port 8000 already in use**:
Edit `docker-compose.yml` and change the web service ports from `8000:8000` to `8001:8000` (or another port).

**Database connection errors**:
Wait a few more seconds for PostgreSQL to fully start, then retry migrations.

**Geocoding fails**:
This is normal if the OpenStreetMap Nominatim API is rate-limited or the location format isn't recognized. Try again in a few seconds.

## Next Steps

- Explore the admin interface
- Add more events manually
- Try different filter combinations
- Check out PHASE3-SUMMARY.md for implementation details
