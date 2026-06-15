"""Buildozer 前台 Service 入口（:foreground:sticky）。"""

from __future__ import annotations


def main() -> None:
    from background_engine import run_service_loop

    run_service_loop()
