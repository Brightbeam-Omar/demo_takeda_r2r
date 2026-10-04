"""``python -m app_api.migrate``: bring the ``app`` database to the latest schema."""

from app_api.db import migrate

if __name__ == "__main__":
    migrate()
