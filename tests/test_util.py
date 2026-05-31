"""Tests for util module.

Author: Ron Webb
Since: 1.0.0
"""

from pathlib import Path
import logging

import litscan.util as util_module
from litscan.util import (
    _ensure_config_dir,
    _load_config,
    _load_packaged_config,
    setup_logger,
)

_MINIMAL_INI = (
    "[loggers]\nkeys=root\n\n"
    "[handlers]\nkeys=consoleHandler\n\n"
    "[formatters]\nkeys=consoleFormatter\n\n"
    "[logger_root]\nlevel=INFO\nhandlers=consoleHandler\n\n"
    "[handler_consoleHandler]\nclass=StreamHandler\nformatter=consoleFormatter\n"
    "args=(sys.stderr,)\n\n"
    "[formatter_consoleFormatter]\nformat=%(levelname)s:%(name)s:%(message)s\n"
)


def test_load_config_succeeds_with_valid_ini(tmp_path: Path) -> None:
    """It should load fileConfig successfully when the ini file is valid."""
    ini = tmp_path / "logging.ini"
    ini.write_text(_MINIMAL_INI, encoding="utf-8")
    _load_config(str(ini))
    assert isinstance(logging.getLogger("root"), logging.Logger)


def test_load_config_falls_back_to_basic_config_on_bad_path(monkeypatch) -> None:
    """It should fall back to basicConfig when the ini path is invalid."""
    calls: list[int] = []
    monkeypatch.setattr(logging, "basicConfig", lambda **_kw: calls.append(1))
    _load_config("/nonexistent/path/logging.ini")
    assert calls == [1]


def test_load_packaged_config_loads_bundled_ini() -> None:
    """It should load the logging.ini bundled inside the litscan package."""
    _load_packaged_config()
    assert isinstance(logging.getLogger("litscan"), logging.Logger)


def test_ensure_config_dir_creates_directory_and_seeds_ini(tmp_path: Path) -> None:
    """It should create the directory and copy the bundled logging.ini into it."""
    config_dir = tmp_path / "cfg"
    result = _ensure_config_dir(config_dir)
    assert config_dir.exists()
    assert result == config_dir / "logging.ini"
    assert result.exists()


def test_ensure_config_dir_does_not_overwrite_existing_ini(tmp_path: Path) -> None:
    """It should not overwrite logging.ini when one already exists."""
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    existing = config_dir / "logging.ini"
    existing.write_text("# sentinel", encoding="utf-8")
    _ensure_config_dir(config_dir)
    assert existing.read_text(encoding="utf-8") == "# sentinel"


def test_setup_logger_uses_packaged_config_by_default(monkeypatch) -> None:
    """It should use the bundled logging.ini when LITSCAN_CONFIG_DIR is not set."""
    monkeypatch.delenv("LITSCAN_CONFIG_DIR", raising=False)
    called: list[int] = []
    monkeypatch.setattr(util_module, "_load_packaged_config", lambda: called.append(1))
    logger = setup_logger("tests.default")
    assert called == [1]
    assert isinstance(logger, logging.Logger)


def test_setup_logger_uses_config_dir_when_env_is_set(
    tmp_path: Path, monkeypatch
) -> None:
    """It should seed and load from LITSCAN_CONFIG_DIR when the env var is set."""
    monkeypatch.setenv("LITSCAN_CONFIG_DIR", str(tmp_path))
    logger = setup_logger("tests.config_dir")
    assert (tmp_path / "logging.ini").exists()
    assert isinstance(logger, logging.Logger)
    assert logger.name == "tests.config_dir"
