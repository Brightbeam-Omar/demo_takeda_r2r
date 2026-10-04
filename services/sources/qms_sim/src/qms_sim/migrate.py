"""``python -m qms_sim.migrate``: bring the ``qms_sim`` database to the latest schema."""

from qms_sim.db import migrate

if __name__ == "__main__":
    migrate()
