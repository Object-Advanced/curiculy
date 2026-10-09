"""Report foreign-key problems in Curiculy's SQLite files. Read-only.

SQLite only enforces foreign keys when a connection turns them on, and until
now Curiculy never did. Before enforcing them, run this against each data
directory to see:

* declared foreign keys that point at a table missing from that file
  (left over from older model versions), and
* rows whose foreign key points at a parent row that no longer exists.

    docker compose exec api python scripts/check_foreign_keys.py --data-dir /data

Files are opened read-only (mode=ro); nothing is changed. Exit status is 1
when any problem is found.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows} - {"sqlite_sequence"}


def check_file(path: Path) -> list[str]:
    """Problems in one database file, as human-readable lines."""
    problems: list[str] = []
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as error:
        return [f"could not open: {error}"]
    try:
        tables = _tables(conn)
        for table in sorted(tables):
            for row in conn.execute(f'PRAGMA foreign_key_list("{table}")'):
                parent = row[2]
                if parent not in tables:
                    problems.append(f"{table}.{row[3]} references missing table {parent}")
        for table, rowid, parent, _fk in conn.execute("PRAGMA foreign_key_check"):
            problems.append(f"{table} row {rowid} points at a missing {parent} row")
    except sqlite3.Error as error:
        problems.append(f"check failed: {error}")
    finally:
        conn.close()
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("/data"))
    args = parser.parse_args(argv)

    files = sorted(args.data_dir.glob("*.db"))
    if not files:
        print(f"No .db files in {args.data_dir}")
        return 0
    found = False
    for path in files:
        problems = check_file(path)
        print(f"{path.name}: {'OK' if not problems else f'{len(problems)} problem(s)'}")
        for line in problems:
            print(f"  - {line}")
        found = found or bool(problems)
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
