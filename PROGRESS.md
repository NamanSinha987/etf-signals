# Progress log

Where the project stands, so work can resume on any machine. Updated after every step.
Project background and roadmap: see `CLAUDE.md`. How to run: see `README.md`.

**Last updated:** 10 Nov 2026

## Resume on a new machine

1. Install Python 3.12 (`.python-version`; GitHub Actions uses 3.12, laptop still has 3.9.2).
2. Get the code: `git clone https://github.com/<you>/etf-signals.git` (once pushed).
3. `python -m venv .venv` -> `.venv\Scripts\activate` -> `pip install -r requirements.txt -r requirements-dev.txt`
4. `git pull` first (the bot commits data daily), then `python -m pytest -q` (offline, ~5 s).
5. Offline run: `python pipeline.py --no-fetch --no-notify`; with fetching: `python pipeline.py --no-notify`.
6. Continue from **Next step** below.

## Current status

Phase 1 hardening finished. Local git repo created with the first commit on `main`.
Pushed to GitHub on 10 Nov 2026: https://github.com/NamanSinha987/etf-signals (private).
(Push needed a new Git for Windows / token - GitHub doesn't accept account passwords for git.)

## Next step

**Phase 1 is live (10 Nov 2026).** Watch a week of scheduled runs (step 6e below), then start
Phase 2 (backtest harness).

_Previous step notes:_ Actions tab -> run "Daily ETF signals" manually -> check the log
(does Yahoo work from GitHub? does the bhavcopy fallback get blocked?). Add Telegram secrets
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` (README has the steps).

After that: watch a week of daily runs, then start **Phase 2 (backtest harness)** - see CLAUDE.md.

## Remaining steps

- [x] 6b. Push to GitHub (10 Nov 2026)
- [x] 6c. First manual run on GitHub (10 Nov 2026, 17:23 IST): green in 22 s, tests passed,
        Yahoo works from GitHub, bot committed data. No 10 Nov bar yet (run was before the
        18:47 schedule; possibly an NSE holiday) - so the bhavcopy fallback is still unverified.
- [x] 6d. Telegram secrets added; message received on 10 Nov 2026 17:57 IST (incl. the
        "NO NEW PRICES" warning).
- [ ] 6e. Watch the scheduled 18:47 IST runs for a week (Telegram message + "Daily update"
        commit each weekday). Check whether 10 Nov gets a bar (holiday or not) and whether
        the bhavcopy fallback ever kicks in from GitHub.
- [ ] Install Python 3.12 on the laptop (Naman)
- [ ] Phase 2: backtest harness reusing `src/strategy.py`; consider NSE bhavcopy parquet data (below)

## Done

| Date | Step | What and why |
|---|---|---|
| 9 Nov 2026 | Phase 1 code | Pipeline, strategy, Telegram notify, GitHub workflow written. |
| 9 Nov 2026 | 1. Bug fixes | `fetch_yahoo` crashed for a single ticker (yfinance >= 0.2.48 column format), so a newly added ETF never got its history; backfill now also retries symbols with only recent rows. Stale-data warning never fired because `last_bar` was computed after forward-fill. Both verified. |
| 9 Nov 2026 | 2a. Pinned versions | `requirements.txt` pinned to tested versions (pandas 2.3.3, numpy 2.0.2, pyyaml 6.0.2, requests 2.32.5, yfinance 1.2.0) so GitHub installs the same as the laptop. |
| 9 Nov 2026 | 2b. Line endings | `.gitattributes` stores text as LF so CSVs written on Windows and Linux don't produce whole-file diffs. |
| 9 Nov 2026 | 3. Reliable fetch | `fetch_yahoo_retry` re-requests symbols that came back empty (3 tries, 10 s / 20 s waits). `today_ist()` replaces `date.today()` so GitHub's UTC clock doesn't matter. Message starts its warnings with "NO NEW PRICES" when a weekday run gets no bar for today. |
| 9 Nov 2026 | 4. Splits | `adjusted_symbols` compares Yahoo's re-fetched last-10-day closes with stored Yahoo closes on the same dates; >2% difference means Yahoo re-adjusted history (split/bonus), so that symbol's full history is re-downloaded and replaced. |
| 10 Nov 2026 | 5. Tests + CI | 15 offline tests in `tests/` (strategy picks/actions/stale bar, merge, bhavcopy parse, single-ticker Yahoo, retry, split resync, partial backfill, pipeline re-run and no-new-prices alert). `tests.yml` runs them on every code push; `daily.yml` runs them before the pipeline so broken code can't send signals. pytest pinned in `requirements-dev.txt`. Fixed a pandas FutureWarning in `_append_history`. |
| 10 Nov 2026 | 6a. Go-live prep | `daily.yml` moved to `.github/workflows/`, `.python-version` = 3.12, README updated, `git init` on `main` with first commit (includes `data/prices.csv` 2018 -> 9 Nov 2026). |

## Data

- `data/prices.csv` - daily OHLCV for the 12 ETFs, 2018-01-01 onward, from Yahoo (`source` column).
  Created/updated by `pipeline.py`; committed daily by the GitHub bot. Safe to delete - the next
  run rebuilds it.
- `signals/latest.csv`, `signals/history.csv` - today's signals and the paper-trading log.
- **Outside this project:** `D:\NotWindows\Quant2.0\data\export\` has NSE bhavcopy parquet files,
  `cm_2021..2026` and `fo_2021..2026` (1.2 GB, up to 2 Nov 2026). All 12 ETFs present in CM (series EQ).
  Gaps: ITBEES, MID150BEES, PHARMABEES, SILVERBEES start 10 May 2022; MON100 starts 16 Jun 2021 -
  check for missing files or old symbol names. Too big for the repo; intended for Phase 2 backtests
  and cross-checking Yahoo.

## Phase 2 - backtesting (started 10 Nov 2026)

- Backtester is a **separate public library** at `D:\NotWindows\Quant2.0\backtester` (own repo,
  own PROGRESS.md). v0.1.0 done and tested; installed here in editable mode
  (`pip install -e ../backtester`). Not needed by the daily pipeline - research only.
- **Data problem found:** Yahoo prices are 10x-100x too small for a few days around unit splits:
  19-20 Dec 2019 (NIFTYBEES, BANKBEES, GOLDBEES, HNGSNGBEES, PSUBNKBEES) and 17-18 Jun 2021
  (MON100). Doesn't affect live signals (200-day lookback) but breaks any backtest over those
  dates. SILVERBEES -19% / -23% on 30 Jan / 2 Feb 2026 is real (silver crash).
- **Fixed 11 Nov 2026:** `fix_scale_glitches` in `src/data.py` rescales bars 7.9x-12.6x (or
  ~100x) off their +-5-day median and marks them `source = yahoo_fixed` (12 rows repaired;
  `adjusted_symbols` ignores fixed rows). Runs on every update. NIFTYBEES buy-and-hold now:
  CAGR 11.8%, vol 15.2%, max DD -36.3% (was vol 306%, DD -90%).
- **Next:** (1) Naman pushes the backtester repo; (2) decide dashboard hosting (see below);
  (3) `backtest.py` here: baseline result of the current strategy vs NIFTYBEES.
- **Dashboard (decided 11 Nov 2026):** static HTML page with interactive charts, rebuilt by the
  daily GitHub run, hosted **privately on Cloudflare Pages behind Cloudflare Access** (one-time
  email code login), link in the Telegram message. Plan:
  1. ~~Naman: push backtester repo~~ - done 11 Nov 2026 (public, tag v0.1.0).
  2. `backtest.py`: baseline of the current strategy vs NIFTYBEES (main dashboard content).
  3. Dashboard generator, built and viewed locally first.
  4. Naman: free Cloudflare account + API token as GitHub secrets; then deploy step + Access.
  5. Link in Telegram message.

## Decisions

- **10 Nov 2026 - storage:** keep data in the GitHub repo (CSV, ~1.6 MB, grows <1 KB/day; git
  history = point-in-time record). Move to object storage (R2/S3, Parquet) when constituent,
  fundamental or bhavcopy data is added. The 1.2 GB bhavcopy archive never goes in this repo.
- **10 Nov 2026 - direction:** project will grow into fundamental and component-wise strategies
  (see CLAUDE.md "Long-term direction"). Price-only for now, to test the pipeline end to end.

## Open issues / notes

- **GitHub schedule lateness:** the first scheduled run (10 Nov, due 18:47 IST) started ~7 h late
  (Telegram at 01:59 IST). Fixed the consequence on 11 Nov: `expected_session()` picks the
  session to look for (today from 16:00 IST, else the previous weekday) instead of the calendar
  date. If runs keep arriving after ~22:00, add an external trigger (e.g. cron-job.org calling
  `workflow_dispatch`) - watch the Telegram times this week.

- Laptop Python is 3.9.2, GitHub uses 3.12 - install 3.12 locally. Tests pass on 3.9; CI checks 3.12.
- Yahoo and the NSE bhavcopy fallback are untested from GitHub's servers (both sometimes block cloud IPs).
- Don't commit locally generated `data/` or `signals/` changes - the bot owns them; always `git pull` first.
