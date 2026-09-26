# STATE.md — Current Run State

The agent rewrites this file at the end of every phase and every fix iteration.
Keep it short. This is the first thing read at the start of a session.

```yaml
active_strategy:    BBRSIMeanReversion
strategy_file:      user_data/strategies/BBRSIMeanReversion.py (created at Phase 1)
plan_file:          user_data/strategies/plan/BBRSIMeanReversion.md
config:             configs/strategies/BBRSIMeanReversion.json
current_phase:      1
phase_status:       NOT_STARTED     # NOT_STARTED | IN_PROGRESS | PASS | FAIL | DEAD
iteration:          0               # fix attempts within current_phase (max 3)
freqai_enabled:     false
branch:             rj/strategy/BBRSIMeanReversion  # forked from rj/develop 2026-09-26
journal:            .agent/reports/BBRSIMeanReversion/journal.md
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

2026-09-26 blueprint overhaul (agent-run, user-approved): all plans
restructured to `plan/00-TEMPLATE.md`; 3 plans added (10 DonchianATRBreakout,
11 BBSqueezeBreakout, 12 RelativeStrengthBTC); scored research backlog at
`plan/RESEARCH-BACKLOG.md`; plan-level bug fixes listed in
`plan/INDEX.md` ("blueprint overhaul"); `BBRSIMeanReversion.json` config
recreated early (the reset deleted it; Phase 0 sanctions recreation);
framework review at `.agent/reports/framework-review-2026-09-26.md`.
BBRSIMeanReversion restarts at Phase 1 with the plan's documented
rejection-confirmed fallback ready as the Phase-3 fix.

Pick the next strategy from `user_data/strategies/plan/INDEX.md`.
Recommended order: `BBRSIMeanReversion` first (it is the control), then
`SuperTrendBBCombo`, then the two futures-native plans.

## Last verified result

```yaml
command:            freqtrade backtesting --config configs/strategies/SmokeTestStrategy.json --timerange 20250601-20250701 --cache none  (infra canary — not the strategy)
timerange:          20250601-20250701
trades:             50
profit_factor:      n/a (canary; total -3.95%)
max_drawdown_pct:   6.57
sharpe:             -4.13
funding_fees:       applied, 0 warnings
```

## Portfolio ledger

Twelve plans, none implemented yet. A plan is only real once it passes Phase 7.
Terminal states: `DEAD` (verdict at `.agent/reports/<Name>/DEAD.md`) or
`DEPLOYED` (`FINAL.md`). Cross-run summary: `.agent/reports/PORTFOLIO.md`.

| # | Strategy | TF | Short | Phase | Status |
|---|----------|-----|-------|-------|--------|
| 1 | BBRSIMeanReversion | 15m | yes | 0 | PASS |
| 2 | KeltnerATRReversion | 15m | yes | 0 | NOT_STARTED |
| 3 | VWAPBandReversion | 15m | yes | 0 | NOT_STARTED |
| 4 | EWODipHunter | 15m | no | 0 | NOT_STARTED |
| 5 | MultiMATSL | 15m | yes | 0 | NOT_STARTED |
| 6 | SuperTrendBBCombo | 15m | yes | 0 | NOT_STARTED |
| 7 | ObeliskRSIRegime | 15m | yes | 0 | NOT_STARTED |
| 8 | FundingSkewCarry | 1h | yes | 0 | NOT_STARTED |
| 9 | LiquidationWickFade | 5m | yes | 0 | NOT_STARTED |
| 10 | DonchianATRBreakout | 15m | yes | 0 | NOT_STARTED |
| 11 | BBSqueezeBreakout | 15m | yes | 0 | NOT_STARTED |
| 12 | RelativeStrengthBTC | 15m | yes | 0 | NOT_STARTED |

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
