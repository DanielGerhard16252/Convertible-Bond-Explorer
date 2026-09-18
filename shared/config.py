"""Explicit runtime configuration and bundled resource locations."""

import os
from pathlib import Path
import sys

from dotenv import load_dotenv


def application_directory() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def resource_directory() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def load_app_environment() -> None:
    """Prefer runtime overrides, then the credentials bundled at build time."""
    load_dotenv(application_directory() / ".env", override=False)
    if getattr(sys, "frozen", False):
        load_dotenv(resource_directory() / ".env", override=False)


def configured_data_path(variable: str, filename: str) -> Path:
    load_app_environment()
    configured = os.getenv(variable)
    if not configured:
        return resource_directory() / "data" / filename
    path = Path(configured).expanduser()
    return path if path.is_absolute() else application_directory() / path
