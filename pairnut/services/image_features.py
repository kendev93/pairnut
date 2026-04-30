"""OpenCV image feature extraction and similarity scoring."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Sequence

from ..database import repositories


OPENCV_FEATURE_VERSION = "opencv-v1"


@dataclass(frozen=True)
class ImageFeatures:
    color_histogram: list[float]
    texture_vector: list[float]
    shape_vector: list[float]


@dataclass(frozen=True)
class WalnutImageSimilarity:
    score: float
    matched_faces: int
    base_faces: int
    candidate_faces: int


def _normalize(values) -> list[float]:
    total = float(values.sum())
    if total <= 0:
        return [0.0 for _ in values.flatten()]
    return [float(value / total) for value in values.flatten()]


def extract_opencv_features(image_path: Path) -> ImageFeatures:
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("OpenCV 未安装，无法提取图片特征。") from exc

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"图片无法读取: {image_path}")

    image = cv2.resize(image, (256, 256), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    color_hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    color_histogram = _normalize(color_hist)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray_hist = cv2.calcHist([gray], [0], None, [32], [0, 256])
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    gradient = cv2.magnitude(sobel_x, sobel_y)
    gradient_hist = cv2.calcHist([np.uint8(np.clip(gradient, 0, 255))], [0], None, [16], [0, 256])
    texture_vector = (
        _normalize(gray_hist)
        + _normalize(gradient_hist)
        + [
            min(float(laplacian.var()) / 10000.0, 1.0),
            min(float(gradient.mean()) / 255.0, 1.0),
        ]
    )

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, threshold = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(threshold, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        shape_vector = [0.0, 0.0, 0.0, 0.0]
    else:
        contour = max(contours, key=cv2.contourArea)
        area = float(cv2.contourArea(contour))
        x, y, width, height = cv2.boundingRect(contour)
        perimeter = float(cv2.arcLength(contour, True))
        hull = cv2.convexHull(contour)
        hull_area = float(cv2.contourArea(hull))
        image_area = float(gray.shape[0] * gray.shape[1])
        shape_vector = [
            min(area / image_area, 1.0),
            min(width / max(height, 1), 3.0) / 3.0,
            min(area / max(width * height, 1), 1.0),
            min((4.0 * math.pi * area) / max(perimeter * perimeter, 1.0), 1.0),
            min(area / max(hull_area, 1.0), 1.0),
        ]

    return ImageFeatures(
        color_histogram=color_histogram,
        texture_vector=texture_vector,
        shape_vector=shape_vector,
    )


def serialize_vector(vector: Sequence[float]) -> str:
    return json.dumps([round(float(value), 8) for value in vector], separators=(",", ":"))


def deserialize_vector(value: str) -> list[float]:
    loaded = json.loads(value)
    return [float(item) for item in loaded]


def store_opencv_features(image_id: int, image_path: Path) -> None:
    features = extract_opencv_features(image_path)
    repositories.upsert_walnut_image_feature(
        image_id=image_id,
        feature_version=OPENCV_FEATURE_VERSION,
        color_histogram=serialize_vector(features.color_histogram),
        texture_vector=serialize_vector(features.texture_vector),
        shape_vector=serialize_vector(features.shape_vector),
    )


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return max(0.0, min(1.0, dot / (left_norm * right_norm)))


def shape_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))
    return max(0.0, min(1.0, 1.0 - (distance / math.sqrt(len(left)))))


def feature_similarity(left: dict, right: dict) -> float:
    color_score = cosine_similarity(
        deserialize_vector(left["color_histogram"]),
        deserialize_vector(right["color_histogram"]),
    )
    texture_score = cosine_similarity(
        deserialize_vector(left["texture_vector"]),
        deserialize_vector(right["texture_vector"]),
    )
    current_shape_similarity = shape_similarity(
        deserialize_vector(left["shape_vector"]),
        deserialize_vector(right["shape_vector"]),
    )
    return ((color_score * 0.4) + (texture_score * 0.4) + (current_shape_similarity * 0.2)) * 100.0


def walnut_image_similarity(base_walnut_id: int, candidate_walnut_id: int) -> WalnutImageSimilarity | None:
    base_features = {
        int(feature["face_no"]): feature
        for feature in repositories.list_walnut_image_features(base_walnut_id, OPENCV_FEATURE_VERSION)
    }
    candidate_features = {
        int(feature["face_no"]): feature
        for feature in repositories.list_walnut_image_features(candidate_walnut_id, OPENCV_FEATURE_VERSION)
    }
    matched_faces = sorted(set(base_features) & set(candidate_features))
    if not matched_faces:
        return None

    score = sum(feature_similarity(base_features[face_no], candidate_features[face_no]) for face_no in matched_faces)
    return WalnutImageSimilarity(
        score=score / len(matched_faces),
        matched_faces=len(matched_faces),
        base_faces=len(base_features),
        candidate_faces=len(candidate_features),
    )
