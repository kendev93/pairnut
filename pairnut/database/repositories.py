"""Repositories for SQLite persistence."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from .connection import db_connection


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_pair(walnut_id_1: int, walnut_id_2: int) -> tuple[int, int]:
    if walnut_id_1 == walnut_id_2:
        raise ValueError("A walnut cannot pair with itself.")
    return (walnut_id_1, walnut_id_2) if walnut_id_1 < walnut_id_2 else (walnut_id_2, walnut_id_1)


def row_to_dict(row) -> dict[str, Any] | None:
    return dict(row) if row else None


def create_variety(name: str, code_prefix: str, tolerance_mm: float = 1.0) -> int:
    timestamp = now_str()
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO varieties (name, code_prefix, tolerance_mm, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name.strip(), code_prefix.strip().upper(), tolerance_mm, timestamp, timestamp),
        )
        return int(cursor.lastrowid)


def update_variety(variety_id: int, name: str, code_prefix: str, tolerance_mm: float) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE varieties
            SET name = ?, code_prefix = ?, tolerance_mm = ?, updated_at = ?
            WHERE id = ?
            """,
            (name.strip(), code_prefix.strip().upper(), tolerance_mm, now_str(), variety_id),
        )


def delete_variety(variety_id: int) -> None:
    with db_connection() as conn:
        conn.execute("DELETE FROM varieties WHERE id = ?", (variety_id,))


def get_variety(variety_id: int) -> dict[str, Any] | None:
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM varieties WHERE id = ?", (variety_id,)).fetchone()
        return row_to_dict(row)


def list_varieties() -> list[dict[str, Any]]:
    with db_connection() as conn:
        rows = conn.execute("SELECT * FROM varieties ORDER BY name COLLATE NOCASE").fetchall()
        return [dict(row) for row in rows]


def create_walnut(data: dict[str, Any]) -> int:
    timestamp = now_str()
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO walnuts (
                variety_id, serial_mode, serial_no, edge_mm, belly_mm, height_mm,
                weight_g, defect_level, notes, is_locked, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (
                data["variety_id"],
                data["serial_mode"],
                data["serial_no"].strip(),
                data["edge_mm"],
                data["belly_mm"],
                data["height_mm"],
                data["weight_g"],
                data["defect_level"],
                data.get("notes"),
                timestamp,
                timestamp,
            ),
        )
        return int(cursor.lastrowid)


def update_walnut(walnut_id: int, data: dict[str, Any]) -> None:
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE walnuts
            SET serial_mode = ?, serial_no = ?, edge_mm = ?, belly_mm = ?, height_mm = ?,
                weight_g = ?, defect_level = ?, notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                data["serial_mode"],
                data["serial_no"].strip(),
                data["edge_mm"],
                data["belly_mm"],
                data["height_mm"],
                data["weight_g"],
                data["defect_level"],
                data.get("notes"),
                now_str(),
                walnut_id,
            ),
        )


def delete_walnut(walnut_id: int) -> None:
    with db_connection() as conn:
        conn.execute("DELETE FROM walnuts WHERE id = ?", (walnut_id,))


def get_walnut(walnut_id: int) -> dict[str, Any] | None:
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM walnuts WHERE id = ?", (walnut_id,)).fetchone()
        return row_to_dict(row)


def get_walnut_by_serial(serial_no: str) -> dict[str, Any] | None:
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM walnuts WHERE serial_no = ?", (serial_no.strip(),)).fetchone()
        return row_to_dict(row)


def get_walnut_by_serial_and_variety(serial_no: str, variety_id: int) -> dict[str, Any] | None:
    with db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM walnuts WHERE serial_no = ? AND variety_id = ?",
            (serial_no.strip(), variety_id),
        ).fetchone()
        return row_to_dict(row)


def list_walnuts(variety_id: int | None = None, include_locked: bool = True) -> list[dict[str, Any]]:
    query = """
        SELECT walnuts.*, varieties.name AS variety_name, varieties.code_prefix, varieties.tolerance_mm
        FROM walnuts
        JOIN varieties ON varieties.id = walnuts.variety_id
    """
    params: list[Any] = []
    clauses: list[str] = []
    if variety_id is not None:
        clauses.append("walnuts.variety_id = ?")
        params.append(variety_id)
    if not include_locked:
        clauses.append("walnuts.is_locked = 0")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY walnuts.serial_no COLLATE NOCASE"
    with db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def upsert_walnut_image(walnut_id: int, face_no: int, original_filename: str, stored_path: str) -> int:
    timestamp = now_str()
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO walnut_images (walnut_id, face_no, original_filename, stored_path, imported_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(walnut_id, face_no) DO UPDATE SET
                original_filename = excluded.original_filename,
                stored_path = excluded.stored_path,
                imported_at = excluded.imported_at
            """,
            (walnut_id, face_no, original_filename, stored_path, timestamp),
        )
        row = cursor.execute(
            "SELECT id FROM walnut_images WHERE walnut_id = ? AND face_no = ?",
            (walnut_id, face_no),
        ).fetchone()
        return int(row["id"])


def upsert_walnut_image_feature(
    image_id: int,
    feature_version: str,
    color_histogram: str,
    texture_vector: str,
    shape_vector: str,
) -> int:
    timestamp = now_str()
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO walnut_image_features (
                image_id, feature_version, color_histogram, texture_vector, shape_vector, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(image_id) DO UPDATE SET
                feature_version = excluded.feature_version,
                color_histogram = excluded.color_histogram,
                texture_vector = excluded.texture_vector,
                shape_vector = excluded.shape_vector,
                created_at = excluded.created_at
            """,
            (image_id, feature_version, color_histogram, texture_vector, shape_vector, timestamp),
        )
        row = cursor.execute("SELECT id FROM walnut_image_features WHERE image_id = ?", (image_id,)).fetchone()
        return int(row["id"])


def list_walnut_images(walnut_id: int) -> list[dict[str, Any]]:
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM walnut_images
            WHERE walnut_id = ?
            ORDER BY face_no
            """,
            (walnut_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_walnut_image_features(walnut_id: int, feature_version: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = [walnut_id]
    version_clause = ""
    if feature_version is not None:
        version_clause = " AND wif.feature_version = ?"
        params.append(feature_version)
    with db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT wi.walnut_id, wi.face_no, wi.stored_path, wif.*
            FROM walnut_images wi
            JOIN walnut_image_features wif ON wif.image_id = wi.id
            WHERE wi.walnut_id = ?{version_clause}
            ORDER BY wi.face_no
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def get_walnut_image(walnut_id: int, face_no: int) -> dict[str, Any] | None:
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM walnut_images
            WHERE walnut_id = ? AND face_no = ?
            """,
            (walnut_id, face_no),
        ).fetchone()
        return row_to_dict(row)


def delete_walnut_image(walnut_id: int, face_no: int) -> None:
    with db_connection() as conn:
        conn.execute(
            "DELETE FROM walnut_images WHERE walnut_id = ? AND face_no = ?",
            (walnut_id, face_no),
        )


def upsert_walnut_mesh(walnut_id: int, original_filename: str, stored_path: str) -> int:
    timestamp = now_str()
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO walnut_meshes (walnut_id, original_filename, stored_path, imported_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(walnut_id) DO UPDATE SET
                original_filename = excluded.original_filename,
                stored_path = excluded.stored_path,
                imported_at = excluded.imported_at
            """,
            (walnut_id, original_filename, stored_path, timestamp),
        )
        row = cursor.execute("SELECT id FROM walnut_meshes WHERE walnut_id = ?", (walnut_id,)).fetchone()
        return int(row["id"])


def upsert_walnut_mesh_feature(
    mesh_id: int,
    feature_version: str,
    dimensions_vector: str,
    shape_vector: str,
) -> int:
    timestamp = now_str()
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO walnut_mesh_features (
                mesh_id, feature_version, dimensions_vector, shape_vector, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(mesh_id) DO UPDATE SET
                feature_version = excluded.feature_version,
                dimensions_vector = excluded.dimensions_vector,
                shape_vector = excluded.shape_vector,
                created_at = excluded.created_at
            """,
            (mesh_id, feature_version, dimensions_vector, shape_vector, timestamp),
        )
        row = cursor.execute("SELECT id FROM walnut_mesh_features WHERE mesh_id = ?", (mesh_id,)).fetchone()
        return int(row["id"])


def get_walnut_mesh(walnut_id: int) -> dict[str, Any] | None:
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM walnut_meshes
            WHERE walnut_id = ?
            """,
            (walnut_id,),
        ).fetchone()
        return row_to_dict(row)


def list_walnut_mesh_features(walnut_id: int, feature_version: str | None = None) -> list[dict[str, Any]]:
    params: list[Any] = [walnut_id]
    version_clause = ""
    if feature_version is not None:
        version_clause = " AND wmf.feature_version = ?"
        params.append(feature_version)
    with db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT wm.walnut_id, wm.stored_path, wmf.*
            FROM walnut_meshes wm
            JOIN walnut_mesh_features wmf ON wmf.mesh_id = wm.id
            WHERE wm.walnut_id = ?{version_clause}
            ORDER BY wmf.created_at DESC
            """,
            params,
        ).fetchall()
        return [dict(row) for row in rows]


def delete_walnut_mesh(walnut_id: int) -> None:
    with db_connection() as conn:
        conn.execute("DELETE FROM walnut_meshes WHERE walnut_id = ?", (walnut_id,))


def list_locked_pairs(variety_id: int | None = None, active_only: bool = True) -> list[dict[str, Any]]:
    query = """
        SELECT lp.*,
               w1.serial_no AS serial_no_1,
               w2.serial_no AS serial_no_2
        FROM locked_pairs lp
        JOIN walnuts w1 ON w1.id = lp.walnut_id_1
        JOIN walnuts w2 ON w2.id = lp.walnut_id_2
    """
    params: list[Any] = []
    clauses: list[str] = []
    if variety_id is not None:
        clauses.append("lp.variety_id = ?")
        params.append(variety_id)
    if active_only:
        clauses.append("lp.is_active = 1")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY lp.locked_at DESC"
    with db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def get_active_lock_for_walnut(walnut_id: int) -> dict[str, Any] | None:
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT * FROM locked_pairs
            WHERE is_active = 1 AND (walnut_id_1 = ? OR walnut_id_2 = ?)
            LIMIT 1
            """,
            (walnut_id, walnut_id),
        ).fetchone()
        return row_to_dict(row)


def lock_pair(variety_id: int, walnut_id_1: int, walnut_id_2: int) -> int:
    left, right = normalize_pair(walnut_id_1, walnut_id_2)
    timestamp = now_str()
    with db_connection() as conn:
        cursor = conn.cursor()
        existing = cursor.execute(
            """
            SELECT id FROM locked_pairs
            WHERE walnut_id_1 = ? AND walnut_id_2 = ? AND is_active = 1
            """,
            (left, right),
        ).fetchone()
        if existing:
            return int(existing["id"])
        if get_active_lock_for_walnut(left) or get_active_lock_for_walnut(right):
            raise ValueError("One of the walnuts is already locked.")
        cursor.execute(
            """
            INSERT INTO locked_pairs (
                variety_id, walnut_id_1, walnut_id_2, locked_at, unlocked_at, is_active
            )
            VALUES (?, ?, ?, ?, NULL, 1)
            """,
            (variety_id, left, right, timestamp),
        )
        cursor.execute("UPDATE walnuts SET is_locked = 1, updated_at = ? WHERE id IN (?, ?)", (timestamp, left, right))
        return int(cursor.lastrowid)


def unlock_pair(pair_id: int) -> None:
    with db_connection() as conn:
        row = conn.execute(
            "SELECT walnut_id_1, walnut_id_2 FROM locked_pairs WHERE id = ? AND is_active = 1",
            (pair_id,),
        ).fetchone()
        if not row:
            return
        timestamp = now_str()
        conn.execute(
            """
            UPDATE locked_pairs
            SET is_active = 0, unlocked_at = ?
            WHERE id = ?
            """,
            (timestamp, pair_id),
        )
        conn.execute(
            "UPDATE walnuts SET is_locked = 0, updated_at = ? WHERE id IN (?, ?)",
            (timestamp, row["walnut_id_1"], row["walnut_id_2"]),
        )


def create_blacklist_pair(variety_id: int, walnut_id_1: int, walnut_id_2: int, reason: str | None = None) -> int:
    left, right = normalize_pair(walnut_id_1, walnut_id_2)
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO pair_blacklist (
                variety_id, walnut_id_1, walnut_id_2, reason, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (variety_id, left, right, reason, now_str()),
        )
        if cursor.lastrowid:
            return int(cursor.lastrowid)
        row = cursor.execute(
            """
            SELECT id FROM pair_blacklist
            WHERE walnut_id_1 = ? AND walnut_id_2 = ?
            """,
            (left, right),
        ).fetchone()
        return int(row["id"])


def list_blacklist_pairs(variety_id: int | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT pb.*,
               w1.serial_no AS serial_no_1,
               w2.serial_no AS serial_no_2
        FROM pair_blacklist pb
        JOIN walnuts w1 ON w1.id = pb.walnut_id_1
        JOIN walnuts w2 ON w2.id = pb.walnut_id_2
    """
    params: list[Any] = []
    if variety_id is not None:
        query += " WHERE pb.variety_id = ?"
        params.append(variety_id)
    query += " ORDER BY pb.created_at DESC"
    with db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def is_pair_blacklisted(walnut_id_1: int, walnut_id_2: int) -> bool:
    left, right = normalize_pair(walnut_id_1, walnut_id_2)
    with db_connection() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM pair_blacklist
            WHERE walnut_id_1 = ? AND walnut_id_2 = ?
            """,
            (left, right),
        ).fetchone()
        return row is not None
