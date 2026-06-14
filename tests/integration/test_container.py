import os
import subprocess
import time

import psycopg
import pytest
import requests
from testcontainers.core.container import DockerContainer
from testcontainers.postgres import PostgresContainer

pytestmark = [pytest.mark.integration, pytest.mark.slow]

IMAGE_TAG = "user-service-test:latest"
POLICY_IMAGE_TAG = "cdp-policies:test"


def _policy_bundle_build(repo_root: str) -> str:
    """Return build context for the CDP platform policy bundle."""
    cdp_policies_dir = os.path.abspath(os.path.join(repo_root, "..", "cdp", "policies"))
    if os.path.isfile(os.path.join(cdp_policies_dir, "Dockerfile")):
        return cdp_policies_dir
    return os.path.join(repo_root, "tests", "policies")


def _normalize_to_psycopg_sqlalchemy_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _replace_db_user(url: str, user: str, password: str) -> str:
    return url.replace("://test:test@", f"://{user}:{password}@", 1)


def _replace_db_host(url: str, host: str) -> str:
    return url.replace("@localhost:", f"@{host}:", 1)


def _normalize_to_psycopg_conn_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


@pytest.fixture(scope="session", autouse=True)
def build_container_image():
    """Build policy bundle and runtime images once per test session."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    policy_context = _policy_bundle_build(repo_root)
    subprocess.run(
        ["docker", "build", "-f", "Dockerfile", "-t", POLICY_IMAGE_TAG, "."],
        cwd=policy_context,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "docker",
            "build",
            "--target",
            "runtime",
            "--build-arg",
            f"CDP_POLICIES_IMAGE={POLICY_IMAGE_TAG}",
            "-t",
            IMAGE_TAG,
            ".",
        ],
        cwd=repo_root,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    yield


@pytest.fixture(scope="module")
def app_container():
    """Start app container with real Postgres; run migrations inside the container."""
    with PostgresContainer("postgres:18") as pg:
        migration_url_host = _normalize_to_psycopg_sqlalchemy_url(pg.get_connection_url())
        migration_url_container = _replace_db_host(migration_url_host, "host.docker.internal")
        app_url_container = _replace_db_user(
            migration_url_container, "app", "template_app_password_123"
        )

        container = DockerContainer(IMAGE_TAG)
        container.with_kwargs(extra_hosts={"host.docker.internal": "host-gateway"})
        container.with_env("ENV", "test")
        container.with_env("PORT", "8018")
        container.with_env("JWT_JWKS_URI", "http://identity:8014/.well-known/jwks.json")
        container.with_env("APP_DATABASE_URL", app_url_container)
        container.with_env("MIGRATION_DATABASE_URL", migration_url_container)
        container.with_exposed_ports(8018)

        with container as c:
            port = c.get_exposed_port(8018)
            host = c.get_container_host_ip()
            base_url = f"http://{host}:{port}"
            start = time.time()
            while time.time() - start < 20:
                try:
                    requests.get(f"{base_url}/health", timeout=1)
                    break
                except requests.exceptions.RequestException:
                    time.sleep(0.5)
            else:
                pytest.fail("Container did not become ready in time.")

            app_url_host = _replace_db_user(migration_url_host, "app", "template_app_password_123")
            yield {
                "base_url": base_url,
                "migration_url": migration_url_host,
                "app_url": app_url_host,
                "container_id": c.get_wrapped_container().id,
            }


def test_container_health(app_container):
    """Run migrations in-container (audit templates at /app/audit-templates), then verify health."""
    subprocess.run(
        [
            "docker",
            "exec",
            app_container["container_id"],
            "python",
            "-m",
            "alembic",
            "upgrade",
            "head",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    with psycopg.connect(_normalize_to_psycopg_conn_url(app_container["migration_url"])) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regnamespace('audit') IS NOT NULL")
            assert cur.fetchone()[0] is True
            cur.execute("SELECT to_regprocedure('audit.process_dml_hook()') IS NOT NULL")
            assert cur.fetchone()[0] is True
            cur.execute("SELECT has_schema_privilege('app', 'audit', 'USAGE')")
            assert cur.fetchone()[0] is True

    start = time.time()
    while time.time() - start < 20:
        try:
            res = requests.get(f"{app_container['base_url']}/health", timeout=1)
            if res.status_code == 200:
                body = res.json()
                assert body["status"] == "ok"
                assert body.get("version")
                return
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)
    pytest.fail("Health endpoint did not become ready after migration.")
