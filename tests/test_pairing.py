from __future__ import annotations

import os
import tempfile
import unittest

from pairnut.database import repositories
from pairnut.database.schema import init_database
from pairnut.services.pairing import (
    blacklist_pair,
    list_blacklist_entries,
    load_pairing_board,
    lock_pair,
    remove_blacklist_entry,
    unlock_pair,
)


class PairingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        os.environ["PAIRNUT_DATA_DIR"] = self.tempdir.name
        init_database()
        self.variety_id = repositories.create_variety("狮子头", "SZT", 1.0)
        self.w1 = self._create_walnut("SZT-0001", 40.0, 42.0, 38.0, 52.0)
        self.w2 = self._create_walnut("SZT-0002", 40.2, 42.1, 38.2, 52.2)
        self.w3 = self._create_walnut("SZT-0003", 44.0, 46.0, 42.0, 60.0)

    def tearDown(self) -> None:
        os.environ.pop("PAIRNUT_DATA_DIR", None)
        self.tempdir.cleanup()

    def _create_walnut(
        self,
        serial_no: str,
        edge_mm: float,
        belly_mm: float,
        height_mm: float,
        weight_g: float,
    ) -> int:
        return repositories.create_walnut(
            {
                "variety_id": self.variety_id,
                "serial_mode": "manual",
                "serial_no": serial_no,
                "edge_mm": edge_mm,
                "belly_mm": belly_mm,
                "height_mm": height_mm,
                "weight_g": weight_g,
                "defect_level": "none",
                "notes": None,
            }
        )

    def test_board_shares_unlocked_candidates_keyed_by_walnut_id(self) -> None:
        board = load_pairing_board(self.variety_id)

        candidate_ids = {item.walnut_id for item in board.candidates_by_walnut[self.w1]}

        self.assertIn(self.w2, candidate_ids)
        self.assertEqual(set(board.walnuts_by_id), {self.w1, self.w2, self.w3})

    def test_board_carries_images_and_locks_for_both_partners(self) -> None:
        repositories.upsert_walnut_image(self.w1, 1, "w1-1.jpg", "w1/1.jpg")
        lock_id = lock_pair(self.variety_id, self.w1, self.w2)

        board = load_pairing_board(self.variety_id)

        self.assertEqual(len(board.images_by_walnut[self.w1]), 1)
        self.assertNotIn(self.w2, board.images_by_walnut)
        self.assertEqual(int(board.locks_by_walnut[self.w1]["id"]), lock_id)
        self.assertEqual(int(board.locks_by_walnut[self.w2]["id"]), lock_id)
        self.assertEqual(board.candidates_by_walnut[self.w1], [])

    def test_lock_pair_rejects_candidate_outside_strict_tolerance(self) -> None:
        outside = self._create_walnut("SZT-0004", 41.1, 42.0, 38.0, 52.0)

        with self.assertRaises(ValueError):
            lock_pair(self.variety_id, self.w1, outside)

    def test_unlock_pair_allows_locking_the_same_pair_again(self) -> None:
        first_id = lock_pair(self.variety_id, self.w1, self.w2)
        unlock_pair(first_id)

        board = load_pairing_board(self.variety_id)
        self.assertNotIn(self.w1, board.locks_by_walnut)

        second_id = lock_pair(self.variety_id, self.w1, self.w2)
        self.assertNotEqual(first_id, second_id)

    def test_blacklist_entries_are_labelled_and_removable(self) -> None:
        blacklist_pair(self.variety_id, self.w1, self.w3, reason="人工排除")

        entries = list_blacklist_entries(self.variety_id)

        self.assertEqual(len(entries), 1)
        self.assertIn("SZT-0003", entries[0].label)
        self.assertIn("人工排除", entries[0].label)

        self.assertTrue(remove_blacklist_entry(entries[0].id))
        self.assertEqual(list_blacklist_entries(self.variety_id), [])
        self.assertFalse(remove_blacklist_entry(entries[0].id))
