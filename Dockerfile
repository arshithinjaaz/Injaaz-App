# name=Dockerfile
FROM python:3.10-slim

# Install OS-level dependencies needed to build Python packages (psycopg2, etc.)
RUN apt-get update --yes \
 && apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      libpq-dev \
      curl \
 && rm -rf /var/lib/apt/lists/*

# Create app user
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt /app/requirements.txt

# Install pip and dependencies
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Ensure a non-root user (optional)
RUN useradd -m injaaz && chown -R injaaz /app
USER injaaz

# Render provides a $PORT env var; default to 5000 if not set
ENV PORT 5000

# Expose port (for clarity)
EXPOSE 5000

# Default command:
# - Try to run the Flask app via gunicorn. Adjust "app:app" if your Flask app object is located elsewhere.
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:$PORT", "app:app"]