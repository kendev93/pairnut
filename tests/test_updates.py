from __future__ import annotations

import unittest
from unittest.mock import patch

from pairnut.services.updates import check_for_update, is_newer_version


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self) -> bytes:
        return self.body


class UpdateTests(unittest.TestCase):
    def test_version_comparison_accepts_release_tags(self) -> None:
        self.assertTrue(is_newer_version("v1.2.0", "1.1.9"))
        self.assertFalse(is_newer_version("v1.2.0", "1.2.0"))
        self.assertFalse(is_newer_version("v1.2.0", "1.2.1"))

    def test_check_for_update_reports_new_release(self) -> None:
        body = b'{"tag_name": "v0.2.0", "html_url": "https://example.com/releases/v0.2.0"}'
        with patch("pairnut.services.updates.urlopen", return_value=_Response(body)):
            info = check_for_update(current_version="0.1.0", release_api_url="https://example.com/api")

        self.assertTrue(info.has_update)
        self.assertEqual(info.latest_version, "v0.2.0")
        self.assertEqual(info.release_url, "https://example.com/releases/v0.2.0")
        self.assertIsNone(info.error)

    def test_check_for_update_handles_network_errors(self) -> None:
        with patch("pairnut.services.updates.urlopen", side_effect=OSError("offline")):
            info = check_for_update(current_version="0.1.0", release_api_url="https://example.com/api")

        self.assertFalse(info.has_update)
        self.assertEqual(info.error, "offline")

    def test_check_for_update_handles_invalid_json(self) -> None:
        with patch("pairnut.services.updates.urlopen", return_value=_Response(b"not json")):
            info = check_for_update(current_version="0.1.0", release_api_url="https://example.com/api")

        self.assertFalse(info.has_update)
        self.assertIsNotNone(info.error)


if __name__ == "__main__":
    unittest.main()
