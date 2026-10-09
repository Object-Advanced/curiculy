"""Back up Curiculy's databases and evidence. Standard library only.

    python scripts/backup.py --data-dir /data --evidence-dir /data/evidence --dest /backups

Each run writes ``<dest>/<UTC timestamp>/`` with a copy of every ``*.db`` in
the data directory, made with SQLite's online backup API (consistent even
while the app is writing; a plain file copy is not, with WAL), checked with
``PRAGMA integrity_check``, and listed in ``manifest.json``. Evidence photos
and PDFs are mirrored into ``<dest>/evidence/``: stored files never change,
so only new ones are copied. Only the newest ``--keep`` snapshots are kept.

Exit status is non-zero if any database fails to copy or check, so a
scheduler can alert on it.

Restore (with the app stopped): copy the snapshot's .db files back into the
data directory and the evidence mirror back into the evidence directory. See
README "Backups and restore".
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_FORMAT = "%Y-%m-%dT%H%M%SZ"


def backup_database(source: Path, destination: Path) -> str:
    """Copy one SQLite file with the backup API; return its integrity_check result."""
    src = sqlite3.connect(source)
    try:
        dst = sqlite3.connect(destination)
        try:
            src.backup(dst)
            return str(dst.execute("PRAGMA integrity_check").fetchone()[0])
        finally:
            dst.close()
    finally:
        src.close()


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


def prune_snapshots(dest: Path, keep: int) -> list[str]:
    snapshots = sorted(
        path for path in dest.iterdir() if path.is_dir() and _is_snapshot(path.name)
    )
    removed = []
    for path in snapshots[: max(0, len(snapshots) - keep)]:
        shutil.rmtree(path)
        removed.append(path.name)
    return removed


def _is_snapshot(name: str) -> bool:
    try:
        datetime.strptime(name, SNAPSHOT_FORMAT)
    except ValueError:
        return False
    return True


def run_backup(
    data_dir: Path,
    dest: Path,
    *,
    evidence_dir: Path | None = None,
    keep: int = 14,
    now: datetime | None = None,
) -> dict:
    """Make one snapshot and return its manifest. Raises if a database fails."""
    stamp = (now or datetime.now(timezone.utc)).strftime(SNAPSHOT_FORMAT)
    snapshot = dest / stamp
    snapshot.mkdir(parents=True, exist_ok=False)
    databases = []
    failures = []
    for source in sorted(data_dir.glob("*.db")):
        target = snapshot / source.name
        try:
            check = backup_database(source, target)
        except sqlite3.Error as error:
            check = f"error: {error}"
        databases.append({"name": source.name, "bytes": target.stat().st_size if target.exists() else 0, "check": check})
        if check != "ok":
            failures.append(source.name)
    manifest = {
        "created_at": stamp,
        "databases": databases,
        "evidence_files_copied": mirror_evidence(evidence_dir, dest / "evidence") if evidence_dir else 0,
    }
    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    manifest["pruned"] = prune_snapshots(dest, keep)
    if failures:
        raise RuntimeError(f"Backup check failed for: {', '.join(failures)}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=Path("/data"))
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--keep", type=int, default=14, help="snapshots to keep (default 14)")
    args = parser.parse_args(argv)
    try:
        manifest = run_backup(args.data_dir, args.dest, evidence_dir=args.evidence_dir, keep=args.keep)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    names = ", ".join(row["name"] for row in manifest["databases"]) or "no databases"
    print(
        f"Snapshot {manifest['created_at']}: {names}; "
        f"{manifest['evidence_files_copied']} new evidence file(s); "
        f"pruned {len(manifest['pruned'])} old snapshot(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
