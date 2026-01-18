FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY src/ ./src/
COPY templates/ ./templates/
COPY static/ ./static/
COPY run.py .

# Copy database schema
COPY db/ ./db/

# Create database directory and initialize with schema
# This creates an empty database structure that can be populated later
RUN mkdir -p db && \
    sqlite3 db/uloom_quran.db < db/schema.sql && \
    sqlite3 db/uloom_quran.db < db/usul_qiraat_schema.sql && \
    sqlite3 db/uloom_quran.db < db/basmala_schema.sql

# Copy data files (mutashabihat, exports)
COPY data/mutashabihat/ ./data/mutashabihat/
COPY data/exports/ ./data/exports/

# Expose port (Cloud Run uses 8080)
EXPOSE 8080

# Run with gunicorn (4 workers for concurrency)
CMD ["gunicorn", "src.api.main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8080", "--timeout", "120"]
