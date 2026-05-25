"""
breakout_detector.py
--------------------
Classifies each candidate into a signal category and adds
conviction/volume flags.

Categories (priority order):
  1. BREAKOUT      — price >= prior 100-day high
  2. NEAR_BREAKOUT — within NEAR_THRESHOLD of the high (default 3%)
  3. WATCHLIST     — passed all filters but further from high

Extra flags:
  - volume_confirmed: latest volume > average (real catalyst)
  - high_conviction: Short Ratio > 8 (research: real squeeze pressure)
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Within this distance of the 100-day high = "near breakout"
NEAR_THRESHOLD = 0.03  # 3%

# Short Ratio above this = high conviction (days-to-cover pressure)
HIGH_CONVICTION_SR = 8.0

# Volume must be at least this multiple of average to "confirm"
VOLUME_CONFIRM_RATIO = 1.0


def classify_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add classification columns to the candidate dataframe.

    Adds:
      - is_breakout (bool)
      - category (str): "BREAKOUT" | "NEAR_BREAKOUT" | "WATCHLIST"
      - volume_confirmed (bool)
      - high_conviction (bool)
    """
    if df.empty:
        for col in ["is_breakout", "category", "volume_confirmed", "high_conviction"]:
            df[col] = []
        return df

    df = df.copy()

    # Breakout: current price reached/exceeded the prior 100-day high
    df["is_breakout"] = df["current_price"] >= df["high_100d"]

    # Category by proximity
    def categorize(row):
        if row["current_price"] >= row["high_100d"]:
            return "BREAKOUT"
        elif row["distance_from_high_pct"] <= NEAR_THRESHOLD:
            return "NEAR_BREAKOUT"
        else:
            return "WATCHLIST"

    df["category"] = df.apply(categorize, axis=1)

    # Volume confirmation (catalyst fingerprint)
    if "volume_ratio" in df.columns:
        df["volume_confirmed"] = df["volume_ratio"] >= VOLUME_CONFIRM_RATIO
    else:
        df["volume_confirmed"] = False

    # High conviction by days-to-cover
    df["high_conviction"] = pd.to_numeric(
        df["Short Ratio"], errors="coerce"
    ) >= HIGH_CONVICTION_SR

    n_break = int((df["category"] == "BREAKOUT").sum())
    n_near = int((df["category"] == "NEAR_BREAKOUT").sum())
    n_watch = int((df["category"] == "WATCHLIST").sum())
    logger.info(
        f"Classification: {n_break} breakout, "
        f"{n_near} near-breakout, {n_watch} watchlist."
    )
    return df