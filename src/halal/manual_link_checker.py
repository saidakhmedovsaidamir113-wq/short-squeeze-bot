"""
manual_link_checker.py
----------------------
Generates Halal verification links.

- Musaffa: working per-stock public pages (musaffa.com/stock/TICKER/)
- Zoya: app-based, so we link to its web screener (no direct page)

When a ticker is passed, Musaffa builds a direct link.
When empty string is passed (digest footer), returns the base links.
"""

import logging
from src.config import HALAL

logger = logging.getLogger(__name__)


def get_zoya_link(ticker: str = "") -> str:
    """Zoya screener link (app-based — no reliable per-stock web page)."""
    return HALAL["zoya_link_template"]


def get_musaffa_link(ticker: str = "") -> str:
    """Musaffa per-stock link if ticker given, else base screener."""
    if ticker:
        return HALAL["musaffa_link_template"].format(ticker=ticker.upper())
    return "https://musaffa.com/stock-screener/"