# Dockerfile
# ---- Stage 1: builder ----
    
FROM python:3.11-slim AS builder

WORKDIR /app

# build tools needed to compile some Python packages
# libpq-dev is needed to compile psycopg2 (the Postgres driver) from source
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# copy ONLY requirements.txt first — this is the layer-caching trick
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: runtime ----
FROM python:3.11-slim

# libpq5 is the runtime library psycopg2 links against (the compiler
# that built it stays behind in the builder stage; only the library itself
# needs to travel to this clean runtime image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy the already-installed packages from the builder stage
COPY --from=builder /install /usr/local

# copy the actual application code
COPY . .

# create a non-root user, give it ownership of /app (so it can write
# files like celerybeat-schedule), then switch to it
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["gunicorn", "parselio.wsgi:application", "--bind", "0.0.0.0:8000"]