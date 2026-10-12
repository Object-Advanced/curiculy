"""Restore one family from a nightly family copy, without touching anyone else.

    python scripts/restore_family.py /backups/<snapshot>/families/<family>.json.gz
    python scripts/restore_family.py <file> --yes      # skip the question

Replaces that family's rows with the copy, in one transaction, working as the
app's role so row-level security keeps every other family out of reach. Sign-ins
and work-sample files aren't touched (they're restored separately; see
docs/4-operations/backups-and-restore.md).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import open_family_session, owner_engine  # noqa: E402
from app.services.family_data import advance_sequences, read_export, restore_family  # noqa: E402


def restore_from_file(path: Path) -> tuple[str, int]:
    export = read_export(path)
    tenant_id = str(export.get("tenant_id", ""))
    session = open_family_session(tenant_id)
    try:
        restored = restore_family(session, export)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    advance_sequences(owner_engine())
    return tenant_id, restored


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path)
    parser.add_argument("--yes", action="store_true", help="don't ask before replacing")
    args = parser.parse_args(argv)
    export = read_export(args.file)
    tenant_id = export.get("tenant_id")
    if not args.yes:
        answer = input(f"Replace every row of family {tenant_id} with {args.file.name}? [y/N] ")
        if answer.strip().lower() not in {"y", "yes"}:
            print("Nothing changed.")
            return 1
    tenant_id, restored = restore_from_file(args.file)
    print(f"Restored family {tenant_id}: {restored} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
