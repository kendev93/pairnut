"""PySide6 application coordinator."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .database import init_database
from .ui.views import PairNutMainWindow


def assets_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "assets"


def build_application(argv: list[str] | None = None) -> tuple[QApplication, PairNutMainWindow]:
    app = QApplication.instance() or QApplication(argv or sys.argv)
    app.setApplicationName("PairNut")
    app.setOrganizationName("PairNut")
    icon_path = assets_dir() / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    init_database()
    window = PairNutMainWindow(icon_path=icon_path)
    app.aboutToQuit.connect(window._teardown_ui)
    return app, window


def run(argv: list[str] | None = None) -> int:
    app, window = build_application(argv)
    window.show()
    return app.exec()
