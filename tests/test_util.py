"""Tests for util module.

Author: Ron Webb
Since: 1.0.0
"""

from pathlib import Path
import logging
import os

import litscan.util as util_module
from litscan.util import setup_logger


def test_setup_logger_uses_found_logging_ini(tmp_path: Path, monkeypatch) -> None:
    """It should configure and return a logger when logging.ini is available."""
    (tmp_path / "logging.ini").write_text(
        """[loggers]\nkeys=root\n\n[handlers]\nkeys=consoleHandler\n\n[formatters]\nkeys=consoleFormatter\n\n[logger_root]\nlevel=INFO\nhandlers=consoleHandler\n\n[handler_consoleHandler]\nclass=StreamHandler\nformatter=consoleFormatter\nargs=(sys.stderr,)\n\n[formatter_consoleFormatter]\nformat=%(levelname)s:%(name)s:%(message)s\n""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    logger = setup_logger("tests.logger")

    assert isinstance(logger, logging.Logger)
    assert logger.name == "tests.logger"


def test_setup_logger_falls_back_to_basic_config(tmp_path: Path, monkeypatch) -> None:
    """It should call basicConfig when no logging.ini is found."""
    calls: list[int] = []

    def fake_basic_config(*_args, **_kwargs) -> None:
        calls.append(1)

    original_exists = os.path.exists

    def fake_exists(path: str) -> bool:
        if path.endswith("logging.ini"):
            return False
        return original_exists(path)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)
    monkeypatch.setattr(util_module.os.path, "exists", fake_exists)

    logger = setup_logger("tests.fallback")

    assert calls == [1]
    assert isinstance(logger, logging.Logger)
