from __future__ import annotations

import os
import tempfile
import unittest

from PySide6.QtWidgets import QApplication

from pairnut.app import build_application
from pairnut.ui.views import PairNutMainWindow


class AppSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    def tearDown(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        self.tempdir.cleanup()

    def test_build_application_creates_main_window(self) -> None:
        app, window = build_application([])
        self.assertIsInstance(app, QApplication)
        self.assertIsInstance(window, PairNutMainWindow)
        self.assertEqual(window.windowTitle(), "PairNut")
        self.assertGreaterEqual(window.minimumWidth(), 1200)
        self.assertGreaterEqual(window.minimumHeight(), 800)
        self.assertEqual(window.stack.count(), 3)
        self.assertEqual(window.nav.count(), 3)
        window.close()
