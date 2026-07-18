from __future__ import annotations

import os
from pathlib import Path


def app_data_dir() -> Path:
    """Return a per-user data directory that sits outside the source checkout."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".autofire"
    path = root / "AutoFire"
    path.mkdir(parents=True, exist_ok=True)
    (path / "log").mkdir(exist_ok=True)
    return path


def database_path() -> Path:
    return app_data_dir() / "autofire.db"


def log_dir() -> Path:
    return app_data_dir() / "log"
