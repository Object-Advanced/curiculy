#!/bin/sh
set -e
mkdir -p /data/evidence
python -c "from app.config import validate_runtime_configuration; validate_runtime_configuration()"
python -c "from app.db import init_databases; init_databases()"
# Behind a proxy or tunnel, every request arrives from the proxy's address.
# --proxy-headers takes the visitor's address from X-Forwarded-For, but only
# when the request comes from FORWARDED_ALLOW_IPS, so a direct client cannot
# claim another address. Rate limits and access logs use the result.
exec uvicorn app.main:app --host 0.0.0.0 --port 80 \
    --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
