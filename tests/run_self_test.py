from __future__ import annotations

from pathlib import Path

from yae.tests.self_test import run_self_test


if __name__ == "__main__":
    run_self_test(Path(__file__).resolve().parents[1])
