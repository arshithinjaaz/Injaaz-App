#!/usr/bin/env python3
"""Copy selected tables from local SQLite into a Postgres DATABASE_URL (Render).

Local is SQLite (`injaaz.db`). Live is Postgres. This script exports rows, then
upserts them on the target. It does not go through Render MCP (those queries
are read-only).

Usage (from repo root):

  # See what would be copied (no write)
  ./venv/bin/python scripts/push_sqlite_to_postgres.py export --group hr
  LIVE_DATABASE_URL='postgresql://USER:PASS@HOST/DB?sslmode=require' \\
    ./venv/bin/python scripts/push_sqlite_to_postgres.py plan --group hr

  # Write to live (destructive if --replace)
  LIVE_DATABASE_URL='postgresql://USER:PASS@HOST/DB?sslmode=require' \\
    ./venv/bin/python scripts/push_sqlite_to_postgres.py push --group hr --write-production

  # Wipe those tables on live first, then copy
  LIVE_DATABASE_URL='...' \\
    ./venv/bin/python scripts/push_sqlite_to_postgres.py push --group hr --write-production --replace

Do not put the live URL in `.env`. Pass LIVE_DATABASE_URL (or --database-url)
for this shell only. Users / sessions are skipped unless --include-auth.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SQLITE = ROOT / "injaaz.db"
DEFAULT_EXPORT = ROOT / "tmp" / "sqlite_to_postgres_export.json"

SKIP_ALWAYS = {
    "sqlite_sequence",
    "sqlite_stat1",
    "alembic_version",
}
AUTH_TABLES = {"users", "sessions", "admin_edit_otp"}
SESSION_TABLES = {"sessions"}
NOISY_TABLES = {
    "audit_logs",
    "email_logs",
    "database_backups",
    "notifications",
    "push_device_tokens",
    "assistant_pending_actions",
}

PRESETS: dict[str, tuple[str, ...]] = {
    "hr": (
        "manpower_trades",
        "manpower_projects",
        "leave_employees",
        "hiring_candidates",
        "hiring_documents",
        "hiring_offer_letters",
        "manpower_vacancies",
        "leave_logs",
        "leave_monthly_usage",
        "leave_plans",
    ),
    "tickets": (
        "ticket_projects",
        "ticket_properties",
        "ticket_zones",
        "ticket_sub_zones",
        "ticket_base_units",
        "ticket_title_templates",
        "ticket_vendors",
        "ticket_vendor_technicians",
        "ticket_service_groups",
        "ticket_fault_categories",
        "ticket_fault_codes",
        "ticket_priorities",
        "ticket_hold_reasons",
        "ticket_cancel_reasons",
        "ticket_supervisor_teams",
        "ticket_project_supervisors",
        "ticket_project_team_members",
        "ticket_project_vendors",
        "tickets",
        "ticket_assets",
        "ticket_triage_logs",
        "ticket_notes",
        "ticket_images",
        "ticket_materials",
        "ticket_manpower",
        "ticket_email_intakes",
    ),
    "procurement": (
        "proc_properties",
        "proc_suppliers",
        "proc_catalog_items",
        "proc_stock",
        "proc_email_templates",
        "proc_purchase_requests",
        "proc_purchase_lines",
        "proc_purchase_documents",
        "proc_goods_receipts",
        "proc_goods_receipt_lines",
        "proc_movements",
    ),
    "bd": (
        "bd_projects",
        "bd_followups",
        "bd_contacts",
        "bd_activities",
        "quotations",
        "quotation_items",
        "quotation_attachments",
    ),
    "fm": (
        "fm_assets",
        "fm_asset_predictions",
        "fm_floor_plans",
        "fm_portfolio_forecasts",
    ),
    "qhse": (
        "qhsi_trainings",
        "qhse_compliance_imports",
        "qhse_staff_compliance_rows",
    ),
    "files": ("files_folders", "files_items", "files_drive_connections"),
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def sqlite_tables(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY 1"
    ).fetchall()
    return [r[0] for r in rows]


def sqlite_fk_graph(conn: sqlite3.Connection, tables: list[str]) -> dict[str, set[str]]:
    wanted = set(tables)
    deps: dict[str, set[str]] = {t: set() for t in tables}
    for table in tables:
        for row in conn.execute(f'PRAGMA foreign_key_list("{table}")'):
            parent = row[2]
            if parent in wanted and parent != table:
                deps[table].add(parent)
    return deps


def topological_order(tables: list[str], deps: dict[str, set[str]]) -> list[str]:
    remaining = list(tables)
    ordered: list[str] = []
    deps = {t: set(deps.get(t, set())) for t in remaining}
    while remaining:
        ready = [t for t in remaining if not deps[t]]
        if not ready:
            # Cycle: append remaining in original order so the push can still run
            ordered.extend(remaining)
            break
        for t in ready:
            ordered.append(t)
            remaining.remove(t)
            for child in remaining:
                deps[child].discard(t)
    return ordered


def resolve_tables(
    conn: sqlite3.Connection,
    *,
    group: str | None,
    extra: list[str],
    include_auth: bool,
    include_noisy: bool,
    include_sessions: bool = False,
) -> list[str]:
    available = sqlite_tables(conn)
    available_set = set(available)
    if group == "all":
        chosen = list(available)
    elif group:
        if group not in PRESETS:
            raise SystemExit(
                f"Unknown group {group!r}. Choose one of: {', '.join(sorted(PRESETS))}, all"
            )
        chosen = [t for t in PRESETS[group] if t in available_set]
        missing = [t for t in PRESETS[group] if t not in available_set]
        for t in missing:
            print(f"skip missing local table {t}")
    else:
        chosen = []
    for t in extra:
        if t not in available_set:
            raise SystemExit(f"Local SQLite has no table {t!r}")
        if t not in chosen:
            chosen.append(t)
    if not chosen:
        raise SystemExit("No tables selected. Pass --group hr (or tickets, procurement, all) or --table NAME")

    filtered = []
    for t in chosen:
        if t in SKIP_ALWAYS:
            continue
        if t in SESSION_TABLES and not include_sessions:
            print(f"skip {t} (laptop sessions are not copied to live)")
            continue
        if t in AUTH_TABLES and not include_auth:
            print(f"skip {t} (pass --include-auth to copy users)")
            continue
        if t in NOISY_TABLES and not include_noisy and group == "all":
            print(f"skip {t} (pass --include-noisy to copy logs/backups)")
            continue
        filtered.append(t)
    return topological_order(filtered, sqlite_fk_graph(conn, filtered))


def export_sqlite(sqlite_path: Path, out_path: Path, tables: list[str]) -> dict:
    if not sqlite_path.is_file():
        raise SystemExit(f"SQLite not found: {sqlite_path}")
    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row
    payload = {
        "exported_at": _utcnow_iso(),
        "source": str(sqlite_path),
        "tables": {},
    }
    for table in tables:
        rows = [dict(r) for r in conn.execute(f'SELECT * FROM "{table}"').fetchall()]
        payload["tables"][table] = rows
        print(f"export {table}: {len(rows)}")
    conn.close()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, default=str), encoding="utf-8")
    print(f"wrote {out_path} ({out_path.stat().st_size} bytes)")
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


def _parse_date(val):
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()[:10]
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return val


def _parse_bool(val):
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return bool(val)
    s = str(val).strip().lower()
    if s in ("1", "true", "t", "yes", "y"):
        return True
    if s in ("0", "false", "f", "no", "n"):
        return False
    return val


def _parse_json(val):
    if val is None or val == "":
        return None
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, (bytes, bytearray)):
        val = val.decode("utf-8", errors="replace")
    if isinstance(val, str):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val
    return val


def _pg_type_name(col_type) -> str:
    return str(getattr(col_type, "__visit_name__", col_type) or "").lower()


def coerce_value(val, col_type):
    from psycopg2.extras import Json

    name = _pg_type_name(col_type)
    raw = str(col_type).lower()
    if "bool" in name or "bool" in raw:
        return _parse_bool(val)
    if "datetime" in name or "timestamp" in raw:
        return _parse_dt(val)
    if name == "date" or raw == "date":
        return _parse_date(val)
    if "json" in name or "json" in raw:
        parsed = _parse_json(val)
        if isinstance(parsed, (dict, list)):
            return Json(parsed)
        return parsed
    if isinstance(val, (dict, list)):
        return Json(val)
    return val


def _target_url(cli_url: str | None) -> str:
    url = normalize_url(
        cli_url
        or os.environ.get("LIVE_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    )
    if not url or "sqlite" in url.lower():
        raise SystemExit(
            "Set LIVE_DATABASE_URL to the Render Postgres External URL, e.g.\n"
            "  export LIVE_DATABASE_URL='postgresql://USER:PASS@HOST/DB?sslmode=require'\n"
            "Do not put this in .env. Then re-run the push command."
        )
    return url


def _ensure_varchar_capacity(conn, table: str, col_types: dict, rows: list[dict], col_names: list[str]) -> None:
    from sqlalchemy import text

    for name in col_names:
        col_type = col_types[name]
        length = getattr(col_type, "length", None)
        if not length:
            continue
        max_len = 0
        for raw in rows:
            val = raw.get(name)
            if isinstance(val, str):
                max_len = max(max_len, len(val))
        if max_len > int(length):
            new_len = max(max_len, int(length) * 2)
            conn.execute(
                text(
                    f"ALTER TABLE {_quote_ident(table)} "
                    f"ALTER COLUMN {_quote_ident(name)} TYPE VARCHAR({new_len})"
                )
            )
            print(f"widened {table}.{name} VARCHAR({length}) -> VARCHAR({new_len})")


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def plan_or_push(payload: dict, database_url: str, *, replace: bool, write: bool) -> None:
    from sqlalchemy import create_engine, inspect, text

    url = normalize_url(database_url)
    if "render.com" in url.lower() and "sslmode=" not in url.lower():
        url += ("&" if "?" in url else "?") + "sslmode=require"
    engine = create_engine(url)
    insp = inspect(engine)
    table_order = list(payload.get("tables", {}).keys())
    existing = set(insp.get_table_names())
    missing = [t for t in table_order if t not in existing]
    if missing:
        print("skip tables missing on live (deploy first if you need them): " + ", ".join(missing))
        table_order = [t for t in table_order if t in existing]
        payload = dict(payload)
        payload["tables"] = {t: payload.get("tables", {}).get(t) or [] for t in table_order}

    print("Postgres connection OK")
    with engine.connect() as conn:
        for table in table_order:
            local_n = len(payload["tables"].get(table) or [])
            live_n = conn.execute(text(f"SELECT COUNT(*) FROM {_quote_ident(table)}")).scalar()
            print(f"plan {table}: local={local_n} live={live_n}")

    if not write:
        print("Dry run only. Re-run with `push --write-production` to copy rows.")
        return

    with engine.begin() as conn:
        if replace:
            # Live sessions (and similar) still point at users even when we skip copying them.
            for extra in ("sessions", "email_otps", "push_device_tokens"):
                if extra in existing and extra not in table_order:
                    n = conn.execute(text(f"DELETE FROM {_quote_ident(extra)}")).rowcount
                    print(f"cleared {extra}: {n}")
            for table in reversed(table_order):
                n = conn.execute(text(f"DELETE FROM {_quote_ident(table)}")).rowcount
                print(f"cleared {table}: {n}")

        fk_cache: dict[str, set[int]] = {}

        def load_ids(ref_table: str) -> set[int]:
            if ref_table not in fk_cache:
                if ref_table not in existing:
                    fk_cache[ref_table] = set()
                else:
                    rows = conn.execute(text(f"SELECT id FROM {_quote_ident(ref_table)}")).fetchall()
                    fk_cache[ref_table] = {int(r[0]) for r in rows if r[0] is not None}
            return fk_cache[ref_table]

        for table in table_order:
            rows = payload.get("tables", {}).get(table) or []
            pg_cols = insp.get_columns(table)
            col_types = {c["name"]: c["type"] for c in pg_cols}
            col_names = [c["name"] for c in pg_cols]
            fks = insp.get_foreign_keys(table)
            nullable = {c["name"]: c.get("nullable", True) for c in pg_cols}
            if not rows:
                print(f"push {table}: 0 (skip)")
                continue
            _ensure_varchar_capacity(conn, table, col_types, rows, col_names)
            upserted = 0
            skipped = 0
            cleared_fk = 0
            for raw in rows:
                data = {}
                for name in col_names:
                    if name not in raw:
                        continue
                    data[name] = coerce_value(raw.get(name), col_types[name])
                if "id" not in data:
                    skipped += 1
                    continue
                drop_row = False
                for fk in fks:
                    ref_table = fk.get("referred_table")
                    constrained = fk.get("constrained_columns") or []
                    referred = fk.get("referred_columns") or []
                    if not ref_table or referred != ["id"]:
                        continue
                    ids = load_ids(ref_table)
                    for col in constrained:
                        val = data.get(col)
                        if val is None:
                            continue
                        try:
                            ival = int(val)
                        except (TypeError, ValueError):
                            if nullable.get(col, True):
                                data[col] = None
                                cleared_fk += 1
                            else:
                                drop_row = True
                            continue
                        if ival not in ids:
                            if nullable.get(col, True):
                                data[col] = None
                                cleared_fk += 1
                            else:
                                drop_row = True
                if drop_row:
                    skipped += 1
                    continue
                names = list(data.keys())
                placeholders = ", ".join(f":{c}" for c in names)
                insert_cols = ", ".join(_quote_ident(c) for c in names)
                updates = ", ".join(
                    f"{_quote_ident(c)} = EXCLUDED.{_quote_ident(c)}" for c in names if c != "id"
                )
                sql = (
                    f"INSERT INTO {_quote_ident(table)} ({insert_cols}) "
                    f"VALUES ({placeholders}) ON CONFLICT (id) DO UPDATE SET {updates}"
                )
                conn.execute(text(sql), data)
                upserted += 1
            max_id = conn.execute(
                text(f"SELECT COALESCE(MAX(id), 0) FROM {_quote_ident(table)}")
            ).scalar()
            try:
                conn.execute(
                    text("SELECT setval(pg_get_serial_sequence(:tbl, 'id'), :val, true)"),
                    {"tbl": table, "val": int(max_id or 1)},
                )
            except Exception:
                pass
            fk_cache[table] = load_ids(table) | {
                int(r["id"]) for r in rows if r.get("id") is not None
            }
            extra = []
            if cleared_fk:
                extra.append(f"cleared {cleared_fk} orphan FKs")
            if skipped:
                extra.append(f"skipped {skipped}")
            suffix = f" ({'; '.join(extra)})" if extra else ""
            print(f"push {table}: {upserted}{suffix}")

    print("Done.")


def _connect_sqlite(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise SystemExit(f"SQLite not found: {path}")
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy local SQLite tables into Render Postgres"
    )
    parser.add_argument("command", choices=("export", "plan", "push"))
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE)
    parser.add_argument("--file", type=Path, default=DEFAULT_EXPORT)
    parser.add_argument(
        "--group",
        choices=(*sorted(PRESETS), "all"),
        help="Preset table set. hr = leave/hiring/manpower (usual first copy).",
    )
    parser.add_argument("--table", action="append", default=[], help="Extra table name (repeatable)")
    parser.add_argument("--include-auth", action="store_true", help="Also copy users so FKs match")
    parser.add_argument("--include-sessions", action="store_true", help="Also copy sessions (usually skip)")
    parser.add_argument("--include-noisy", action="store_true", help="With --group all, also copy logs")
    parser.add_argument("--database-url", help="Postgres URL (else LIVE_DATABASE_URL)")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete existing rows in the selected live tables before upsert",
    )
    parser.add_argument(
        "--write-production",
        action="store_true",
        help="Required for push. Without it, push is a dry-run plan.",
    )
    args = parser.parse_args()

    conn = _connect_sqlite(args.sqlite)
    tables = resolve_tables(
        conn,
        group=args.group,
        extra=args.table,
        include_auth=args.include_auth,
        include_noisy=args.include_noisy,
        include_sessions=args.include_sessions,
    )
    conn.close()
    print("tables:", ", ".join(tables))

    if args.command == "export":
        export_sqlite(args.sqlite, args.file, tables)
        return

    if not args.file.is_file() or args.command in ("plan", "push"):
        export_sqlite(args.sqlite, args.file, tables)

    payload = json.loads(args.file.read_text(encoding="utf-8"))
    # Keep only selected tables, in FK order
    payload["tables"] = {t: payload.get("tables", {}).get(t) or [] for t in tables}
    url = _target_url(args.database_url)
    write = args.command == "push" and args.write_production
    if args.command == "push" and not args.write_production:
        print("Refusing to write: pass --write-production to copy into live Postgres.")
    plan_or_push(payload, url, replace=args.replace, write=write)


if __name__ == "__main__":
    main()
