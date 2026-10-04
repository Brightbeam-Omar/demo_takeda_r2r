from alembic import context
from lims_sim.models import Base
from r2r_core.db import run_migrations_env

run_migrations_env(context, Base.metadata)
