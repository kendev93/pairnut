"""Database schema management."""

from __future__ import annotations

from .connection import db_connection


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS varieties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        code_prefix TEXT NOT NULL UNIQUE,
        tolerance_mm REAL NOT NULL DEFAULT 1.0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS walnuts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        variety_id INTEGER NOT NULL,
        serial_mode TEXT NOT NULL CHECK(serial_mode IN ('manual', 'auto')),
        serial_no TEXT NOT NULL UNIQUE,
        edge_mm REAL NOT NULL,
        belly_mm REAL NOT NULL,
        height_mm REAL NOT NULL,
        weight_g REAL NOT NULL,
        defect_level TEXT NOT NULL DEFAULT 'none'
            CHECK(defect_level IN ('none', 'light', 'medium', 'heavy')),
        notes TEXT,
        is_locked INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (variety_id) REFERENCES varieties(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS locked_pairs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        variety_id INTEGER NOT NULL,
        walnut_id_1 INTEGER NOT NULL,
        walnut_id_2 INTEGER NOT NULL,
        locked_at TEXT NOT NULL,
        unlocked_at TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (variety_id) REFERENCES varieties(id) ON DELETE CASCADE,
        FOREIGN KEY (walnut_id_1) REFERENCES walnuts(id) ON DELETE CASCADE,
        FOREIGN KEY (walnut_id_2) REFERENCES walnuts(id) ON DELETE CASCADE,
        CHECK (walnut_id_1 < walnut_id_2)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pair_blacklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        variety_id INTEGER NOT NULL,
        walnut_id_1 INTEGER NOT NULL,
        walnut_id_2 INTEGER NOT NULL,
        reason TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (variety_id) REFERENCES varieties(id) ON DELETE CASCADE,
        FOREIGN KEY (walnut_id_1) REFERENCES walnuts(id) ON DELETE CASCADE,
        FOREIGN KEY (walnut_id_2) REFERENCES walnuts(id) ON DELETE CASCADE,
        CHECK (walnut_id_1 < walnut_id_2)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS walnut_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        walnut_id INTEGER NOT NULL,
        face_no INTEGER NOT NULL CHECK(face_no BETWEEN 1 AND 6),
        original_filename TEXT NOT NULL,
        stored_path TEXT NOT NULL,
        imported_at TEXT NOT NULL,
        FOREIGN KEY (walnut_id) REFERENCES walnuts(id) ON DELETE CASCADE,
        UNIQUE (walnut_id, face_no)
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_pair_blacklist_pair
    ON pair_blacklist (walnut_id_1, walnut_id_2)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_walnuts_variety
    ON walnuts (variety_id, is_locked, serial_no)
    """,
]


def _ensure_locked_pairs_active_unique_index(conn) -> None:
    """Ensure at most one active lock per walnut pair; allow multiple inactive history rows.

    The previous index included ``is_active`` in the key, which forbade more than one
    unlocked history row for the same pair (lock → unlock → lock → unlock failed).
    """
    cursor = conn.cursor()
    cursor.execute("DROP INDEX IF EXISTS idx_locked_pairs_active_pair")
    cursor.execute(
        """
        CREATE UNIQUE INDEX idx_locked_pairs_active_pair
        ON locked_pairs (walnut_id_1, walnut_id_2)
        WHERE is_active = 1
        """
    )


def init_database() -> None:
    """Create the current schema."""
    with db_connection() as conn:
        cursor = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        _ensure_locked_pairs_active_unique_index(conn)
