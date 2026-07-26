# Phase 0: Data & Infra Readiness

## Why this phase exists
Every downstream phase blames the strategy when a command fails. Most early
failures are actually config or data problems. This phase separates the two,
once, before any strategy code is written.

## Prerequisite
A strategy plan exists. Either:
- one of the nine plans in `user_data/strategies/plan/` (see `INDEX.md`), or
- a filled-in `.agent/prompts/strategy-idea.md`.

If neither exists, or the idea file still has template placeholders, STOP and
ask which strategy to build.

Also confirm `configs/strategies/<Name>.json` exists for it. If not, create it
by copying an existing one and changing `strategy`, `timeframe` and
`pair_whitelist`. Keep `add_config_files: ["../base.futures.json"]`.

## Your Task
Run four checks. Modify no strategy code.

### Check 1 — data exists for the requested pairs and timeframe
```bash
freqtrade list-data --config configs/strategies/$STRAT.json --show-timerange
```
Confirm every pair in the strategy idea appears, at the strategy's timeframe,
covering the IS+OOS range in `.agent/ENVIRONMENT.md`.

If a requested pair or timeframe is missing: STOP. Do not run
`download-data` (machine is offline). Report the gap and ask the user whether
to drop the pair or change the timeframe.

### Check 2 — config isolation and pair notation

```bash
freqtrade list-strategies --config configs/strategies/<Name>.json 2>&1 | grep "Using config"
```
Exactly two configs must be listed: the strategy config and `../base.futures.json`.
If `config.json` or `user_data/config.json` appears, **STOP** — a `--config` is
missing somewhere and the run is contaminated.

Then confirm `exchange.pair_whitelist` uses futures notation (`BTC/USDT:USDT`,
never `BTC/USDT`) and matches the pairs in the plan that actually have data.

### Check 3 — infra canary
```bash
freqtrade backtesting --config configs/strategies/$STRAT.json \
  --timerange 20250601-20250701 \
  2>&1 | grep -vE " INFO - " | tail -15
```
This must produce a results table with a non-zero trade count.

- Canary PASSES -> infra is good. Any later failure is your strategy's fault.
- Canary FAILS -> infra is broken. Do NOT write strategy code. Diagnose the
  config against `.agent/ENVIRONMENT.md` gotchas and report to the user.

### Check 4 — confirm the IS/OOS split
State the two timeranges you will use, from `.agent/ENVIRONMENT.md`.
Confirm they do not overlap. You will be held to this split for the whole run.

### Check 5 — funding data is present (futures only)

```bash
ls user_data/data/binanceusdm/futures/*-1h-funding_rate.feather | wc -l
```
Must be 10. If it is 0, funding fees are silently zero and every backtest will
overstate profit — see `.agent/ENVIRONMENT.md` gotcha #13 for the one-line fix.

Also confirm the canary run printed no
`No history for <PAIR>, funding_rate, 1h found` warnings.

## DO NOT
- Create or edit any strategy file
- Run `freqtrade download-data`
- Edit `configs/*.json` unless a check failed and you have named the exact gotcha
- Proceed to Phase 1 with any check failing

## Exit Criteria
- [ ] Every pair in the plan has data at the strategy timeframe
- [ ] Only the strategy config + base config loaded — no `config.json`
- [ ] `pair_whitelist` uses futures notation and matches the plan
- [ ] Canary backtest produced a results table with > 0 trades
- [ ] IS and OOS timeranges stated and non-overlapping
- [ ] 10 funding-rate files present, no funding warnings
- [ ] `.agent/STATE.md` updated: `current_phase: 1`

## Output Format

```
PHASE 0 COMPLETE
─────────────────────────
Pairs with data:   <list>
Pairs missing:     <list or "none">
Timeframe:         <tf>
IS window:         <timerange>
OOS window:        <timerange>
Canary trades:     <N>
─────────────────────────
Data check:    PASS/FAIL
Notation check:PASS/FAIL
Canary check:  PASS/FAIL
Split check:   PASS/FAIL
─────────────────────────
VERDICT: PASS (proceed to Phase 1) / FAIL (reason)
```
