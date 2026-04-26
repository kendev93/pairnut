"""SQLite connection helpers."""

from __future__ import annotations

import os
import sys
import sqlite3
from contextlib import contextmanager
from pathlib import Path


APP_DIR_NAME = "PairNut"


def get_data_dir() -> Path:
    """Return the writable application data directory."""
    override = os.environ.get("PAIRNUT_DATA_DIR")
    if override:
        data_dir = Path(override)
    elif getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            data_dir = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
        elif sys.platform == "win32":
            root = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
            data_dir = Path(root) / APP_DIR_NAME
        else:
            data_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_DIR_NAME
    else:
        data_dir = Path(__file__).resolve().parents[2] / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    """Return the SQLite file path."""
    return get_data_dir() / "pairnut.db"


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
