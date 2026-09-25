# Data Download Reference — Verified Dataset Commands (freqtrade 2026.6)

How to build or restore this repo's futures dataset on this machine. Written
2026-09-24 after the working-tree dataset was found deleted and re-downloaded
with explicit user authorization. Cite: `docs/data-download.md` (local docs).

## Network status

**Network IS available** (verified 2026-09-24: `api.binance.com` and
`data.binance.vision` both reachable). The old "machine is offline" note is
obsolete. Restoring this exact dataset with these commands is pre-authorized
by the user (2026-09-24). Anything beyond this dataset — new pairs, new
exchanges, spot mode, trade-data (`--dl-trades`) — still requires asking first.

## The dataset

| Item | Value |
|------|-------|
| Exchange | `binanceusdm` (config: futures / isolated) |
| Pairs (10) | BTC ETH SOL BNB XRP ADA DOGE AVAX LINK LTC — all `/USDT:USDT` |
| OHLCV timeframes | 1m 5m 15m 30m 1h 4h 8h 1d |
| Start | `20220101` (open end -> downloads to now) |
| Candle types | `futures` + **auto-added `mark` and `funding_rate`** in futures mode (docs/data-download.md: "freqtrade will automatically download the necessary candle types ... unless specified otherwise via --candle-types") |
| Format | feather (base config `dataformat_ohlcv`) |
| Location | `user_data/data/binanceusdm/futures/` |

## The verified command

```bash
source .venv/bin/activate
# MANDATORY: --config per repo rules. This config carries the 10-pair
# whitelist and futures mode; download-data reads pairs from it.
setsid nohup freqtrade download-data \
  --config configs/strategies/SmokeTestStrategy.json \
  --timeframes 1m 5m 15m 30m 1h 4h 8h 1d \
  --timerange 20220101- \
  > results/download.log 2>&1 < /dev/null &
```

**Why setsid**: the bash tool kills its whole process group on timeout — a
plain `nohup ... &` still dies with it. `setsid` detaches the session so the
download survives. Launch in one command that returns immediately; poll
progress with separate quick commands (never `sleep` in the launching call).

**Resume behavior**: `download-data` is incremental — it skips data already
on disk and extends from where it stopped (docs: "iteratively increase the
amount of data stored"). If a download dies mid-way, relaunch the same
command; nothing is lost. Do NOT use `--erase` unless corruption is proven.

**Incremental top-up later** (e.g. after a month of dry-running):
```bash
freqtrade download-data --config configs/strategies/SmokeTestStrategy.json \
  --timeframes 15m 1m --timerange 20260701-
```

## Funding data — the gotcha that no longer applies

ENVIRONMENT.md gotcha #13 described repairing *-8h-funding_rate.feather
files copied to *-1h names. A **fresh 2026.6 download writes funding files
directly at the timeframe freqtrade expects** (`funding_fee_timeframe`
default 1h), so the manual copy repair is not needed for fresh downloads.
Verify instead by absence of failure:

- `ls user_data/data/binanceusdm/futures/*-1h-funding_rate.feather | wc -l`
  must equal the pair count (10)
- a canary backtest prints no
  `No history for <PAIR>, funding_rate, 1h found` warnings
- canary trades carry non-zero `funding_fees`

If the warnings ever reappear, funding is silently free again and every
futures result is optimistic — re-check before trusting any backtest.

## Post-download verification (run all, in order)

```bash
# 1. Inventory: every pair x timeframe present, sane candle counts
freqtrade list-data --config configs/strategies/SmokeTestStrategy.json --show-timerange

# 2. Funding + mark present
ls user_data/data/binanceusdm/futures/ | grep -c funding_rate    # >= 10 files
ls user_data/data/binanceusdm/futures/ | grep -c mark            # >= 10 files

# 3. Infra canary (needs user_data/strategies/SmokeTestStrategy.py)
freqtrade backtesting --config configs/strategies/SmokeTestStrategy.json \
  --timerange 20250601-20250701 --cache none \
  2>&1 | grep -vE " INFO - " | tail -15
# Expect: results table, > 0 trades, NO funding warnings, and non-zero
# funding_fees on most trades held across a funding timestamp.
```

After verification, update the Data section of `.agent/ENVIRONMENT.md`
(common date range, candle counts) — never leave it stale.

## Cost/size expectations

~2-3 GB, tens of minutes, mostly the 1m files (≈2.5M candles per pair-year at
1m). The 1m set exists solely for `--timeframe-detail 1m` realism passes;
if disk pressure ever forces a cut, 1m is the only candidate — but then the
Phase 4 realism pass degrades and must be recorded as SKIPPED.
