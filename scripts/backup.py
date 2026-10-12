"""Back up Curiculy: the whole database (verified), each family, and the work samples.

    python scripts/backup.py --evidence-dir /data/evidence --dest /backups --keep 14

Each run writes ``<dest>/<UTC timestamp>/``:

- ``curiculy.dump``: the whole database (``pg_dump`` custom format). It is
  restored into a scratch database and every table counted before the run is
  called good.
- ``families/<family>.json.gz``: one file per family, so one family can be
  restored without touching anyone else (``scripts/restore_family.py``).
- ``manifest.json``: what was written and checked.

Work samples are mirrored into ``<dest>/evidence/``: stored files never
change, so only new ones are copied. Only the newest ``--keep`` snapshots are
kept.

Needs ``DATABASE_OWNER_URL`` (the dump, the scratch restore, the list of
families) and ``DATABASE_URL`` (each family's export runs as the app's role,
scoped by row-level security). ``pg_dump`` and ``pg_restore`` must be the
server's major version; the Docker image's ``backup`` stage installs them.

Exit status is non-zero if anything fails, so a scheduler can alert on it.
Restoring: docs/4-operations/backups-and-restore.md.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.config import reveal_secret, settings  # noqa: E402
from app.db import DEMO_TENANT_PREFIX, open_family_session, owner_engine  # noqa: E402
from app.services.family_data import export_family, write_export  # noqa: E402

SNAPSHOT_FORMAT = "%Y-%m-%dT%H%M%SZ"
DUMP_NAME = "curiculy.dump"


def libpq_url(url: str) -> str:
    """postgresql+psycopg://… (SQLAlchemy) -> postgresql://… (pg_dump, psycopg)."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def owner_url() -> str:
    return libpq_url(reveal_secret(settings.database_owner_url))


def _with_database(url: str, database: str) -> str:
    from urllib.parse import urlsplit, urlunsplit

    return urlunsplit(urlsplit(url)._replace(path=f"/{database}"))


def table_counts(url: str) -> dict[str, int]:
    """Rows in every table (owner role: sees every family)."""
    with psycopg.connect(url) as conn:
        names = [
            row[0]
            for row in conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1"
            )
        ]
        return {
            name: conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))).fetchone()[0]
            for name in names
        }


def dump_database(url: str, path: Path) -> None:
    subprocess.run(
        ["pg_dump", "--format=custom", "--no-password", "--file", str(path), "--dbname", url],
        check=True,
        capture_output=True,
    )


def verify_dump(url: str, path: Path, stamp: str) -> dict[str, int]:
    """Restore the dump into a scratch database, count every table, then drop it."""
    scratch = f"curiculy_verify_{stamp.lower().replace('-', '')}"
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(scratch)))
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(scratch)))
    try:
        subprocess.run(
            [
                "pg_restore",
                "--no-owner",
                "--no-privileges",
                "--exit-on-error",
                "--no-password",
                "--dbname",
                _with_database(url, scratch),
                str(path),
            ],
            check=True,
            capture_output=True,
        )
        return table_counts(_with_database(url, scratch))
    finally:
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(scratch)))


def family_ids() -> list[str]:
    """Every real family (demo households are throwaway and skipped)."""
    with owner_engine().connect() as conn:
        return conn.execute(
            text("SELECT tenant_id FROM households WHERE tenant_id NOT LIKE :demo ORDER BY tenant_id"),
            {"demo": f"{DEMO_TENANT_PREFIX}%"},
        ).scalars().all()


def export_families(folder: Path) -> list[dict]:
    exported = []
    for tenant_id in family_ids():
        session = open_family_session(tenant_id)
        try:
            export = export_family(session)
        finally:
            session.close()
        path = folder / f"{tenant_id}.json.gz"
        write_export(path, export)
        rows = sum(len(rows) for rows in export["tables"].values())
        exported.append({"family": tenant_id, "rows": rows, "bytes": path.stat().st_size})
    return exported


def mirror_evidence(source: Path, destination: Path) -> int:
    """Copy evidence files that are not in the mirror yet; return how many."""
    if not source.is_dir():
        return 0
    copied = 0
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        if target.exists() and target.stat().st_size == path.stat().st_size:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied


def _is_snapshot(name: str) -> bool:
    try:
        datetime.strptime(name, SNAPSHOT_FORMAT)
    except ValueError:
        return False
    return True


def prune_snapshots(dest: Path, keep: int) -> list[str]:
    snapshots = sorted(path for path in dest.iterdir() if path.is_dir() and _is_snapshot(path.name))
    removed = []
    for path in snapshots[: max(0, len(snapshots) - keep)]:
        shutil.rmtree(path)
        removed.append(path.name)
    return removed


def run_backup(
    dest: Path,
    *,
    evidence_dir: Path | None = None,
    keep: int = 14,
    now: datetime | None = None,
) -> dict:
    """Make one snapshot and return its manifest. Raises if any step fails."""
    stamp = (now or datetime.now(timezone.utc)).strftime(SNAPSHOT_FORMAT)
    snapshot = dest / stamp
    snapshot.mkdir(parents=True, exist_ok=False)
    url = owner_url()
    live_tables = set(table_counts(url))

    dump = snapshot / DUMP_NAME
    dump_database(url, dump)
    restored = verify_dump(url, dump, stamp)
    missing = sorted(live_tables - set(restored))
    if missing:
        raise RuntimeError(f"The restored copy is missing tables: {', '.join(missing)}")

    families = export_families(snapshot / "families")
    manifest = {
        "created_at": stamp,
        "database": {"file": DUMP_NAME, "bytes": dump.stat().st_size, "restored_rows": restored},
        "families": families,
        "evidence_files_copied": mirror_evidence(evidence_dir, dest / "evidence") if evidence_dir else 0,
    }
    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    manifest["pruned"] = prune_snapshots(dest, keep)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--keep", type=int, default=14, help="snapshots to keep (default 14)")
    args = parser.parse_args(argv)
    try:
        manifest = run_backup(args.dest, evidence_dir=args.evidence_dir, keep=args.keep)
    except (RuntimeError, OSError, subprocess.CalledProcessError, psycopg.Error) as error:
        detail = getattr(error, "stderr", b"") or b""
        if isinstance(detail, bytes):
            detail = detail.decode(errors="replace")
        print(f"error: backup failed: {error} {detail}".strip(), file=sys.stderr)
        return 1
    rows = sum(manifest["database"]["restored_rows"].values())
    print(
        f"Snapshot {manifest['created_at']}: database checked ({rows} rows restored), "
        f"{len(manifest['families'])} family file(s), "
        f"{manifest['evidence_files_copied']} new evidence file(s), "
        f"pruned {len(manifest['pruned'])} old snapshot(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
