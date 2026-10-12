# Monitoring

## Is it up?
- **`https://curiculy.com/api/health`** returns `{"status":"ok","database":"ok",...}` when the app can reach Postgres. `docker ps` also shows `curiculy_db … (healthy)` (`pg_isready` every 5 seconds).
- **`docker ps`** shows `curiculy_api … (healthy)`. Docker runs the same check every 30 seconds.

## Logs
- `docker logs --since 1h curiculy_api`: every request, with the visitor's real address, method, path and status.
- **What's normal:**
  - **Internet scanners probing for WordPress and similar get 404s.** They're harmless.
  - **401 / 422** from a stale app on someone's device means they should refresh.

## The log check (`/home/objadv/curiculy-ops/log_check.py`)
A read-only report on the last 72 hours. It never changes anything. It covers:
- container health and restarts
- request counts by status
- **kid sign-ins:** family-code lookups and PIN sign-ins, with 401 = wrong code or PIN and 429 = too many tries
- parents opening the family code
- **rate-limited** clients
- **refused uploads** (413 too big, 415 wrong type)
- **server errors** (5xx) and Python tracebacks
- the top 404 paths
- the **latest backup snapshots** and their check results

**Run it any time:**
```
python3 /home/objadv/curiculy-ops/log_check.py
```

It writes `/home/objadv/curiculy-ops/reports/log-check-<date>.txt`.

**Scheduled:** a one-time run on **2026-10-13 at 13:00 UTC** (`--once` removes its own cron line afterwards). The baseline report is `log-check-2026-10-10.txt`.

## Open items
- **No outside uptime monitor and no alerts.** If the server goes down at night, nobody is told.
- **No error tracking** that groups crashes.
- **Planned for the public launch** (Phase 8): an uptime check and status page, error tracking, metrics and alerts. A simple free uptime monitor on `/api/health` is worth adding sooner.
