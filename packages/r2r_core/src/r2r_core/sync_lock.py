"""The one Postgres advisory lock between the demo reset and the drain worker (F13-FR-05, OQ-148).

The reset holds it exclusively (a transaction-level lock) from before it clears the app tables until the new
data is published; the worker takes it shared for each drain pass and skips the pass when it cannot.
"""

RESET_LOCK_KEY = 7_201_126  # any fixed number: both sides must use this one
