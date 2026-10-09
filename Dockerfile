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

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY index.html .
COPY sw.js .
COPY static ./static
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh && mkdir -p /data/evidence

ENV PYTHONUNBUFFERED=1
EXPOSE 80

ENTRYPOINT ["./entrypoint.sh"]


FROM base AS dev

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY pytest.ini .
COPY tests ./tests

ENTRYPOINT []
CMD ["pytest"]
