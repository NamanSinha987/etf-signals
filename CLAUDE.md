# Project context for Claude

Personal ETF trading environment for Naman. Daily end-of-day pipeline on NSE ETFs:
fetch data -> run strategies -> generate signals -> notify. **Signals only - no automated
order placement for now.** Low infra budget.

**Current state and next step: see `PROGRESS.md`. Update it after every completed step.**

## Decisions so far
- Runs on **GitHub Actions** (cron 13:17 UTC = 18:47 IST, Mon-Fri), private repo.
  Runners have no persistent disk, so data and signals are CSVs committed back to the repo.
- Automated execution later needs a VPS with a **static IP** (SEBI retail algo framework,
  enforced from 1 Apr 2026). Keep code portable (plain Python, config in YAML) for that move.
- Data: Yahoo Finance (`<SYMBOL>.NS`, split-adjusted, used for backfill + last-10-day refresh),
  NSE CM bhavcopy (UDiFF zip) as fallback for the latest day. NSE often blocks cloud IPs -
  verify from GitHub Actions before relying on it.
- Strategy (placeholder, Phase 1): close > 200d SMA filter, rank by 126d return, hold top 3
  equal weight, rest cash. Parameters in `config.yaml`.
- Universe: 12 liquid NSE ETFs in `config.yaml` (broad, sector, gold/silver, international).

## Long-term direction (decided 10 Nov 2026)
Naman wants this to grow beyond price-only strategies: fundamentals, component-wise
(index constituents -> ETF-level features such as breadth, aggregate valuation, earnings
growth), multiple robust strategies. Phase 1 deliberately stays price-only to prove the
end-to-end pipeline. Storage: git-committed CSVs for now; move to object storage
(e.g. Cloudflare R2 / S3, Parquet) once constituent / fundamental / bhavcopy data is added.
Keep all storage behind `load_*` / `save_*` functions so that move touches one module.

## Roadmap
1. **Phase 1 (done 9 Nov 2026):** minimal pipeline + workflow + Telegram notify.
   Pending: move `daily.yml` into `.github/workflows/`, push to GitHub, test a manual run.
2. **Phase 2:** backtest harness that reuses `src/strategy.py` (no separate research code),
   with costs/slippage, CAGR / Sharpe / max DD / turnover; `signals/history.csv` is the
   paper-trading log.
3. **Phase 3:** Claude in the loop - news fetch, LLM summaries + sentiment per ETF/sector
   stored daily as a feature, daily brief. Via Claude API from Python or
   `anthropics/claude-code-action`. Don't backtest LLM sentiment on historical news
   (look-ahead via model knowledge); only use scores collected live.
4. **Phase 4:** broker API execution, VPS + static IP, position sizing, kill-switch.

## Conventions
- Separate modules: `src/data.py` (data), `src/strategy.py` (signals), `src/notify.py` (output).
- Config in YAML, not hardcoded. Each run must be reproducible from stored data.
- `python pipeline.py --no-fetch --no-notify` runs offline on stored data for testing.
- Windows laptop; project at `D:\NotWindows\Quant2.0\etf-signals`.
