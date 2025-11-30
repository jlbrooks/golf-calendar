# Database Migrations Guide

## Initial Setup

After starting the Docker containers for the first time, you need to create and apply migrations:

### 1. Create Migrations

```bash
docker compose exec web uv run python manage.py makemigrations
```

This will create migration files in `events/migrations/` that define:
- Tour table with name, slug, website_url
- Venue table with name, location fields, and PostGIS Point field
- Event table with dates, status, category, and relationships

### 2. Apply Migrations

```bash
docker compose exec web uv run python manage.py migrate
```

This applies all migrations including:
- Django's built-in migrations (auth, admin, sessions, etc.)
- PostGIS extension setup
- events app migrations

### 3. Create Superuser

```bash
docker compose exec web uv run python manage.py createsuperuser
```

Follow the prompts to create an admin user.

### 4. Load Sample Data (Optional)

```bash
docker compose exec web uv run python manage.py load_sample_data
```

This creates:
- 3 tours (PGA Tour, DP World Tour, LPGA Tour)
- 4 venues (Augusta, St Andrews, Pebble Beach, Renaissance Club)
- 4 events (The Masters, Scottish Open, Pebble Beach Pro-Am, The Open)
- Geocodes all venues

## Future Migrations

When you make changes to models:

```bash
# Create migration files
docker compose exec web uv run python manage.py makemigrations

# Review the generated migration files
cat events/migrations/XXXX_*.py

# Apply migrations
docker compose exec web uv run python manage.py migrate

# Check migration status
docker compose exec web uv run python manage.py showmigrations
```

## Troubleshooting

**Migration conflicts**: If you have migration conflicts, you can:
```bash
docker compose exec web uv run python manage.py makemigrations --merge
```

**Reset database** (DANGER: loses all data):
```bash
docker compose down -v  # Remove volumes
docker compose up -d    # Restart
docker compose exec web uv run python manage.py migrate
```
