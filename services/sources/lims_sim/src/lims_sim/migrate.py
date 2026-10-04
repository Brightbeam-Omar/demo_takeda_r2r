"""``python -m lims_sim.migrate``: bring the ``lims_sim`` database to the latest schema."""

from lims_sim.db import migrate

if __name__ == "__main__":
    migrate()
