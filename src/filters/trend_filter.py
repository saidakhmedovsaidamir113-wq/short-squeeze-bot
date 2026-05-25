"""
trend_filter.py
---------------
Filters out stocks in a downtrend.

Rule: A stock passes if its current price is ABOVE its 50-day SMA.
Price below SMA 50 = downtrend = rejected.

(Per strategy: later this may be extended with trendline logic,
but SMA 50 is the objective baseline.)
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def apply_trend_filter(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only stocks trading above their 50-day SMA.

    Expects columns: current_price, sma_50
    """
    if df.empty:
        return df

    before = len(df)
    filtered = df[df["current_price"] > df["sma_50"]].reset_index(drop=True)

    logger.info(
        f"Trend filter (price > SMA50): "
        f"{len(filtered)} of {before} stocks passed."
    )
    return filtered