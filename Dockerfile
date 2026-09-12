FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed by psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before copying app code
# (layer cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
COPY --from=frontend-build /frontend/dist ./frontend/dist

RUN addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Start: run Alembic migrations then start Uvicorn
# Using shell form so we can chain commands
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers
