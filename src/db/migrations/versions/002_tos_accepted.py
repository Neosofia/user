"""002 tos_accepted on users

Revision ID: 002
Revises: 001
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "tos_accepted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="True after the user accepts the platform Terms of Service in CDP UI",
        ),
    )
    op.execute(sa.text("SELECT audit.setup_tracking('public', 'users')"))


def downgrade() -> None:
    raise NotImplementedError("Downgrade is disabled to preserve immutable audit history.")
