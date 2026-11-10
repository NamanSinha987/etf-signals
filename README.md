# etf-signals

Daily signal pipeline for NSE ETFs. Runs on GitHub Actions after market close, fetches prices, runs the strategy, saves signals and sends a Telegram summary. **Signals only - no orders are placed.**

```
config.yaml                 universe + strategy parameters (edit this, not the code)
pipeline.py                 entry point: data -> signals -> save -> notify
src/data.py                 Yahoo Finance fetch + NSE bhavcopy fallback, CSV storage
src/strategy.py             trend-filtered momentum rotation
src/notify.py               Telegram message
.github/workflows/daily.yml cron job (18:47 IST, Mon-Fri): tests -> pipeline -> commit
.github/workflows/tests.yml runs the tests on every code push
tests/                      offline tests (no network), run with: python -m pytest -q
PROGRESS.md                 current status and next step
data/prices.csv             price history (created on first run, committed daily)
signals/latest.csv          today's signals
signals/history.csv         every day's signals (your paper-trading log)
```

## Strategy (Phase 1 placeholder)

1. Eligible only if close > 200-day SMA.
2. Rank eligible ETFs by 6-month (126-day) return.
3. Hold the top 3, equal weight; empty slots stay in cash.

Actions are relative to the previous day: `BUY` (new), `HOLD`, `SELL` (dropped out).

## Run locally (Windows)

```powershell
cd D:\NotWindows\Quant2.0\etf-signals
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
python pipeline.py --no-notify
```

The first run backfills history from 2018 for all ETFs (takes ~30 seconds).

## Put it on GitHub Actions

1. Create a **private** repo on GitHub (e.g. `etf-signals`), empty (no README, no .gitignore).
2. From this folder (the local git repo already exists with the first commit):
   ```powershell
   git remote add origin https://github.com/<you>/etf-signals.git
   git push -u origin main
   ```
3. In the repo: **Actions** tab -> enable workflows -> open "Daily ETF signals" -> **Run workflow** to test it once manually.
4. Check the run log. If the price fetch fails from GitHub's servers, tell Claude - the fallback source can be changed.

## Telegram alerts (optional, ~5 min)

1. In Telegram, message **@BotFather** -> `/newbot` -> copy the bot token.
2. Send any message to your new bot, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `chat.id`.
3. In the GitHub repo: **Settings -> Secrets and variables -> Actions** -> add
   `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`.

Without these the pipeline still runs; the summary is just printed in the Actions log.

## Notes

- Cron is in UTC and GitHub can start scheduled runs late; signals are end-of-day, so that's fine.
- On market holidays the run finds no new bar and re-issues the previous day's signals without changing actions.
- A >25% one-day move or missing bar is flagged as a warning in the message.
- Moving to automated orders later needs a VPS with a static IP (SEBI rule) - the same code runs there.
