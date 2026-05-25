# Short Squeeze Signal Bot

A Telegram bot that scans Finviz for short squeeze candidates and sends weekly signals.

## Strategy
- Short Float tiers: 20%+, 25%+, 30%+
- Short Ratio > 4
- Stock above SMA 50 (no downtrend)
- Within 15% of 100-day high
- Entry signal when 100-day high breaks
- Halal compliance check (manual via Zoya link)

## Stack
- Python 3.12
- finvizfinance, yfinance, pandas
- python-telegram-bot
- APScheduler
- ScraperAPI (proxy for Finviz access from blocked regions)

## Disclaimer
This bot provides educational signals only. **Not financial advice.**
Always do your own research before trading.

## Status
🚧 Under development.