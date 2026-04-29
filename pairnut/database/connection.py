"""SQLite connection helpers."""

from __future__ import annotations

import os
import shutil
import sqlite3
from contextlib import contextmanager
from pathlib import Path


APP_DIR_NAME = "PairNut"


def _default_user_data_dir() -> Path:
    documents_dir = Path.home() / "Documents"
    return documents_dir / APP_DIR_NAME


def _legacy_project_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


def _migrate_legacy_database(data_dir: Path) -> None:
    """Copy an early development database out of the project tree once."""
    legacy_db = _legacy_project_data_dir() / "pairnut.db"
    target_db = data_dir / "pairnut.db"
    if target_db.exists() or not legacy_db.exists():
        return
    shutil.copy2(legacy_db, target_db)


def get_data_dir() -> Path:
    """Return the writable application data directory."""
    override = os.environ.get("PAIRNUT_DATA_DIR")
    if override:
        data_dir = Path(override)
    else:
        data_dir = _default_user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    if not override:
        _migrate_legacy_database(data_dir)
    return data_dir


def get_db_path() -> Path:
    """Return the SQLite file path."""
    return get_data_dir() / "pairnut.db"


def get_images_dir() -> Path:
    """Return the root directory for imported user images."""
    images_dir = get_data_dir() / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return images_dir


@contextmanager
def db_connection():
    """Yield a SQLite connection with row access and FK support."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
