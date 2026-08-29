#!/bin/sh
set -e
mkdir -p /data/evidence
python -c "from app.db import init_databases; init_databases()"
exec uvicorn app.main:app --host 0.0.0.0 --port 80
