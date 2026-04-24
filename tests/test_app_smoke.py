from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace

import flet as ft

from pairnut import app as app_module


class FakeWindow:
    def __init__(self) -> None:
        self.min_width = None
        self.min_height = None


class FakePage:
    def __init__(self) -> None:
        self.title = None
        self.theme_mode = None
        self.padding = None
        self.spacing = None
        self.window = FakeWindow()
        self.controls = []
        self.cleaned = False
        self.updated = 0

    def clean(self) -> None:
        self.cleaned = True
        self.controls.clear()

    def add(self, *controls) -> None:
        self.controls.extend(controls)

    def update(self) -> None:
        self.updated += 1


class AppSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name

    def tearDown(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        self.tempdir.cleanup()

    def test_app_renders_main_shell(self) -> None:
        page = FakePage()
        app_module.main(page)
        self.assertEqual(page.title, "PairNut")
        self.assertEqual(page.window.icon, "icon.png")
        self.assertEqual(page.window.min_width, 1200)
        self.assertEqual(page.window.min_height, 800)
        self.assertEqual(len(page.controls), 1)
        self.assertIsInstance(page.controls[0], ft.Container)
        self.assertGreater(page.updated, 0)
