# STATE.md — Current Run State

The agent rewrites this file at the end of every phase and every fix iteration.
Keep it short. This is the first thing read at the start of a session.

```yaml
active_strategy:    (none — pick from user_data/strategies/plan/INDEX.md)
strategy_file:      (none)
plan_file:          (none)
config:             (none yet — created at Phase 0/1 as configs/strategies/<Name>.json)
current_phase:      0
phase_status:       NOT_STARTED     # NOT_STARTED | IN_PROGRESS | PASS | FAIL | DEAD
iteration:          0               # fix attempts within current_phase (max 3)
freqai_enabled:     false
branch:             rj/develop      # framework branch; create rj/strategy/<Name> per strategy
journal:            (created at Phase 0 as .agent/reports/<Name>/journal.md)
```

Reset on 2026-09-26 (user-approved full reset): the in-progress BBRSIMeanReversion
run (Phase 4 FAIL, iter 1) was removed — strategy file, config and per-strategy
reports deleted. The Phase 4 diagnosis survives in `.agent/JOURNAL.md`
(2026-09-24 Phase 4 entry): PF 0.615, root cause = entry fires on the knife
candle with no confirmation, pre-ranked fix = rejection-confirmed entry.
When this plan is picked up again, restart from Phase 1 and re-propose that
fix at Phase 3.

Framework v2 (Kotegawa risk layer, protections, `--timeframe-detail 1m`,
`--cache none`, `--enable-protections` on all Phase 4+ backtests,
per-strategy journals, orchestrator skill, tool-level guardrails,
`.agent/scripts/framework-check.sh`) lives on `rj/develop`. Future strategy
branches fork from it.

Pick the next strategy from `user_data/strategies/plan/INDEX.md`.
Recommended order: `BBRSIMeanReversion` first (it is the control), then
`SuperTrendBBCombo`, then the two futures-native plans.

## Last verified result

```yaml
command:            (none run yet)
timerange:          -
trades:             -
profit_factor:      -
max_drawdown_pct:   -
sharpe:             -
funding_fees:       -
```

## Portfolio ledger

Nine plans, none implemented yet. A plan is only real once it passes Phase 7.
Terminal states: `DEAD` (verdict at `.agent/reports/<Name>/DEAD.md`) or
`DEPLOYED` (`FINAL.md`). Cross-run summary: `.agent/reports/PORTFOLIO.md`.

| # | Strategy | TF | Short | Phase | Status |
|---|----------|-----|-------|-------|--------|
| 1 | BBRSIMeanReversion | 15m | yes | 0 | NOT_STARTED |
| 2 | KeltnerATRReversion | 15m | yes | 0 | NOT_STARTED |
| 3 | VWAPBandReversion | 15m | yes | 0 | NOT_STARTED |
| 4 | EWODipHunter | 15m | no | 0 | NOT_STARTED |
| 5 | MultiMATSL | 15m | yes | 0 | NOT_STARTED |
| 6 | SuperTrendBBCombo | 15m | yes | 0 | NOT_STARTED |
| 7 | ObeliskRSIRegime | 15m | yes | 0 | NOT_STARTED |
| 8 | FundingSkewCarry | 1h | yes | 0 | NOT_STARTED |
| 9 | LiquidationWickFade | 5m | yes | 0 | NOT_STARTED |

## Infra baseline (verified 2026-09-24, do not re-verify unless something breaks)

| Check | Result |
|-------|--------|
| Per-strategy config isolation | loads only `<Name>.json` + `base.futures.json`; never `config.json` |
| `list-strategies` | OK (no DUPLICATE NAME) |
| Canary backtest | 50 trades on 20250601-20250701, runs clean |
| `lookahead-analysis` | runs, `has_bias = No` (needs `--pairs`) |
| `recursive-analysis` | runs, flags indicator drift at low warm-up |
| `hyperopt` (5 epochs) | runs clean |
| `backtesting-analysis` | runs, reads exported zip |
| Funding fees | **applied** — 39/50 canary trades carry non-zero funding |
| Export path | `results/backtests/*.zip` via `--backtest-directory` |

`user_data/strategies/SmokeTestStrategy.py` is the infra canary. If it fails,
the problem is the environment, not the strategy.
`.agent/scripts/framework-check.sh` verifies all of the above in one run.
