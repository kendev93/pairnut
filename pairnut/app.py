"""Flet application coordinator."""

from __future__ import annotations

import flet as ft

from .database import init_database
from .ui.views import PairNutUI


def main(page: ft.Page) -> None:
    page.title = "PairNut"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.spacing = 0
    page.window.min_width = 1200
    page.window.min_height = 800

    init_database()
    ui = PairNutUI(page)
    ui.render()
