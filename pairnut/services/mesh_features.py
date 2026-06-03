"""3D mesh import, feature extraction, and similarity scoring."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
import shutil
import struct
from typing import Iterable

from ..database import get_meshes_dir, repositories


MESH_FEATURE_VERSION = "mesh-basic-v1"
SUPPORTED_MESH_SUFFIXES = {".stl", ".obj", ".ply"}


@dataclass(frozen=True)
class MeshData:
    vertices: list[tuple[float, float, float]]
    faces: list[tuple[int, int, int]]


@dataclass(frozen=True)
class MeshFeature:
    dimensions_vector: list[float]
    shape_vector: list[float]


@dataclass(frozen=True)
class WalnutMeshSimilarity:
    score: float


def _safe_path_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._") or "walnut"


def _serialize_vector(values: Iterable[float]) -> str:
    return json.dumps([round(float(value), 8) for value in values], separators=(",", ":"))


def _deserialize_vector(value: str) -> list[float]:
    return [float(item) for item in json.loads(value)]


def _triangulate(indices: list[int]) -> list[tuple[int, int, int]]:
    if len(indices) < 3:
        return []
    first = indices[0]
    return [(first, indices[i], indices[i + 1]) for i in range(1, len(indices) - 1)]


def _parse_obj(path: Path) -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        if parts[0] == "v" and len(parts) >= 4:
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif parts[0] == "f" and len(parts) >= 4:
            indices: list[int] = []
            for raw_index in parts[1:]:
                value = raw_index.split("/", 1)[0]
                index = int(value)
                indices.append(index - 1 if index > 0 else len(vertices) + index)
            faces.extend(_triangulate(indices))
    return MeshData(vertices=vertices, faces=faces)


def _parse_ascii_stl(text: str) -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    current: list[int] = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 4 and parts[0].lower() == "vertex":
            vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            current.append(len(vertices) - 1)
            if len(current) == 3:
                faces.append((current[0], current[1], current[2]))
                current = []
    return MeshData(vertices=vertices, faces=faces)


def _parse_binary_stl(data: bytes) -> MeshData:
    if len(data) < 84:
        return MeshData(vertices=[], faces=[])
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_size = 84 + (triangle_count * 50)
    if len(data) < expected_size:
        raise ValueError("STL 文件不完整。")
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int]] = []
    offset = 84
    for _ in range(triangle_count):
        offset += 12
        face_indices: list[int] = []
        for _vertex in range(3):
            vertex = struct.unpack_from("<fff", data, offset)
            vertices.append((float(vertex[0]), float(vertex[1]), float(vertex[2])))
            face_indices.append(len(vertices) - 1)
            offset += 12
        faces.append((face_indices[0], face_indices[1], face_indices[2]))
        offset += 2
    return MeshData(vertices=vertices, faces=faces)


def _parse_stl(path: Path) -> MeshData:
    data = path.read_bytes()
    if data[:5].lower() == b"solid":
        parsed = _parse_ascii_stl(data.decode("utf-8", errors="ignore"))
        if parsed.vertices:
            return parsed
    return _parse_binary_stl(data)


def _parse_ply(path: Path) -> MeshData:
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "ply":
        raise ValueError("PLY 文件头不正确。")
    vertex_count = 0
    face_count = 0
    header_end = -1
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "format binary_little_endian 1.0" or stripped == "format binary_big_endian 1.0":
            raise ValueError("暂不支持二进制 PLY，请导出 ASCII PLY。")
        if stripped.startswith("element vertex "):
            vertex_count = int(stripped.rsplit(" ", 1)[1])
        elif stripped.startswith("element face "):
            face_count = int(stripped.rsplit(" ", 1)[1])
        elif stripped == "end_header":
            header_end = index
            break
    if header_end < 0:
        raise ValueError("PLY 文件缺少 end_header。")

    body = lines[header_end + 1 :]
    vertices: list[tuple[float, float, float]] = []
    for line in body[:vertex_count]:
        parts = line.strip().split()
        if len(parts) < 3:
            raise ValueError("PLY 顶点数据不完整。")
        vertices.append((float(parts[0]), float(parts[1]), float(parts[2])))

    faces: list[tuple[int, int, int]] = []
    face_lines = body[vertex_count : vertex_count + face_count]
    for line in face_lines:
        parts = line.strip().split()
        if not parts:
            continue
        count = int(parts[0])
        indices = [int(item) for item in parts[1 : 1 + count]]
        faces.extend(_triangulate(indices))
    return MeshData(vertices=vertices, faces=faces)


def load_mesh(path: str | Path) -> MeshData:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_MESH_SUFFIXES:
        raise ValueError("仅支持 STL、OBJ、PLY 3D 模型文件。")
    if suffix == ".obj":
        mesh = _parse_obj(source)
    elif suffix == ".stl":
        mesh = _parse_stl(source)
    else:
        mesh = _parse_ply(source)
    if len(mesh.vertices) < 4:
        raise ValueError("模型顶点数量太少，无法提取稳定特征。")
    return mesh


def _sub(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _cross(left: tuple[float, float, float], right: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        (left[1] * right[2]) - (left[2] * right[1]),
        (left[2] * right[0]) - (left[0] * right[2]),
        (left[0] * right[1]) - (left[1] * right[0]),
    )


def _dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return (left[0] * right[0]) + (left[1] * right[1]) + (left[2] * right[2])


def _norm(value: tuple[float, float, float]) -> float:
    return math.sqrt(_dot(value, value))


def extract_mesh_features(path: str | Path) -> MeshFeature:
    mesh = load_mesh(path)
    xs = [vertex[0] for vertex in mesh.vertices]
    ys = [vertex[1] for vertex in mesh.vertices]
    zs = [vertex[2] for vertex in mesh.vertices]
    dimensions = sorted(
        [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)],
        reverse=True,
    )
    bbox_volume = dimensions[0] * dimensions[1] * dimensions[2]

    surface_area = 0.0
    signed_volume = 0.0
    for face in mesh.faces:
        a, b, c = mesh.vertices[face[0]], mesh.vertices[face[1]], mesh.vertices[face[2]]
        surface_area += _norm(_cross(_sub(b, a), _sub(c, a))) / 2.0
        signed_volume += _dot(a, _cross(b, c)) / 6.0
    volume = abs(signed_volume)

    centroid = (sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs))
    radii = [_norm(_sub(vertex, centroid)) for vertex in mesh.vertices]
    mean_radius = sum(radii) / len(radii)
    radial_std = math.sqrt(sum((radius - mean_radius) ** 2 for radius in radii) / len(radii)) if radii else 0.0
    radial_cv = radial_std / mean_radius if mean_radius > 0 else 0.0

    compactness = volume / bbox_volume if bbox_volume > 0 else 0.0
    sphericity = ((math.pi ** (1.0 / 3.0)) * ((6.0 * volume) ** (2.0 / 3.0)) / surface_area) if volume > 0 and surface_area > 0 else 0.0
    aspect_1 = dimensions[1] / dimensions[0] if dimensions[0] > 0 else 0.0
    aspect_2 = dimensions[2] / dimensions[0] if dimensions[0] > 0 else 0.0

    return MeshFeature(
        dimensions_vector=dimensions,
        shape_vector=[
            bbox_volume,
            volume,
            surface_area,
            compactness,
            sphericity,
            radial_cv,
            aspect_1,
            aspect_2,
        ],
    )


def store_mesh_features(mesh_id: int, mesh_path: str | Path) -> int:
    feature = extract_mesh_features(mesh_path)
    return store_mesh_feature(mesh_id, feature)


def store_mesh_feature(mesh_id: int, feature: MeshFeature) -> int:
    return repositories.upsert_walnut_mesh_feature(
        mesh_id=mesh_id,
        feature_version=MESH_FEATURE_VERSION,
        dimensions_vector=_serialize_vector(feature.dimensions_vector),
        shape_vector=_serialize_vector(feature.shape_vector),
    )


def import_walnut_mesh(walnut_id: int, file_path: str | Path) -> int:
    source = Path(file_path)
    if source.suffix.lower() not in SUPPORTED_MESH_SUFFIXES:
        raise ValueError("仅支持 STL、OBJ、PLY 3D 模型文件。")
    if not source.exists() or not source.is_file():
        raise ValueError("模型文件不存在。")

    walnut = repositories.get_walnut(walnut_id)
    if walnut is None:
        raise ValueError("核桃不存在。")

    feature = extract_mesh_features(source)
    meshes_root = get_meshes_dir()
    relative_path = Path(f"{walnut_id}-{_safe_path_part(walnut['serial_no'])}") / f"source{source.suffix.lower()}"
    target = meshes_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    previous = repositories.get_walnut_mesh(walnut_id)
    shutil.copy2(source, target)
    mesh_id = repositories.upsert_walnut_mesh(walnut_id, source.name, relative_path.as_posix())
    store_mesh_feature(mesh_id, feature)
    if previous:
        old_path = meshes_root / previous["stored_path"]
        if old_path != target and old_path.exists():
            old_path.unlink()
    return mesh_id


def delete_walnut_mesh(walnut_id: int) -> bool:
    mesh = repositories.get_walnut_mesh(walnut_id)
    if mesh is None:
        return False
    mesh_path = get_meshes_dir() / mesh["stored_path"]
    if mesh_path.exists():
        mesh_path.unlink()
    repositories.delete_walnut_mesh(walnut_id)
    return True


def _value_similarity(left: float, right: float) -> float:
    denominator = max(abs(left), abs(right), 1e-9)
    return max(0.0, 1.0 - (abs(left - right) / denominator))


def _vector_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    length = min(len(left), len(right))
    return sum(_value_similarity(left[index], right[index]) for index in range(length)) / length


def feature_similarity(left: dict, right: dict) -> float:
    left_dimensions = _deserialize_vector(left["dimensions_vector"])
    right_dimensions = _deserialize_vector(right["dimensions_vector"])
    left_shape = _deserialize_vector(left["shape_vector"])
    right_shape = _deserialize_vector(right["shape_vector"])

    dimension_score = _vector_similarity(left_dimensions, right_dimensions)
    volume_score = _vector_similarity(left_shape[:3], right_shape[:3])
    shape_score = _vector_similarity(left_shape[3:], right_shape[3:])
    return ((dimension_score * 0.45) + (volume_score * 0.25) + (shape_score * 0.30)) * 100.0


def walnut_mesh_similarity(base_walnut_id: int, candidate_walnut_id: int) -> WalnutMeshSimilarity | None:
    base_features = repositories.list_walnut_mesh_features(base_walnut_id, MESH_FEATURE_VERSION)
    candidate_features = repositories.list_walnut_mesh_features(candidate_walnut_id, MESH_FEATURE_VERSION)
    if not base_features or not candidate_features:
        return None
    return WalnutMeshSimilarity(score=feature_similarity(base_features[0], candidate_features[0]))
