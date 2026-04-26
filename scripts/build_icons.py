#!/usr/bin/env python3
"""Create platform icon files from assets/icon.png."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ICON = ROOT / "assets" / "icon.png"
OUTPUT_DIR = ROOT / "build" / "icons"
ICO_PATH = OUTPUT_DIR / "icon.ico"
ICNS_PATH = OUTPUT_DIR / "icon.icns"

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]
ICNS_SIZES = [16, 32, 128, 256, 512]


def load_icon() -> Image.Image:
    if not SOURCE_ICON.exists():
        raise FileNotFoundError(f"Missing source icon: {SOURCE_ICON}")
    return Image.open(SOURCE_ICON).convert("RGBA")


def write_ico(image: Image.Image) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(ICO_PATH, sizes=[(size, size) for size in ICO_SIZES])


def write_icns(image: Image.Image) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(ICNS_PATH, sizes=[(size, size) for size in [*ICNS_SIZES, 1024]])


def main() -> None:
    image = load_icon()
    write_ico(image)
    write_icns(image)
    print(f"Wrote {ICO_PATH}")
    if ICNS_PATH.exists():
        print(f"Wrote {ICNS_PATH}")


if __name__ == "__main__":
    main()
