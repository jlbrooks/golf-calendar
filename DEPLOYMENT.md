# Homelab Deployment Guide

This guide covers deploying the golf-calendar application to your Proxmox homelab Docker VM with nginx proxy manager.

## Prerequisites

- Docker VM running Ubuntu with Docker and Docker Compose installed
- Nginx Proxy Manager running and accessible
- Domain `golfcalendar.jlbrooks.tech` configured in DNS (pointing to your homelab)
- SSH access to the Docker VM

## Step 1: Prepare the Deployment Environment

### 1.1 Clone or Transfer the Repository

On your Docker VM, clone the repository or transfer the project files:

```bash
# If using git
git clone <repository-url> /opt/golf-calendar
cd /opt/golf-calendar

# Or transfer files via SCP/rsync from your development machine
```

### 1.2 Create Production Environment File

Create a `.env` file from the template:

```bash
cp env.prod.example .env
```

Then edit `.env` and update the values.

**Important:** Generate a secure SECRET_KEY:

```bash
python3 -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Copy the output and paste it as the `SECRET_KEY` value in your `.env` file.

Verify your `.env` file contains:
- `SECRET_KEY` - Your generated secret key
- `DEBUG=False` - Must be False in production
- `ALLOWED_HOSTS=golfcalendar.jlbrooks.tech` - Your domain
- `DATABASE_URL` - Database connection string (default should work)

### 1.3 Verify Tailwind CSS Binary

Ensure the `tailwindcss` binary is present and executable:

```bash
ls -la tailwindcss
chmod +x tailwindcss
```

## Step 2: Deploy the Application

### 2.1 Run the Deployment Script

The `deploy.sh` script automates the deployment process:

```bash
./deploy.sh
```

This script will:
- Build Tailwind CSS
- Build Docker images
- Stop existing containers
- Start services with migrations and static file collection
- Perform a health check

### 2.2 Manual Deployment (Alternative)

If you prefer manual control:

```bash
# Build Tailwind CSS
./tailwindcss -i static/css/input.css -o static/css/output.css --minify

# Build Docker images
docker compose -f docker-compose.prod.yml build

# Start services
docker compose -f docker-compose.prod.yml up -d

# Check logs
docker compose -f docker-compose.prod.yml logs -f
```

## Step 3: Initial Setup

### 3.1 Create Superuser

Create an admin user to access the Django admin:

```bash
docker compose -f docker-compose.prod.yml exec web uv run python manage.py createsuperuser
```

Follow the prompts to create your admin account.

### 3.2 (Optional) Load Sample Data

If you have sample data to load:

```bash
docker compose -f docker-compose.prod.yml exec web uv run python manage.py load_sample_data
```

### 3.3 (Optional) Geocode Venues

If you have venues that need geocoding:

```bash
docker compose -f docker-compose.prod.yml exec web uv run python manage.py geocode_venues --all --delay 2.0
```

## Step 4: Configure Nginx Proxy Manager

### 4.1 Access Nginx Proxy Manager

1. Log into your Nginx Proxy Manager web interface
2. Navigate to "Hosts" → "Proxy Hosts"
3. Click "Add Proxy Host"

### 4.2 Configure the Proxy Host

**Details Tab:**
- **Domain Names:** `golfcalendar.jlbrooks.tech`
- **Scheme:** `http`
- **Forward Hostname/IP:** `docker-vm-ip` (or `localhost` if NPM is on same VM)
- **Forward Port:** `8000`
- **Cache Assets:** Enabled (recommended)
- **Block Common Exploits:** Enabled
- **Websockets Support:** Not required (Django/HTMX doesn't use WebSockets)

**SSL Tab:**
- **SSL Certificate:** Request a new SSL Certificate with Let's Encrypt
- **Force SSL:** Enabled
- **HTTP/2 Support:** Enabled
- **HSTS Enabled:** Enabled (recommended)

**Advanced Tab:**
- Leave default unless you need custom nginx configuration

### 4.3 Save and Test

Click "Save" and test access at `https://golfcalendar.jlbrooks.tech`

## Step 5: Verify Deployment

### 5.1 Check Application Status

```bash
# View running containers
docker compose -f docker-compose.prod.yml ps

# Check logs
docker compose -f docker-compose.prod.yml logs -f web

# Check database connection
docker compose -f docker-compose.prod.yml exec web uv run python manage.py dbshell
```

### 5.2 Test Application

1. Visit `https://golfcalendar.jlbrooks.tech` in your browser
2. Verify the homepage loads correctly
3. Test filtering and search functionality
4. Access admin at `https://golfcalendar.jlbrooks.tech/admin/`

## Maintenance

### Viewing Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Web service only
docker compose -f docker-compose.prod.yml logs -f web

# Database service only
docker compose -f docker-compose.prod.yml logs -f db
```

### Updating the Application

```bash
# Pull latest code
git pull  # or transfer updated files

# Rebuild and redeploy
./deploy.sh
```

### Database Backups

```bash
# Create backup
docker compose -f docker-compose.prod.yml exec db pg_dump -U postgres golf_calendar > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
docker compose -f docker-compose.prod.yml exec -T db psql -U postgres golf_calendar < backup_file.sql
```

### Running Management Commands

```bash
# General format
docker compose -f docker-compose.prod.yml exec web uv run python manage.py <command>

# Examples
docker compose -f docker-compose.prod.yml exec web uv run python manage.py migrate
docker compose -f docker-compose.prod.yml exec web uv run python manage.py createsuperuser
docker compose -f docker-compose.prod.yml exec web uv run python manage.py scrape_pga_tour
```

### Stopping Services

```bash
# Stop services (keeps containers)
docker compose -f docker-compose.prod.yml stop

# Stop and remove containers (keeps volumes/data)
docker compose -f docker-compose.prod.yml down

# Stop and remove everything including volumes (⚠️ deletes database)
docker compose -f docker-compose.prod.yml down -v
```

## Troubleshooting

### Application Not Responding

1. Check if containers are running:
   ```bash
   docker compose -f docker-compose.prod.yml ps
   ```

2. Check logs for errors:
   ```bash
   docker compose -f docker-compose.prod.yml logs web
   ```

3. Verify database is healthy:
   ```bash
   docker compose -f docker-compose.prod.yml exec db pg_isready -U postgres
   ```

### Static Files Not Loading

1. Verify static files were collected:
   ```bash
   docker compose -f docker-compose.prod.yml exec web ls -la /app/staticfiles
   ```

2. Recollect static files:
   ```bash
   docker compose -f docker-compose.prod.yml exec web uv run python manage.py collectstatic --noinput
   ```

### Database Connection Issues

1. Check database is running:
   ```bash
   docker compose -f docker-compose.prod.yml ps db
   ```

2. Verify DATABASE_URL in .env matches docker-compose settings
3. Check database logs:
   ```bash
   docker compose -f docker-compose.prod.yml logs db
   ```

### Nginx Proxy Manager Issues

1. Verify the proxy host is pointing to the correct IP and port
2. Check Nginx Proxy Manager logs
3. Ensure port 8000 is accessible from NPM (check firewall if on different VMs)
4. Test direct access: `curl http://docker-vm-ip:8000`

### Tailwind CSS Not Updating

1. Rebuild Tailwind CSS locally and commit:
   ```bash
   ./tailwindcss -i static/css/input.css -o static/css/output.css --minify
   ```

2. Or rebuild Docker image:
   ```bash
   docker compose -f docker-compose.prod.yml build --no-cache web
   docker compose -f docker-compose.prod.yml up -d web
   ```

## Security Considerations

- ✅ `DEBUG=False` in production
- ✅ Strong `SECRET_KEY` generated
- ✅ SSL/TLS via Let's Encrypt
- ✅ Database password in .env (not committed)
- ⚠️ Consider changing default Postgres password in production
- ⚠️ Review `ALLOWED_HOSTS` regularly
- ⚠️ Keep Docker images updated
- ⚠️ Regular database backups

## Architecture Overview

```
Internet
  ↓
Nginx Proxy Manager (SSL termination)
  ↓
Docker VM:8000
  ↓
golf-calendar web container (Gunicorn)
  ↓
PostGIS database container
```

## Ports

- **8000:** Web application (internal, accessed via NPM)
- **5432:** PostgreSQL (internal, not exposed to host)

## Volumes

- `postgres_data`: Persistent database storage

## Network

Services communicate via Docker bridge network `golf_calendar_network`.

