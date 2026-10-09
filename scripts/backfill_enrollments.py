#!/usr/bin/env python3
"""Operator tool: backfill Enrollment from assignment provenance.

Not run at application startup. Default is dry-run. Use --apply to insert.
"""

from app.services.enrollment_backfill import main

if __name__ == "__main__":
    raise SystemExit(main())
