# Use Python 3.12 slim image
FROM python:3.12-slim

# Install system dependencies for PostGIS and psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-cache

# Copy application code
COPY . .

# Expose port 8000
EXPOSE 8000

# Run migrations and start server
CMD ["uv", "run", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
