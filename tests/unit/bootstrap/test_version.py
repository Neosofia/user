import pytest
from importlib.metadata import PackageNotFoundError

from src.bootstrap import version as version_module

pytestmark = pytest.mark.unit


def test_service_version_uses_installed_distribution(monkeypatch):
    version_module.service_version.cache_clear()
    monkeypatch.setattr(version_module, "version", lambda _name: "9.9.9")
    assert version_module.service_version() == "9.9.9"
    version_module.service_version.cache_clear()


def test_service_version_falls_back_to_pyproject(monkeypatch):
    version_module.service_version.cache_clear()
    monkeypatch.setattr(
        version_module,
        "version",
        lambda _name: (_ for _ in ()).throw(PackageNotFoundError()),
    )
    result = version_module.service_version()
    assert result
    assert result != "0.0.0"
    version_module.service_version.cache_clear()
