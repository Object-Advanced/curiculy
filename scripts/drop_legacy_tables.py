#!/usr/bin/env python3
"""Operator tool: DROP empty leftover scheduled_work / evidence_captures tables.

Not run at application startup. Default is dry-run. Use --apply to DROP tables
whose COUNT(*) is 0. Never deletes rows. Non-empty tables are left untouched.
"""

from app.services.legacy_table_drop import main

if __name__ == "__main__":
    raise SystemExit(main())
