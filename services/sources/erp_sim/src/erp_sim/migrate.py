"""``python -m erp_sim.migrate``: bring the ``erp_sim`` database to the latest schema."""

from erp_sim.db import migrate

if __name__ == "__main__":
    migrate()
