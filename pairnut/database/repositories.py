"""Repositories for SQLite persistence."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from .connection import db_connection

_VALID_SERIAL_MODES = {"manual", "auto"}
_VALID_DEFECT_LEVELS = {"none", "light", "medium", "heavy"}
_CODE_PREFIX_PATTERN = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")


def now_str() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def normalize_pair(walnut_id_1: int, walnut_id_2: int) -> tuple[int, int]:
    if walnut_id_1 == walnut_id_2:
        raise ValueError("A walnut cannot pair with itself.")
    return (walnut_id_1, walnut_id_2) if walnut_id_1 < walnut_id_2 else (walnut_id_2, walnut_id_1)


def row_to_dict(row) -> dict[str, Any] | None:
    return dict(row) if row else None


def _effective_walnut_dict(row) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    effective_lock = result.pop("effective_is_locked", None)
    if effective_lock is not None:
        result["is_locked"] = int(effective_lock)
    return result


def _effective_lock_projection(alias: str = "walnuts") -> str:
    return f"""
        CASE WHEN EXISTS (
            SELECT 1 FROM locked_pairs active_lock
            WHERE active_lock.is_active = 1
              AND (active_lock.walnut_id_1 = {alias}.id OR active_lock.walnut_id_2 = {alias}.id)
        ) THEN 1 ELSE 0 END AS effective_is_locked
    """


def validate_variety_input(name: str, code_prefix: str, tolerance_mm: float) -> tuple[str, str, float]:
    normalized_name = name.strip() if isinstance(name, str) else ""
    normalized_prefix = code_prefix.strip().upper() if isinstance(code_prefix, str) else ""
    if not normalized_name:
        raise ValueError("品种名称不能为空。")
    if not _CODE_PREFIX_PATTERN.fullmatch(normalized_prefix):
        raise ValueError("编号前缀只能包含字母、数字和连字符。")
    normalized_tolerance = _positive_finite_number(tolerance_mm, "统一偏差")
    return normalized_name, normalized_prefix, normalized_tolerance


def validate_walnut_input(data: dict[str, Any]) -> dict[str, Any]:
    serial_mode = data.get("serial_mode")
    if serial_mode not in _VALID_SERIAL_MODES:
        raise ValueError("编号方式无效。")

    serial_no = data.get("serial_no")
    if not isinstance(serial_no, str) or not serial_no.strip():
        raise ValueError("核桃编号不能为空。")

    defect_level = data.get("defect_level")
    if defect_level not in _VALID_DEFECT_LEVELS:
        raise ValueError("瑕疵等级无效。")

    return {
        "serial_mode": serial_mode,
        "serial_no": serial_no.strip(),
        "edge_mm": _positive_finite_number(data.get("edge_mm"), "边尺寸"),
        "belly_mm": _positive_finite_number(data.get("belly_mm"), "肚尺寸"),
        "height_mm": _positive_finite_number(data.get("height_mm"), "高度"),
        "weight_g": _positive_finite_number(data.get("weight_g"), "克重"),
        "defect_level": defect_level,
        "notes": data.get("notes"),
    }


def _positive_finite_number(value: Any, field_name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}必须是有效数字。") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{field_name}必须大于 0。")
    return number


def create_variety(name: str, code_prefix: str, tolerance_mm: float = 1.0) -> int:
    name, code_prefix, tolerance_mm = validate_variety_input(name, code_prefix, tolerance_mm)
    timestamp = now_str()
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO varieties (name, code_prefix, tolerance_mm, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, code_prefix, tolerance_mm, timestamp, timestamp),
        )
        return int(cursor.lastrowid)


def update_variety(variety_id: int, name: str, code_prefix: str, tolerance_mm: float) -> None:
    name, code_prefix, tolerance_mm = validate_variety_input(name, code_prefix, tolerance_mm)
    with db_connection() as conn:
        conn.execute(
            """
            UPDATE varieties
            SET name = ?, code_prefix = ?, tolerance_mm = ?, updated_at = ?
            WHERE id = ?
            """,
            (name, code_prefix, tolerance_mm, now_str(), variety_id),
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
    data = {**data, **validate_walnut_input(data)}
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
                data["serial_no"],
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
    data = {**data, **validate_walnut_input(data)}
    with db_connection() as conn:
        if conn.execute(
            """
            SELECT 1 FROM locked_pairs
            WHERE is_active = 1 AND (walnut_id_1 = ? OR walnut_id_2 = ?)
            LIMIT 1
            """,
            (walnut_id, walnut_id),
        ).fetchone():
            raise ValueError("已锁定的核桃不能编辑，请先解除锁定。")
        conn.execute(
            """
            UPDATE walnuts
            SET serial_mode = ?, serial_no = ?, edge_mm = ?, belly_mm = ?, height_mm = ?,
                weight_g = ?, defect_level = ?, notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                data["serial_mode"],
                data["serial_no"],
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
    if get_active_lock_for_walnut(walnut_id):
        raise ValueError("Cannot delete a locked walnut.")
    with db_connection() as conn:
        conn.execute("DELETE FROM walnuts WHERE id = ?", (walnut_id,))


def get_walnut(walnut_id: int) -> dict[str, Any] | None:
    with db_connection() as conn:
        row = conn.execute(
            f"SELECT walnuts.*, {_effective_lock_projection()} FROM walnuts WHERE id = ?",
            (walnut_id,),
        ).fetchone()
        return _effective_walnut_dict(row)


def get_walnut_by_serial(serial_no: str) -> dict[str, Any] | None:
    with db_connection() as conn:
        row = conn.execute(
            f"SELECT walnuts.*, {_effective_lock_projection()} FROM walnuts WHERE serial_no = ?",
            (serial_no.strip(),),
        ).fetchone()
        return _effective_walnut_dict(row)


def get_walnut_by_serial_and_variety(serial_no: str, variety_id: int) -> dict[str, Any] | None:
    with db_connection() as conn:
        row = conn.execute(
            f"SELECT walnuts.*, {_effective_lock_projection()} FROM walnuts WHERE serial_no = ? AND variety_id = ?",
            (serial_no.strip(), variety_id),
        ).fetchone()
        return _effective_walnut_dict(row)


def list_walnuts(variety_id: int | None = None, include_locked: bool = True) -> list[dict[str, Any]]:
    effective_lock_projection = _effective_lock_projection().strip()
    query = f"""
        SELECT walnuts.*,
               {effective_lock_projection},
               varieties.name AS variety_name, varieties.code_prefix, varieties.tolerance_mm
        FROM walnuts
        JOIN varieties ON varieties.id = walnuts.variety_id
    """
    params: list[Any] = []
    clauses: list[str] = []
    if variety_id is not None:
        clauses.append("walnuts.variety_id = ?")
        params.append(variety_id)
    if not include_locked:
        clauses.append(
            "NOT EXISTS ("
            "SELECT 1 FROM locked_pairs active_lock "
            "WHERE active_lock.is_active = 1 "
            "AND (active_lock.walnut_id_1 = walnuts.id OR active_lock.walnut_id_2 = walnuts.id)"
            ")"
        )
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY walnuts.serial_no COLLATE NOCASE"
    with db_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        walnuts: list[dict[str, Any]] = []
        for row in rows:
            walnut = _effective_walnut_dict(row)
            if walnut is not None:
                walnuts.append(walnut)
        return walnuts


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


def upsert_walnut_image_with_feature(
    walnut_id: int,
    face_no: int,
    original_filename: str,
    stored_path: str,
    feature_version: str,
    color_histogram: str,
    texture_vector: str,
    shape_vector: str,
) -> int:
    """Upsert an image and its feature row in one database transaction."""
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
        image = cursor.execute(
            "SELECT id FROM walnut_images WHERE walnut_id = ? AND face_no = ?",
            (walnut_id, face_no),
        ).fetchone()
        image_id = int(image["id"])
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
        return image_id


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


def list_walnut_images_for_variety(variety_id: int) -> dict[int, list[dict[str, Any]]]:
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT wi.*
            FROM walnut_images wi
            JOIN walnuts w ON w.id = wi.walnut_id
            WHERE w.variety_id = ?
            ORDER BY wi.walnut_id, wi.face_no
            """,
            (variety_id,),
        ).fetchall()
    result: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(int(row["walnut_id"]), []).append(dict(row))
    return result


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


def list_walnut_image_features_for_variety(
    variety_id: int,
    feature_version: str | None = None,
) -> dict[int, list[dict[str, Any]]]:
    params: list[Any] = [variety_id]
    version_clause = ""
    if feature_version is not None:
        version_clause = " AND wif.feature_version = ?"
        params.append(feature_version)
    with db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT wi.walnut_id, wi.face_no, wi.stored_path, wif.*
            FROM walnut_images wi
            JOIN walnuts w ON w.id = wi.walnut_id
            JOIN walnut_image_features wif ON wif.image_id = wi.id
            WHERE w.variety_id = ?{version_clause}
            ORDER BY wi.walnut_id, wi.face_no
            """,
            params,
        ).fetchall()
    result: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(int(row["walnut_id"]), []).append(dict(row))
    return result


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


def list_walnut_meshes_for_variety(variety_id: int) -> dict[int, dict[str, Any]]:
    with db_connection() as conn:
        rows = conn.execute(
            """
            SELECT wm.*
            FROM walnut_meshes wm
            JOIN walnuts w ON w.id = wm.walnut_id
            WHERE w.variety_id = ?
            ORDER BY wm.walnut_id
            """,
            (variety_id,),
        ).fetchall()
    return {int(row["walnut_id"]): dict(row) for row in rows}


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


def list_walnut_mesh_features_for_variety(
    variety_id: int,
    feature_version: str | None = None,
) -> dict[int, list[dict[str, Any]]]:
    params: list[Any] = [variety_id]
    version_clause = ""
    if feature_version is not None:
        version_clause = " AND wmf.feature_version = ?"
        params.append(feature_version)
    with db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT wm.walnut_id, wm.stored_path, wmf.*
            FROM walnut_meshes wm
            JOIN walnuts w ON w.id = wm.walnut_id
            JOIN walnut_mesh_features wmf ON wmf.mesh_id = wm.id
            WHERE w.variety_id = ?{version_clause}
            ORDER BY wm.walnut_id, wmf.created_at DESC
            """,
            params,
        ).fetchall()
    result: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(int(row["walnut_id"]), []).append(dict(row))
    return result


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
        _validate_pair_variety(cursor, variety_id, left, right)
        if cursor.execute(
            """
            SELECT 1 FROM pair_blacklist
            WHERE walnut_id_1 = ? AND walnut_id_2 = ?
            LIMIT 1
            """,
            (left, right),
        ).fetchone():
            raise ValueError("该配对已被拉黑，不能锁定。")
        pair_rows = cursor.execute(
            """
            SELECT w.edge_mm, w.belly_mm, w.height_mm, v.tolerance_mm
            FROM walnuts w
            JOIN varieties v ON v.id = w.variety_id
            WHERE w.id IN (?, ?)
            ORDER BY w.id
            """,
            (left, right),
        ).fetchall()
        tolerance_mm = float(pair_rows[0]["tolerance_mm"])
        if any(
            abs(pair_rows[0][field] - pair_rows[1][field]) > tolerance_mm
            for field in ("edge_mm", "belly_mm", "height_mm")
        ):
            raise ValueError("该配对超出品种统一偏差，不能锁定。")
        existing = cursor.execute(
            """
            SELECT id FROM locked_pairs
            WHERE walnut_id_1 = ? AND walnut_id_2 = ? AND is_active = 1
            """,
            (left, right),
        ).fetchone()
        if existing:
            return int(existing["id"])
        active_lock = cursor.execute(
            """
            SELECT id FROM locked_pairs
            WHERE is_active = 1
              AND (
                  walnut_id_1 IN (?, ?)
                  OR walnut_id_2 IN (?, ?)
              )
            LIMIT 1
            """,
            (left, right, left, right),
        ).fetchone()
        if active_lock:
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
        _validate_pair_variety(cursor, variety_id, left, right)
        if cursor.execute(
            """
            SELECT 1 FROM locked_pairs
            WHERE walnut_id_1 = ? AND walnut_id_2 = ? AND is_active = 1
            LIMIT 1
            """,
            (left, right),
        ).fetchone():
            raise ValueError("已锁定的配对不能拉黑，请先解除锁定。")
        normalized_reason = reason.strip() if isinstance(reason, str) and reason.strip() else None
        cursor.execute(
            """
            INSERT OR IGNORE INTO pair_blacklist (
                variety_id, walnut_id_1, walnut_id_2, reason, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (variety_id, left, right, normalized_reason, now_str()),
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


def _validate_pair_variety(cursor, variety_id: int, walnut_id_1: int, walnut_id_2: int) -> None:
    rows = cursor.execute(
        "SELECT id, variety_id FROM walnuts WHERE id IN (?, ?)",
        (walnut_id_1, walnut_id_2),
    ).fetchall()
    if len(rows) != 2 or any(row["variety_id"] != variety_id for row in rows):
        raise ValueError("Both walnuts must exist in the selected variety.")


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


def delete_blacklist_pair(blacklist_id: int) -> bool:
    with db_connection() as conn:
        cursor = conn.execute("DELETE FROM pair_blacklist WHERE id = ?", (blacklist_id,))
        return cursor.rowcount > 0


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
