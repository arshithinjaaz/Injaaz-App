#!/usr/bin/env python3
"""Snapshot the app database to a file, and restore a chosen snapshot.

Backups are gzipped JSON under ./backups (gitignored). Same format works for
local SQLite and live Postgres.

Usage (from repo root):

  ./venv/bin/python scripts/db_snapshot.py backup
  ./venv/bin/python scripts/db_snapshot.py backup --live
  ./venv/bin/python scripts/db_snapshot.py backup --interval 30
  ./venv/bin/python scripts/db_snapshot.py list
  ./venv/bin/python scripts/db_snapshot.py restore backups/kynvera-local-20260908-1630.json.gz --write

`--live` uses LIVE_DATABASE_URL (Render External URL). Do not put that URL in git.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sqlite3
import sys
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FORMAT = "injaaz-db-snapshot-v1"
DEFAULT_KEEP = 48
SKIP_TABLES = {"sqlite_sequence", "sqlite_stat1"}


def backup_dir() -> Path:
    override = (os.environ.get("DB_BACKUPS_DIR") or "").strip()
    if override:
        path = Path(override)
    else:
        generated = (os.environ.get("GENERATED_DIR") or "").strip()
        path = Path(generated) / "db_backups" if generated else ROOT / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _stamp() -> str:
    return _utcnow().strftime("%Y%m%d-%H%M")


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def jsonable(value):
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, (dict, list)):
        return value
    return str(value)


def resolve_source(*, live: bool, database_url: str | None, sqlite_path: Path | None) -> tuple[str, str]:
    """Return ('sqlite', path) or ('postgresql', url)."""
    if live:
        url = normalize_url(os.environ.get("LIVE_DATABASE_URL") or os.environ.get("DATABASE_URL") or "")
        if not url or "sqlite" in url.lower():
            raise SystemExit(
                "Set LIVE_DATABASE_URL to the Render External Database URL, then re-run with --live."
            )
        return "postgresql", url
    url = normalize_url(database_url or os.environ.get("DATABASE_URL") or "")
    if url and "sqlite" not in url.lower() and url.startswith("postgresql"):
        return "postgresql", url
    path = sqlite_path or ROOT / "injaaz.db"
    return "sqlite", str(path)


def sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY 1"
    ).fetchall()
    return [r[0] for r in rows if r[0] not in SKIP_TABLES]


def sqlite_fk_order(conn: sqlite3.Connection, tables: list[str]) -> list[str]:
    wanted = set(tables)
    deps = {t: set() for t in tables}
    for table in tables:
        for row in conn.execute(f'PRAGMA foreign_key_list("{table}")'):
            parent = row[2]
            if parent in wanted and parent != table:
                deps[table].add(parent)
    remaining = list(tables)
    ordered: list[str] = []
    while remaining:
        ready = [t for t in remaining if not deps[t]]
        if not ready:
            ordered.extend(remaining)
            break
        for t in ready:
            ordered.append(t)
            remaining.remove(t)
            for child in remaining:
                deps[child].discard(t)
    return ordered


def dump_sqlite(path: str) -> dict:
    if not Path(path).is_file():
        raise SystemExit(f"SQLite not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    tables = sqlite_fk_order(conn, sqlite_tables(conn))
    payload_tables = {}
    for table in tables:
        rows = [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"').fetchall()]
        payload_tables[table] = [{k: jsonable(v) for k, v in row.items()} for row in rows]
        print(f"backup {table}: {len(rows)}")
    conn.close()
    return payload_tables


def dump_postgres(url: str) -> dict:
    from sqlalchemy import create_engine, inspect, text

    url = normalize_url(url)
    if "render.com" in url.lower() and "sslmode=" not in url.lower():
        url += ("&" if "?" in url else "?") + "sslmode=require"
    engine = create_engine(url)
    payload_tables = {}
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        tables = [t for t in inspect(engine).get_table_names() if t not in SKIP_TABLES]
        print(f"backup tables={len(tables)}")
        for table in tables:
            rows = conn.execute(text(f"SELECT * FROM {_quote_ident(table)}")).mappings().all()
            payload_tables[table] = [{k: jsonable(v) for k, v in dict(r).items()} for r in rows]
            if rows:
                print(f"backup {table}: {len(rows)}")
    return payload_tables


def write_snapshot(payload_tables: dict, *, kind: str, source: str, dest: Path) -> Path:
    payload = {
        "format": FORMAT,
        "exported_at": _utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_kind": kind,
        "source": source,
        "tables": payload_tables,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(dest, "wt", encoding="utf-8") as f:
        json.dump(payload, f, default=str)
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")
    return dest


def create_backup(*, live: bool = False, database_url: str | None = None, sqlite_path: Path | None = None) -> Path:
    kind, source = resolve_source(live=live, database_url=database_url, sqlite_path=sqlite_path)
    label = "live" if live or "render.com" in source.lower() else "local"
    dest = backup_dir() / f"kynvera-{label}-{_stamp()}.json.gz"
    print(f"source {kind}: {source if kind == 'sqlite' else '[url redacted]'}")
    tables = dump_sqlite(source) if kind == "sqlite" else dump_postgres(source)
    return write_snapshot(payload_tables=tables, kind=kind, source=source if kind == "sqlite" else kind, dest=dest)


def prune_backups(keep: int) -> None:
    files = sorted(backup_dir().glob("kynvera-*.json.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in files[keep:]:
        stale.unlink()
        print(f"pruned {stale.name}")


def list_backups() -> list[Path]:
    files = sorted(backup_dir().glob("kynvera-*.json.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        print(f"No snapshots in {backup_dir()}")
        return []
    for path in files:
        stamp = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"{stamp}  {path.stat().st_size:8d}  {path}")
    return files


def load_snapshot(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"Snapshot not found: {path}")
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, dict) or "tables" not in payload:
        raise SystemExit(f"Not a database snapshot: {path}")
    return payload


def _parse_dt(val):
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=None) if val.tzinfo else val
    s = str(val).strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return s


def restore_sqlite(payload: dict, sqlite_path: str) -> None:
    conn = sqlite3.connect(sqlite_path)
    try:
        existing = sqlite_tables(conn)
        table_order = [t for t in sqlite_fk_order(conn, existing) if t in (payload.get("tables") or {})]
        missing = [t for t in (payload.get("tables") or {}) if t not in existing]
        for t in missing:
            print(f"skip missing table {t}")
        conn.execute("PRAGMA foreign_keys=OFF")
        for table in reversed(table_order):
            n = conn.execute(f'DELETE FROM "{table}"').rowcount
            print(f"cleared {table}: {n}")
        for table in table_order:
            rows = payload["tables"].get(table) or []
            if not rows:
                print(f"restore {table}: 0")
                continue
            cols = [r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')]
            n = 0
            for raw in rows:
                data = {k: raw.get(k) for k in cols if k in raw}
                if not data:
                    continue
                names = list(data.keys())
                placeholders = ", ".join("?" for _ in names)
                conn.execute(
                    f'INSERT OR REPLACE INTO "{table}" ({", ".join(names)}) VALUES ({placeholders})',
                    [data[c] for c in names],
                )
                n += 1
            print(f"restore {table}: {n}")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.commit()
    finally:
        conn.close()


def restore_postgres(payload: dict, database_url: str) -> None:
    from scripts.push_sqlite_to_postgres import plan_or_push

    tables = payload.get("tables") or {}
    payload = dict(payload)
    payload["tables"] = tables
    plan_or_push(payload, database_url, replace=True, write=True)


def restore_backup(
    path: Path,
    *,
    live: bool = False,
    database_url: str | None = None,
    sqlite_path: Path | None = None,
    write: bool = False,
) -> None:
    payload = load_snapshot(path)
    kind, source = resolve_source(live=live, database_url=database_url, sqlite_path=sqlite_path)
    print(f"snapshot {path.name}  tables={len(payload.get('tables') or {})}")
    print(f"target {kind}: {source if kind == 'sqlite' else '[url redacted]'}")
    if not write:
        print("Dry run. Re-run with --write to restore this file.")
        for name, rows in (payload.get("tables") or {}).items():
            print(f"  {name}: {len(rows or [])}")
        return
    if kind == "sqlite":
        restore_sqlite(payload, source)
    else:
        restore_postgres(payload, source)
    print("Done.")


def run_interval(minutes: int, *, live: bool, keep: int, database_url: str | None) -> None:
    print(f"snapshot every {minutes} minutes → {backup_dir()}")
    while True:
        try:
            create_backup(live=live, database_url=database_url)
            prune_backups(keep)
        except Exception as exc:
            print(f"BACKUP_FAILED: {type(exc).__name__}: {exc}")
        print(f"next snapshot in {minutes} minutes")
        time.sleep(max(1, minutes) * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backup or restore the app database to a file")
    sub = parser.add_subparsers(dest="command", required=True)

    b = sub.add_parser("backup", help="Write a snapshot under backups/")
    b.add_argument("--live", action="store_true", help="Use LIVE_DATABASE_URL (Render)")
    b.add_argument("--database-url", help="Postgres URL (else DATABASE_URL or local SQLite)")
    b.add_argument("--sqlite", type=Path, help="SQLite file (default ./injaaz.db)")
    b.add_argument("--interval", type=int, metavar="MIN", help="Repeat every MIN minutes (e.g. 30)")
    b.add_argument("--keep", type=int, default=DEFAULT_KEEP, help="Snapshots to keep (default 48)")

    r = sub.add_parser("restore", help="Restore one snapshot file into the target database")
    r.add_argument("file", type=Path, help="Path to a kynvera-*.json.gz snapshot")
    r.add_argument("--live", action="store_true", help="Restore into LIVE_DATABASE_URL")
    r.add_argument("--database-url", help="Postgres URL")
    r.add_argument("--sqlite", type=Path, help="SQLite file to restore into")
    r.add_argument("--write", action="store_true", help="Required. Without it, only prints a plan.")

    sub.add_parser("list", help="List snapshots in backups/")

    args = parser.parse_args()
    if args.command == "list":
        list_backups()
        return
    if args.command == "backup":
        if args.interval:
            run_interval(
                args.interval,
                live=args.live,
                keep=args.keep,
                database_url=args.database_url,
            )
            return
        create_backup(live=args.live, database_url=args.database_url, sqlite_path=args.sqlite)
        prune_backups(args.keep)
        return
    restore_backup(
        args.file,
        live=args.live,
        database_url=args.database_url,
        sqlite_path=args.sqlite,
        write=args.write,
    )


if __name__ == "__main__":
    main()
