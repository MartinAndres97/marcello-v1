from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_db_url
from app.models import Base

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=get_db_url().render_as_string(hide_password=False), target_metadata=target_metadata,
                      literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(get_db_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
