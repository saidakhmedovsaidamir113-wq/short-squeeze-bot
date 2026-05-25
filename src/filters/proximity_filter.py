"""
proximity_filter.py
-------------------
Filters out stocks sitting too far below their 100-day high.

Rule: A stock passes if it is within X% of its 100-day high.
Default X = 15% (configurable in settings.yaml).

This keeps only stocks "primed" for a breakout, removing those
that are deep below their highs (unlikely to squeeze soon).
"""

import logging
import pandas as pd

from src.config import STRATEGY

logger = logging.getLogger(__name__)


def apply_proximity_filter(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only stocks within the configured % distance of 100-day high.

    Expects column: distance_from_high_pct
    """
    if df.empty:
        return df

    max_distance = STRATEGY["max_distance_from_high_pct"]  # 0.15

    before = len(df)
    filtered = df[df["distance_from_high_pct"] <= max_distance].reset_index(drop=True)

    logger.info(
        f"Proximity filter (within {max_distance:.0%} of 100d high): "
        f"{len(filtered)} of {before} stocks passed."
    )
    return filtered