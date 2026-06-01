"""001 users registry

Revision ID: 001
Revises: 000
Create Date: 2026-05-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = "000"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "uuid",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="Same as users.uuid in Authentication (JWT sub); not generated here",
        ),
        sa.Column("tenant_uuid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idp_id", sa.Text(), nullable=False),
        sa.Column(
            "display_code",
            sa.Text(),
            nullable=True,
            comment="Human-facing shorthand",
        ),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column(
            "roles",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
            comment="Tier-2 role slugs: {tenant_type}.{role} (e.g. platform.admin)",
        ),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint("idp_id"),
        sa.UniqueConstraint("tenant_uuid", "display_code", name="uq_users_tenant_display_code"),
    )
    op.create_index("ix_users_tenant_uuid", "users", ["tenant_uuid"])

    op.execute(sa.text("SELECT audit.setup_tracking('public', 'users')"))


def downgrade() -> None:
    raise NotImplementedError("Downgrade is disabled to preserve immutable audit history.")
