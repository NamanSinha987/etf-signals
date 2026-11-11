"""Send the daily summary to Telegram. Silently skipped if credentials are not set."""
from __future__ import annotations

import html
import logging
import os

import pandas as pd
import requests

log = logging.getLogger(__name__)


def format_message(signals: pd.DataFrame, warnings: list[str]) -> str:
    asof = pd.Timestamp(signals["asof"].iloc[0]).strftime("%d %b %Y")
    lines = [f"ETF signals - {asof}", ""]

    held = signals[signals["target_weight"] > 0]
    if held.empty:
        lines.append("Target: 100% cash (no ETF passes the trend filter)")
    else:
        lines.append("Target portfolio:")
        for _, r in held.iterrows():
            lines.append(f"  {r.symbol:<11} {r.target_weight:.0%}  mom {r.momentum:+.1%}  [{r.action}]")
        cash = 1 - held["target_weight"].sum()
        if cash > 0.001:
            lines.append(f"  CASH        {cash:.0%}")

    exits = signals[signals["action"] == "SELL"]
    if not exits.empty:
        lines += ["", "Exit: " + ", ".join(exits["symbol"])]
    if warnings:
        lines += ["", "Warnings:"] + [f"  {w}" for w in warnings]
    return "\n".join(lines)


def telegram_html(text: str, link: str | None = None) -> str:
    """Message as a monospace block; the dashboard link goes below it (links inside <pre> aren't clickable)."""
    body = f"<pre>{html.escape(text)}</pre>"
    if link:
        body += f'\n<a href="{html.escape(link)}">Open dashboard</a>'
    return body


def send_telegram(text: str, link: str | None = None) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.info("Telegram not configured; skipping notification")
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": telegram_html(text, link), "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=20,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        log.error("Telegram send failed: %s", e)
        return False
