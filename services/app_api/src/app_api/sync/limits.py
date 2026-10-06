"""Queue constants shared by the drain worker and the health endpoint (kept free of the lakehouse reader)."""

STALE_CLAIM_MINUTES = 5  # a claimed event older than this is taken back by the next full pass (F08, F21)
