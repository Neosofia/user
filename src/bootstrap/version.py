"""Installed distribution version (semver from pyproject) for health and ops."""

from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import tomllib

DISTRIBUTION = "user"


def _pyproject_version() -> str | None:
    candidates = (
        Path("/app/pyproject.toml"),
        Path(__file__).resolve().parents[2] / "pyproject.toml",
    )
    for path in candidates:
        if not path.is_file():
            continue
        with path.open("rb") as handle:
            data = tomllib.load(handle)
        project = data.get("project")
        if isinstance(project, dict):
            raw = project.get("version")
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return None


@lru_cache
def service_version() -> str:
    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        return _pyproject_version() or "0.0.0"
