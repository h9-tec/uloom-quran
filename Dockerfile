FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application code
COPY src/ ./src/
COPY templates/ ./templates/
COPY static/ ./static/
COPY run.py .

# Copy SQLite database (embedded for read-heavy workload)
COPY db/uloom_quran.db ./db/uloom_quran.db

# Expose port (Cloud Run uses 8080)
EXPOSE 8080

# Run with gunicorn (4 workers for concurrency)
CMD ["gunicorn", "src.api.main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8080", "--timeout", "120"]
