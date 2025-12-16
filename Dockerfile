# Multi-stage Dockerfile: build wheels in builder stage, install from wheels in final image

# Stage 1: builder - build wheels
FROM python:3.10-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels

COPY requirements-prod.txt /wheels/requirements-prod.txt

RUN python -m pip install --upgrade pip setuptools wheel \
 && pip wheel --wheel-dir=/wheels -r /wheels/requirements-prod.txt

# Stage 2: runtime image
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy built wheels and install from them
COPY --from=builder /wheels /wheels
COPY requirements-prod.txt /app/requirements-prod.txt

RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install --no-index --find-links=/wheels -r /app/requirements-prod.txt

# Copy application code
COPY . /app

# Create non-root user and adjust permissions
RUN useradd -m injaaz && chown -R injaaz /app
USER injaaz

ENV PORT=${PORT:-5000}
ENV WEB_CONCURRENCY=${WEB_CONCURRENCY:-1}

EXPOSE 5000

CMD ["gunicorn", "wsgi:app", "-w", "1", "--threads", "4", "-b", "0.0.0.0:${PORT}"]