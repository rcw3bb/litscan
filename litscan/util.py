"""
Utility helpers for litscan.

Provides :func:`setup_logger` for consistent logging configuration.

Author: Ron Webb
Since: 1.0.0
"""

from __future__ import annotations

import importlib.resources
import logging
import logging.config
import os
import shutil
from pathlib import Path


def _load_config(config_path: str) -> None:
    """
    Load ``logging.ini`` from *config_path* via :func:`logging.config.fileConfig`.

    Falls back to :func:`logging.basicConfig` and emits a warning when the
    file cannot be parsed.

    Author: Ron Webb
    Since: 1.0.0
    """
    try:
        logging.config.fileConfig(config_path, disable_existing_loggers=False)
    except Exception:  # pylint: disable=broad-exception-caught
        logging.basicConfig(level=logging.INFO)
        logging.exception(
            "Failed to load logging config from %s. Using basic configuration.",
            config_path,
        )


def _load_packaged_config() -> None:
    """
    Load the ``logging.ini`` bundled inside the ``litscan`` package using
    :mod:`importlib.resources`.

    Author: Ron Webb
    Since: 1.0.0
    """
    pkg_ref = importlib.resources.files("litscan").joinpath("logging.ini")
    with importlib.resources.as_file(pkg_ref) as src_path:
        _load_config(str(src_path))


def _ensure_config_dir(config_dir: Path) -> Path:
    """
    Create *config_dir* if it does not exist and copy the packaged
    ``logging.ini`` into it when the file is absent.

    Returns the path to ``logging.ini`` inside *config_dir*.

    Author: Ron Webb
    Since: 1.0.0
    """
    config_dir.mkdir(parents=True, exist_ok=True)
    target = config_dir / "logging.ini"
    if not target.exists():
        pkg_ref = importlib.resources.files("litscan").joinpath("logging.ini")
        with importlib.resources.as_file(pkg_ref) as src_path:
            shutil.copy2(src_path, target)
    return target


def setup_logger(name: str) -> logging.Logger:
    """
    Set up and return a logger with consistent configuration.

    Resolution order for ``logging.ini``:

    1. ``LITSCAN_CONFIG_DIR`` environment variable — when set, the directory
       is created if necessary, the packaged ``logging.ini`` is seeded into
       it on first run, and the file is loaded from there.
    2. Bundled ``logging.ini`` inside the ``litscan`` package — used directly
       via :mod:`importlib.resources` when ``LITSCAN_CONFIG_DIR`` is not set.

    Author: Ron Webb
    Since: 1.0.0
    """
    litscan_config_dir = os.environ.get("LITSCAN_CONFIG_DIR")
    if litscan_config_dir:
        config_path = str(_ensure_config_dir(Path(litscan_config_dir)))
        _load_config(config_path)
    else:
        _load_packaged_config()
    return logging.getLogger(name)
