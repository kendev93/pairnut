from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QLabel

from pairnut.app import build_application, run
from pairnut.database import repositories
from pairnut.services.pairing import PairingBoard
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

    def test_run_shows_main_window_maximized(self) -> None:
        with (
            patch("pairnut.app.build_application") as build_application_mock,
        ):
            app = Mock()
            window = Mock()
            app.exec.return_value = 0
            build_application_mock.return_value = (app, window)

            self.assertEqual(run([]), 0)
            build_application_mock.assert_called_once_with([])
            window.showMaximized.assert_called_once_with()
            app.exec.assert_called_once_with()

    def test_locked_pair_card_falls_back_when_partner_row_is_missing(self) -> None:
        """A lock pointing at a missing walnut row must not crash the board."""
        _app, window = build_application([])
        try:
            variety_id = repositories.create_variety("狮子头", "SZT", 1.0)
            walnut_id = repositories.create_walnut(
                self._walnut_data(variety_id, "SZT-0001")
            )
            partner_id = repositories.create_walnut(
                self._walnut_data(variety_id, "SZT-0002")
            )
            repositories.lock_pair(variety_id, walnut_id, partner_id)
            lock = repositories.list_locked_pairs(
                variety_id=variety_id, active_only=True
            )[0]
            walnut = repositories.get_walnut(walnut_id)
            assert walnut is not None
            board = PairingBoard(
                walnuts=[],
                candidates_by_walnut={},
                images_by_walnut={},
                locks_by_walnut={walnut_id: lock},
                walnuts_by_id={},
            )

            group = window.matching_tab._create_walnut_group(
                variety_id, walnut, [], board
            )

            labels = [label.text() for label in group.findChildren(QLabel)]
            self.assertTrue(
                any(f"核桃 {partner_id}" in text for text in labels), labels
            )
        finally:
            window.close()

    def test_unlock_pair_reports_error_instead_of_raising(self) -> None:
        _app, window = build_application([])
        try:
            with (
                patch.object(
                    repositories,
                    "unlock_pair",
                    side_effect=sqlite3.OperationalError("database is locked"),
                ) as unlock_pair,
                patch.object(window, "show_error") as show_error,
            ):
                window.matching_tab._unlock_pair(7)

            unlock_pair.assert_called_once_with(7)
            show_error.assert_called_once()
        finally:
            window.close()

    @staticmethod
    def _walnut_data(variety_id: int, serial_no: str) -> dict:
        return {
            "variety_id": variety_id,
            "serial_mode": "manual",
            "serial_no": serial_no,
            "edge_mm": 40.0,
            "belly_mm": 42.0,
            "height_mm": 38.0,
            "weight_g": 52.0,
            "defect_level": "none",
            "notes": None,
        }

    def test_navigation_refreshes_only_the_selected_tab(self) -> None:
        _app, window = build_application([])
        with (
            patch.object(window.variety_tab, "refresh") as variety_refresh,
            patch.object(window.walnut_tab, "refresh") as walnut_refresh,
            patch.object(window.matching_tab, "refresh") as matching_refresh,
        ):
            window._handle_navigation_change(2)

        self.assertEqual(window.stack.currentIndex(), 2)
        variety_refresh.assert_not_called()
        walnut_refresh.assert_not_called()
        matching_refresh.assert_called_once_with()
        window.close()
