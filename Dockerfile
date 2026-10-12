# The React app (frontend/), built once and copied into the Python image.
FROM node:22.23.2-alpine AS frontend

WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# The app's CSS imports the shared design tokens from ../../static/css.
COPY static/css/tokens.css /src/static/css/tokens.css
RUN npm run build


FROM python:3.12-slim AS base

WORKDIR /app

# WeasyPrint needs Cairo/Pango at runtime to turn portfolio HTML into a PDF.
# Tesseract recovers daily schedules that are scanned images rather than text.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpangoft2-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        libharfbuzz0b \
        libffi8 \
        libwebp7 \
        shared-mime-info \
        fonts-dejavu-core \
        libgomp1 \
        libglib2.0-0 \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
COPY scripts ./scripts
COPY index.html .
COPY sw.js .
COPY static ./static
COPY --from=frontend /src/frontend/dist ./frontend/dist
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh && mkdir -p /data/evidence

ENV PYTHONUNBUFFERED=1
EXPOSE 80

ENTRYPOINT ["./entrypoint.sh"]


# Nightly backups need pg_dump and pg_restore matching the server's major
# version (18), which Debian's own packages don't have; use the PostgreSQL
# project's repository.
FROM base AS backup

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update && apt-get install -y --no-install-recommends postgresql-client-18 \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

ENTRYPOINT []


# The test image also has the Postgres client tools, so the backup script is
# tested end to end.
FROM backup AS dev

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY pytest.ini ruff.toml ./
COPY tests ./tests

ENTRYPOINT []
CMD ["pytest"]
