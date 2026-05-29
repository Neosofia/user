from alembic import context
from sqlalchemy import create_engine

from src.bootstrap.config import settings
from src.db.engine import Base
import src.models.user  # noqa: F401

config = context.config
if config.config_file_name is not None:
    pass

target_metadata = Base.metadata
_migration_url = settings.migration_database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_migration_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_migration_url)
    with engine.begin() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
