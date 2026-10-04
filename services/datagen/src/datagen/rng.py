"""Seeded random streams. Nothing in the generator touches the global ``random`` module."""

import random


def stream(seed: int, name: str) -> random.Random:
    """An independent, reproducible stream per purpose, so tuning one part does not reshuffle another."""
    return random.Random(f"{seed}:{name}")
