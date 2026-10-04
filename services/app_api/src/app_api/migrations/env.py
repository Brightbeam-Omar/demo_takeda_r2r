from alembic import context
from app_api.models import Base
from r2r_core.db import run_migrations_env

run_migrations_env(context, Base.metadata)
