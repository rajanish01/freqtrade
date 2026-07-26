# STATE.md — Current Run State

The agent rewrites this file at the end of every phase and every fix iteration.
Keep it short. This is the first thing read at the start of a session.

```yaml
active_strategy:    (none selected)
strategy_file:      (not yet created)
plan_file:          user_data/strategies/plan/<Name>.md
config:             configs/strategies/<Name>.json
current_phase:      0
phase_status:       NOT_STARTED      # NOT_STARTED | IN_PROGRESS | PASS | FAIL
iteration:          0                # fix attempts within current_phase (max 3)
freqai_enabled:     false
```

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

## Open issues

- `.agent/prompts/strategy-idea.md` is still the blank template. It is only
  needed for a *new* idea — the nine plans above are already specified.
- `user_data/strategies/` currently contains only `RegimeAdaptiveTrend.py`,
  `RegimeAdaptiveTrendV2.py` (pre-existing, outside this workflow) and
  `SmokeTestStrategy.py` (the Phase 0 canary — leave it in place).

## Infra baseline (verified 2026-07-26, do not re-verify unless something breaks)

| Check | Result |
|-------|--------|
| Per-strategy config isolation | loads only `<Name>.json` + `base.futures.json`; never `config.json` |
| `list-strategies` | OK (no DUPLICATE NAME) |
| Canary backtest | 50 trades on 20250601-20250701, runs clean |
| `lookahead-analysis` | runs, `has_bias = No` (needs `--pairs`) |
| `recursive-analysis` | runs, flags indicator drift at low warm-up |
| `hyperopt` (5 epochs) | runs clean |
| `backtesting-analysis` | runs, reads exported zip |
| Funding fees | **applied** — 32/42 canary trades carry non-zero funding |
| Export path | `results/backtests/*.zip` via `--backtest-directory` |

`user_data/strategies/SmokeTestStrategy.py` is the infra canary. If it fails,
the problem is the environment, not the strategy.
