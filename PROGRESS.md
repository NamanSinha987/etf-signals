# Progress log

Where the project stands, so work can resume on any machine. Updated after every step.
Project background and roadmap: see `CLAUDE.md`. How to run: see `README.md`.

**Last updated:** 12 Nov 2026 (Indian ETF universe drafted; strategy research led by Naman)

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
  2. ~~`backtest.py`: baseline~~ - done 11 Nov 2026, see "Baseline backtest" below.
  3. ~~Dashboard generator~~ - done 11 Nov 2026: `python dashboard.py` ->
     `output/dashboard/index.html` (one self-contained file, ~650 KB, no external libraries).
     Logic in `src/dashboard.py`, page in `src/dashboard_template.html`, 3 tests. Sections: today's
     target + every ETF with the reason it is/isn't held; price vs 200d average chart (ETF picker,
     6M-All); backtest tables + growth and drawdown charts; signal history; data health.
     Light/dark mode, works at phone width.
  4. ~~Cloudflare hosting~~ - done 11 Nov 2026. API token (Pages: Edit) + account ID are GitHub
     secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`. Pages project `etf-signals-naman`
     created (one-time setup workflow, since removed). `daily.yml` now builds the dashboard and
     deploys it to **https://etf-signals-naman.pages.dev** after signals are sent and committed
     (`continue-on-error`, so a Cloudflare problem never blocks signals). Backtest results moved
     to the committed `results/backtest/` so GitHub can show them; re-run `python backtest.py`
     and commit to refresh. **No login (decided 11 Nov 2026):** page is public but unlisted
     (`noindex` + `robots.txt`); add Cloudflare Access (email one-time code, free) once it
     shows real positions or broker data (Phase 4).
  5. ~~Link in Telegram message~~ - done 11 Nov 2026: "Open dashboard" link below the message
     (`dashboard.url` in config.yaml). Telegram is sent before the deploy step, so for ~1 min the
     link shows the previous day's page.
- **Dashboard v2 (wanted, later - 11 Nov 2026):** Naman finds the current page too narrow (only the
  live strategy). Wants a much more functional dashboard: many views, drag-and-drop / rearrangeable
  panels, explore lots of things. Revisit once several strategies exist and one is finalized -
  then the dashboard should compare strategies and data, not just show one. Note: interactive
  exploration (choosing parameters, re-running backtests) needs a live app (e.g. Streamlit/Dash
  locally, or a small hosted app), not just a static page.

### Baseline backtest (11 Nov 2026)

`python backtest.py` (needs `pip install -r requirements-research.txt` or `pip install -e ../backtester`).
Replays the live `generate_signals()` daily, trades only when the held set changes (BUY/SELL,
rebalance to equal weight), next-day open, 10 bps/side. Output in `results/backtest/` (committed; the dashboard reads it).

| 6 Nov 2018 - 9 Nov 2026 | Strategy | NIFTYBEES buy & hold |
|---|---|---|
| CAGR | 24.2% | 12.6% |
| Volatility | 20.9% | 15.5% |
| Sharpe (rf=0) | 1.14 | 0.85 |
| Max drawdown | -28.5% | -36.3% |
| Turnover / year | 13.5x | 0 |

Findings / caveats:
- Holdings change every ~6 trading days (360 change days), mostly #3/#4 rank flips -> high
  turnover (~2.7%/yr cost drag). First improvement to test: a rank buffer (keep until rank > 5)
  or weekly/monthly rebalancing.
- 2019-2023 roughly matched NIFTYBEES; nearly all outperformance is 2024-2026 (gold, silver,
  PSU/CPSE). Concentrated, not a steady edge yet.
- Universe chosen with hindsight (today's liquid ETFs) - optimistic bias.
- MID150BEES: Yahoo only has data from 22 Sep 2026 (currently returns 7 rows) - never selectable
  in the backtest. Bhavcopy archive has it from 10 May 2022; fill from there (one-time import).

## Strategy research (Naman leads from 11 Nov 2026; Claude assists)

- Capital for the next few months: max Rs 2-3 lakh (orders ~Rs 50k-1L). Liquidity floor for the
  universe: median daily traded value >= Rs 1 cr (for tight spreads, not size). Broker: INDmoney
  (can also trade US / European / commodity ETFs).
- **12 Nov 2026 - Indian ETF universe:** `research/scan_etf_liquidity.py` scans every NSE ETF in the
  bhavcopy archive (INF ISIN, series EQ), median traded value over 6 months, names from AMFI's NAV
  file -> `research/etf_liquidity.csv` (309 ETFs trade; 122 >= Rs 1 cr/day). Hand-curated
  `research/universe.csv`: 47 exposures (1 cash, 6 broad, 18 sector, 4 theme, 8 factor,
  2 commodity, 3 bond, 5 international), most liquid ETF per exposure, with the underlying index
  (for longer test history) and notes on overlaps / recent listings. **For Naman to review.**
  Cash should be LIQUIDBEES (earns the overnight rate); backtester currently assumes cash earns 0.
- Next (Naman to decide): global ETF universe (US-listed via INDmoney), index histories for the
  Indian exposures, then test strategy families.

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
