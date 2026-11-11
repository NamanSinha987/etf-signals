"""Telegram message HTML: text escaped inside <pre>, dashboard link clickable below it."""
from src.notify import telegram_html


def test_link_goes_below_the_block():
    body = telegram_html("ETF signals", "https://example.pages.dev")
    assert body == '<pre>ETF signals</pre>\n<a href="https://example.pages.dev">Open dashboard</a>'


def test_no_link_and_text_escaped():
    assert telegram_html("move < -25% & up") == "<pre>move &lt; -25% &amp; up</pre>"
