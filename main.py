#!/usr/bin/env python3
"""PairNut desktop entrypoint."""

import flet as ft

from pairnut.app import main


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
