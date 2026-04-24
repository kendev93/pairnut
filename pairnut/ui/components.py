"""Reusable Flet UI helpers."""

from __future__ import annotations

import flet as ft


def section_title(text: str) -> ft.Text:
    return ft.Text(text, size=20, weight=ft.FontWeight.BOLD)


def status_text(message: str, color: str = ft.Colors.BLUE_GREY_700) -> ft.Text:
    return ft.Text(message, color=color)


def labeled_metric(label: str, value: str) -> ft.Column:
    return ft.Column(
        controls=[
            ft.Text(label, size=12, color=ft.Colors.BLUE_GREY_400),
            ft.Text(value, size=14, weight=ft.FontWeight.W_600),
        ],
        spacing=2,
        tight=True,
    )
