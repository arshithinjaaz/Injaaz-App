FROM python:3.10-slim

# Install OS-level deps for building packages (psycopg2, etc.)
RUN apt-get update --yes \
 && apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      libpq-dev \
      curl \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt /app/requirements.txt

RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Create a non-root user (optional)
RUN useradd -m injaaz && chown -R injaaz /app
USER injaaz

# Ensure PORT is set by the platform (Render provides PORT). Default to 5000 locally.
ENV PORT=${PORT:-5000}
ENV WEB_CONCURRENCY=${WEB_CONCURRENCY:-1}

EXPOSE 5000

# Run via sh -c so environment variables like $PORT expand
CMD sh -c "gunicorn -w ${WEB_CONCURRENCY} -b 0.0.0.0:${PORT} app:app"