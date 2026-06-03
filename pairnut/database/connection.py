"""SQLite connection helpers."""

from __future__ import annotations

import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path


APP_DIR_NAME = "PairNut"


def _packaged_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    if sys.platform == "win32":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / APP_DIR_NAME
    if sys.platform.startswith("linux"):
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return root / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME.lower()}"


def _development_data_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "data"


def _default_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return _packaged_data_dir()
    return _development_data_dir()


def get_data_dir() -> Path:
    """Return the writable application data directory."""
    override = os.environ.get("PAIRNUT_DATA_DIR")
    if override:
        data_dir = Path(override)
    else:
        data_dir = _default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    """Return the SQLite file path."""
    return get_data_dir() / "pairnut.db"


def get_images_dir() -> Path:
    """Return the root directory for imported user images."""
    images_dir = get_data_dir() / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return images_dir


def get_models_dir() -> Path:
    """Return the root directory for optional user-downloaded models."""
    models_dir = get_data_dir() / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def get_meshes_dir() -> Path:
    """Return the root directory for imported walnut 3D meshes."""
    meshes_dir = get_data_dir() / "meshes"
    meshes_dir.mkdir(parents=True, exist_ok=True)
    return meshes_dir


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
