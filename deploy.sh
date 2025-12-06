#!/bin/bash
set -e

echo "🚀 Starting deployment of golf-calendar..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "   Please create .env file from .env.prod.example and configure it."
    exit 1
fi

# Build Tailwind CSS locally (for development/testing, Docker will rebuild)
echo "📦 Building Tailwind CSS..."
if [ -f ./tailwindcss ]; then
    ./tailwindcss -i static/css/input.css -o static/css/output.css --minify
    echo "✅ Tailwind CSS built"
else
    echo "⚠️  Warning: tailwindcss binary not found, skipping local build"
    echo "   Docker build will handle Tailwind CSS compilation"
fi

# Build Docker images
echo "🐳 Building Docker images..."
docker compose -f docker-compose.prod.yml build

# Stop existing containers if running
echo "🛑 Stopping existing containers..."
docker compose -f docker-compose.prod.yml down

# Start services
echo "▶️  Starting services..."
docker compose -f docker-compose.prod.yml up -d

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 5

# Run migrations (already handled in docker-compose command, but ensure they ran)
echo "🔄 Verifying migrations..."
docker compose -f docker-compose.prod.yml exec -T web uv run python manage.py migrate --noinput || echo "⚠️  Migrations may have already run"

# Health check
echo "🏥 Performing health check..."
sleep 3
if curl -f http://localhost:8000/admin/login/ > /dev/null 2>&1; then
    echo "✅ Application is responding!"
else
    echo "⚠️  Warning: Application may not be fully ready yet"
    echo "   Check logs with: docker compose -f docker-compose.prod.yml logs -f web"
fi

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Configure nginx proxy manager to forward golfcalendar.jlbrooks.tech to port 8000"
echo "   2. Check logs: docker compose -f docker-compose.prod.yml logs -f"
echo "   3. Create superuser: docker compose -f docker-compose.prod.yml exec web uv run python manage.py createsuperuser"
echo ""

