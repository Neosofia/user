"""000 init db

Revision ID: 000
Revises:
Create Date: 2026-05-28
"""
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import make_url

from src.bootstrap.config import settings

revision = "000"
down_revision = None
branch_labels = None
depends_on = None


def _resolve_audit_template_dir() -> str:
    container_dir = "/app/audit-templates"
    if os.path.isdir(container_dir):
        return container_dir
    fallback_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../../sql/audit"))
    if os.path.isdir(fallback_dir):
        return fallback_dir
    raise FileNotFoundError(
        f"Audit template directory not found. Tried {container_dir!r} and {fallback_dir!r}"
    )


def upgrade() -> None:
    app_password = make_url(settings.app_database_url).password
    if not app_password:
        raise ValueError("APP_DATABASE_URL must include a password for platform init")

    conn = op.get_bind()
    conn.execute(
        sa.text("SELECT set_config(:guc, :password, false)"),
        {"guc": "app.bootstrap_password", "password": app_password},
    )

    template_dir = _resolve_audit_template_dir()
    for file in (
        "00_bootstrap_app.sql",
        "01_dml_hooks.sql",
        "02_ddl_setup.sql",
        "03_ddl_protection.sql",
        "04_views.sql",
        "05_grant_app_audit.sql",
    ):
        file_path = os.path.join(template_dir, file)
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Audit template not found: {file_path}")
        with open(file_path, "r", encoding="utf-8") as handle:
            op.execute(handle.read())


def downgrade() -> None:
    raise Exception(
        "000_init_db is irreversible — dropping the audit schema would destroy all audit history. "
        "To reset, drop and recreate the database."
    )
