"""Round-trip tests for scripts/db_snapshot.py (SQLite file snapshots)."""
from __future__ import annotations

import gzip
import json
import sqlite3
from pathlib import Path

from scripts.db_snapshot import create_backup, load_snapshot, restore_backup


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE people (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE notes (
            id INTEGER PRIMARY KEY,
            person_id INTEGER REFERENCES people(id),
            body TEXT
        );
        INSERT INTO people (id, name) VALUES (1, 'Ada'), (2, 'Grace');
        INSERT INTO notes (id, person_id, body) VALUES (1, 1, 'first'), (2, 2, 'second');
        """
    )
    conn.commit()
    conn.close()


def test_backup_and_restore_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKUPS_DIR", str(tmp_path / "snaps"))
    src = tmp_path / "app.db"
    _make_db(src)

    dest = create_backup(sqlite_path=src)
    assert dest.is_file()
    payload = load_snapshot(dest)
    assert payload["format"] == "injaaz-db-snapshot-v1"
    assert payload["tables"]["people"][0]["name"] == "Ada"
    assert len(payload["tables"]["notes"]) == 2

    conn = sqlite3.connect(str(src))
    conn.execute("DELETE FROM notes")
    conn.execute("DELETE FROM people")
    conn.execute("INSERT INTO people (id, name) VALUES (9, 'gone')")
    conn.commit()
    conn.close()

    restore_backup(dest, sqlite_path=src, write=True)
    conn = sqlite3.connect(str(src))
    people = list(conn.execute("SELECT id, name FROM people ORDER BY id"))
    notes = list(conn.execute("SELECT id, person_id, body FROM notes ORDER BY id"))
    conn.close()
    assert people == [(1, "Ada"), (2, "Grace")]
    assert notes == [(1, 1, "first"), (2, 2, "second")]


def test_restore_without_write_does_not_change_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKUPS_DIR", str(tmp_path / "snaps"))
    src = tmp_path / "app.db"
    _make_db(src)
    dest = create_backup(sqlite_path=src)
    conn = sqlite3.connect(str(src))
    conn.execute("UPDATE people SET name='changed' WHERE id=1")
    conn.commit()
    conn.close()

    restore_backup(dest, sqlite_path=src, write=False)
    conn = sqlite3.connect(str(src))
    name = conn.execute("SELECT name FROM people WHERE id=1").fetchone()[0]
    conn.close()
    assert name == "changed"


def test_snapshot_is_gzip_json(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_BACKUPS_DIR", str(tmp_path / "snaps"))
    src = tmp_path / "app.db"
    _make_db(src)
    dest = create_backup(sqlite_path=src)
    with gzip.open(dest, "rt", encoding="utf-8") as f:
        data = json.load(f)
    assert "people" in data["tables"]
    assert dest.name.startswith("kynvera-local-")
    assert dest.name.endswith(".json.gz")
