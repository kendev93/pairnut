"""Application update checks."""

from __future__ import annotations

from dataclasses import dataclass
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pairnut import __version__


LATEST_RELEASE_URL = "https://gitee.com/api/v5/repos/ck0318/pairnut/releases/latest"


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    current_version: str
    latest_version: str | None
    release_url: str | None
    has_update: bool
    error: str | None = None


def _normalize_version(version: str) -> tuple[int, ...]:
    normalized = version.strip().removeprefix("v").removeprefix("V")
    parts: list[int] = []
    for part in normalized.split("."):
        digits = ""
        for char in part:
            if not char.isdigit():
                break
            digits += char
        parts.append(int(digits or "0"))
    return tuple(parts)


def is_newer_version(latest: str, current: str) -> bool:
    latest_parts = _normalize_version(latest)
    current_parts = _normalize_version(current)
    length = max(len(latest_parts), len(current_parts))
    latest_parts = latest_parts + (0,) * (length - len(latest_parts))
    current_parts = current_parts + (0,) * (length - len(current_parts))
    return latest_parts > current_parts


def check_for_update(
    current_version: str = __version__,
    release_api_url: str = LATEST_RELEASE_URL,
    timeout_seconds: float = 5.0,
) -> UpdateInfo:
    request = Request(release_api_url, headers={"User-Agent": f"PairNut/{current_version}"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return UpdateInfo(
            current_version=current_version,
            latest_version=None,
            release_url=None,
            has_update=False,
            error=str(exc),
        )

    latest_version = str(payload.get("tag_name") or "").strip()
    release_url = str(payload.get("html_url") or "").strip()
    if not latest_version:
        return UpdateInfo(
            current_version=current_version,
            latest_version=None,
            release_url=release_url or None,
            has_update=False,
            error="release payload missing tag_name",
        )

    return UpdateInfo(
        current_version=current_version,
        latest_version=latest_version,
        release_url=release_url or None,
        has_update=is_newer_version(latest_version, current_version),
    )
