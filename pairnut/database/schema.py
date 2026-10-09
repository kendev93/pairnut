"""Database schema management."""

from __future__ import annotations

import logging

from .connection import db_connection

CURRENT_SCHEMA_VERSION = 1
ACTIVE_LOCK_INDEX_NAME = "idx_locked_pairs_active_pair"
_LOGGER = logging.getLogger(__name__)


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
    CREATE TABLE IF NOT EXISTS walnut_image_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_id INTEGER NOT NULL UNIQUE,
        feature_version TEXT NOT NULL,
        color_histogram TEXT NOT NULL,
        texture_vector TEXT NOT NULL,
        shape_vector TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (image_id) REFERENCES walnut_images(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS walnut_meshes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        walnut_id INTEGER NOT NULL UNIQUE,
        original_filename TEXT NOT NULL,
        stored_path TEXT NOT NULL,
        imported_at TEXT NOT NULL,
        FOREIGN KEY (walnut_id) REFERENCES walnuts(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS walnut_mesh_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mesh_id INTEGER NOT NULL UNIQUE,
        feature_version TEXT NOT NULL,
        dimensions_vector TEXT NOT NULL,
        shape_vector TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (mesh_id) REFERENCES walnut_meshes(id) ON DELETE CASCADE
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


def _has_active_pair_unique_index(cursor) -> bool:
    """True when a partial unique index already enforces one active lock per pair."""
    for row in cursor.execute("PRAGMA index_list('locked_pairs')").fetchall():
        if not (row["unique"] and row["partial"]):
            continue
        columns = {
            column["name"]
            for column in cursor.execute(f"PRAGMA index_info('{row['name']}')")
        }
        if columns == {"walnut_id_1", "walnut_id_2"}:
            return True
    return False


def _drop_stale_active_pair_index(cursor) -> int:
    """Drop the index name when it holds an outdated definition.

    Databases created before the partial index existed may still carry a unique
    index on ``(walnut_id_1, walnut_id_2, is_active)``, which blocks repeated
    lock/unlock cycles of the same pair.
    """
    row = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND name = ?",
        (ACTIVE_LOCK_INDEX_NAME,),
    ).fetchone()
    if row is None:
        return 0
    cursor.execute(f"DROP INDEX {ACTIVE_LOCK_INDEX_NAME}")
    return 1


def _deactivate_duplicate_active_pairs(cursor) -> int:
    """Deactivate duplicated active rows, keeping the earliest lock of each pair."""
    duplicates = cursor.execute(
        """
        SELECT walnut_id_1, walnut_id_2, MIN(id) AS keep_id
        FROM locked_pairs
        WHERE is_active = 1
        GROUP BY walnut_id_1, walnut_id_2
        HAVING COUNT(*) > 1
        """
    ).fetchall()
    deactivated = 0
    for duplicate in duplicates:
        cursor.execute(
            """
            UPDATE locked_pairs
            SET is_active = 0
            WHERE walnut_id_1 = ?
              AND walnut_id_2 = ?
              AND is_active = 1
              AND id <> ?
            """,
            (
                duplicate["walnut_id_1"],
                duplicate["walnut_id_2"],
                duplicate["keep_id"],
            ),
        )
        deactivated += cursor.rowcount
    return deactivated


def _ensure_locked_pairs_active_unique_index(conn) -> None:
    """Ensure at most one active lock per walnut pair; allow multiple inactive history rows.

    The previous index included ``is_active`` in the key, which forbade more than
    one unlocked history row for the same pair (lock → unlock → lock → unlock
    failed). The guard is created only when missing, so repeated application
    starts no longer rebuild it.
    """
    cursor = conn.cursor()
    if _has_active_pair_unique_index(cursor):
        return

    _drop_stale_active_pair_index(cursor)
    deactivated = _deactivate_duplicate_active_pairs(cursor)
    if deactivated:
        _LOGGER.warning(
            "已修复 %s 条重复的锁定记录，同一配对保留最早锁定的一条。", deactivated
        )
    cursor.execute(
        f"""
        CREATE UNIQUE INDEX {ACTIVE_LOCK_INDEX_NAME}
        ON locked_pairs (walnut_id_1, walnut_id_2)
        WHERE is_active = 1
        """
    )


def init_database() -> None:
    """Create the current schema and record its migration version."""
    with db_connection() as conn:
        current_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if current_version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"数据库版本 {current_version} 高于应用支持的版本 {CURRENT_SCHEMA_VERSION}。"
            )
        cursor = conn.cursor()
        for statement in SCHEMA_STATEMENTS:
            cursor.execute(statement)
        _ensure_locked_pairs_active_unique_index(conn)
        if current_version < CURRENT_SCHEMA_VERSION:
            conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
