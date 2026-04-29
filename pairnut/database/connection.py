"""SQLite connection helpers."""

from __future__ import annotations

import os
import shutil
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path


APP_DIR_NAME = "PairNut"


def _default_user_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    if sys.platform == "win32":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / APP_DIR_NAME
    if sys.platform.startswith("linux"):
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return root / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME.lower()}"


def _legacy_documents_data_dir() -> Path:
    return Path.home() / "Documents" / APP_DIR_NAME


def _legacy_project_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


def _copy_missing_data_files(source_dir: Path, target_dir: Path) -> None:
    for source_path in source_dir.rglob("*"):
        relative_path = source_path.relative_to(source_dir)
        target_path = target_dir / relative_path
        if source_path.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
        elif not target_path.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)


def _migrate_legacy_data(data_dir: Path) -> None:
    """Copy data from earlier default locations once."""
    if (data_dir / "pairnut.db").exists():
        return
    for legacy_dir in (_legacy_documents_data_dir(), _legacy_project_data_dir()):
        if legacy_dir.resolve() == data_dir.resolve() or not (legacy_dir / "pairnut.db").exists():
            continue
        _copy_missing_data_files(legacy_dir, data_dir)
        return


def get_data_dir() -> Path:
    """Return the writable application data directory."""
    override = os.environ.get("PAIRNUT_DATA_DIR")
    if override:
        data_dir = Path(override)
    else:
        data_dir = _default_user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    if not override:
        _migrate_legacy_data(data_dir)
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
