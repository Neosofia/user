import json
import pytest
import base64
import shutil
import tempfile
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jsonschema import validate
from jsonschema.validators import _RefResolver
import os

# Generate keys at module load time so they exist before ANY test imports
_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

_PRIVATE_PEM = _PRIVATE_KEY.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

_PUBLIC_PEM = _PUBLIC_KEY.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

os.environ["JWT_PUBLIC_KEY"] = base64.b64encode(_PUBLIC_PEM).decode("utf-8")
os.environ.pop("JWT_JWKS_URI", None)
os.environ["JWT_AUDIENCE"] = "user"
os.environ["ENV"] = "test"
os.environ["APP_DATABASE_URL"] = "postgresql+psycopg://app:dummy@localhost/dummy"
os.environ["MIGRATION_DATABASE_URL"] = "postgresql+psycopg://template:dummy@localhost/dummy"

_tests_dir = Path(__file__).resolve().parent
_repo_root = _tests_dir.parent
_base_policies = _repo_root / "policies"
_fixture_product_cedar = _tests_dir / "policies" / "user" / "cedar"
_cdp_product_cedar = _repo_root.parent / "cdp" / "policies" / "user" / "cedar"
_cdp_role_catalog = _repo_root.parent / "cdp" / "policies" / "user" / "role-catalog.json"
_fixture_role_catalog = _tests_dir / "policies" / "user" / "role-catalog.json"


def _product_cedar_sources() -> list[Path]:
    if _cdp_product_cedar.is_dir():
        return [_cdp_product_cedar]
    if _fixture_product_cedar.is_dir():
        return [_fixture_product_cedar]
    return []


def _configure_authorization_policies_dir() -> None:
    product_sources = _product_cedar_sources()
    if product_sources:
        merged = Path(tempfile.mkdtemp(prefix="user-policies-"))
        for cedar_file in _base_policies.glob("*.cedar"):
            shutil.copy2(cedar_file, merged / cedar_file.name)
        for source in product_sources:
            for cedar_file in source.glob("*.cedar"):
                shutil.copy2(cedar_file, merged / cedar_file.name)
        os.environ["AUTHORIZATION_POLICIES_DIR"] = str(merged)
        return
    os.environ["AUTHORIZATION_POLICIES_DIR"] = str(_base_policies)


def _configure_role_catalog_overlay() -> None:
    if _cdp_role_catalog.is_file():
        os.environ["ROLE_CATALOG_OVERLAY"] = str(_cdp_role_catalog)
    elif _fixture_role_catalog.is_file():
        os.environ["ROLE_CATALOG_OVERLAY"] = str(_fixture_role_catalog)


_configure_authorization_policies_dir()
_configure_role_catalog_overlay()

from src.app import create_app  # noqa: E402 — must import after env vars are set

_TIER1_ACTORS = frozenset({"operator", "study", "clinician", "patient", "demo"})


@pytest.fixture(autouse=True)
def _tier1_actor_classes_for_unit_tests():
    """No-op: tier-1 actors come from app config via ``configure_tier1_actor_classes``."""
    yield


@pytest.fixture(scope="session")
def rsa_keypair():
    return {"private": _PRIVATE_PEM, "public": _PUBLIC_PEM}


@pytest.fixture
def app():
    application = create_app(
        {
            "TESTING": True,
            "TIER1_ACTOR_CLASSES": _TIER1_ACTORS,
            "JWT_JWKS_URI": None,
            "JWT_PUBLIC_KEY": _PUBLIC_PEM.decode("utf-8"),
            "JWT_AUDIENCE": "user",
        }
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def api_spec():
    spec_path = Path(__file__).parent.parent / "openapi.json"
    with open(spec_path) as f:
        return json.load(f)


@pytest.fixture
def validate_response():
    def _validate(spec, endpoint, method, status_code, data):
        try:
            schema = spec["paths"][endpoint][method]["responses"][str(status_code)]["content"]["application/json"]["schema"]
        except KeyError:
            return
        resolver = _RefResolver.from_schema(spec)
        validate(instance=data, schema=schema, resolver=resolver)
    return _validate

