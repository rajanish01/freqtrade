# STATE.md — Current Run State

The agent rewrites this file at the end of every phase, maze tier, and fix
iteration. Keep it short. This is the first thing read at the start of a
session.

```yaml
active_strategy:    (none)                     # pick the next pilot from the portfolio ledger below
strategy_file:      (none)
plan_file:          (none)
config:             (none)
current_phase:      (none)                     # 0-8, or 4M with tier sub-state below
phase_status:       NOT_STARTED                # NOT_STARTED | IN_PROGRESS | PASS | FAIL | DEAD
maze:               (not initialized)          # once in the maze: tier: T0-T5, ledger: .agent/reports/<Name>/maze/ledger.csv
freqai_enabled:     false
branch:             rj/framework/maze          # forked from rj/develop 2026-09-27
journal:            .agent/JOURNAL.md
final_report:       (pending)
```

## Reset — 2026-09-28 (framework v3: the MAZE)

User-directed reset of all previous plan runs, on a fresh branch
`rj/framework/maze` forked from `rj/develop` (`5812a4134`). What changed:

- **Framework v3 — MAZE** (`.agent/phases/04M-MAZE.md`): from Phase 4
  onward there is no fixed 3-iteration budget. A failed Phase-4 baseline (T0)
  enters an exhaustive, gate-scored variant tree (T0-T5: structural moves ->
  hyperopt -> confirm -> robustness -> OOS -> one-shot vault). New tooling:
  `.agent/scripts/maze.py` (ledger/tree/genome-staging/vault) and
  `.agent/scripts/hyperopt/MazeGateLoss.py` (gate-aligned hyperopt loss).
  Phases 0-3 unchanged; 5 and 7 are now T2/T4 mechanics references.
- **Policy change (user-approved in the MAZE plan):** risk NUMBERS
  (stoploss, leverage cap, protection values) are a bounded hyperopt search
  dimension from T2 onward, formula-gated by K2/K7 and scored every epoch by
  MazeGateLoss. The risk MECHANISM (sizing structure, half-capital reserve,
  protection methods, K4 payoff floor) is unchanged and still never ML.
- **Prior runs reset (archived, not deleted):**
  - `BBRSIMeanReversion` — DEAD 2026-09-26 (terminal verdict stands, never
    deleted), **user-directed reset 2026-09-28**: re-enter via the MAZE from
    Phase 0/1 (rebuild the strategy from its plan). Archived record at
    `.agent/reports/_archive/pre-maze-2026-09-27/BBRSIMeanReversion/`
    (DEAD.md, journal, postmortem). Its cost-floor lesson (a +0.2% median
    reversion win cannot clear the 0.1% round-trip cost floor at 15m) is the
    T0/T1 failure mode the maze starts from — the confirmation-filter and
    timeframe moves its lesson called for were never tried pre-maze.
  - `DonchianATRBreakout` — Phase 4 FAIL iter 1 (PF 0.9068, DD 45.65%, cost
    floor: raw edge +36.6 USDT consumed ~10x by fees). Archived at
    `.agent/reports/_archive/pre-maze-2026-09-27/DonchianATRBreakout/`
    (strategy .py as .py.txt, journal, postmortem). Its Phase-4 postmortem is
    the T0 failure mode a future maze run would start from; its plan
    (`user_data/strategies/plan/DonchianATRBreakout.md`) remains live.
  - Backtest/check zips archived at `results/_archive/pre-maze-2026-09-27/`.
- **Verified this build (see ENVIRONMENT.md gotchas #8, #14-18):** config
  overrides strategy (not the reverse) for timeframe/stoploss/ROI/trailing/
  max_open_trades; nested `add_config_files` chaining works to 5 levels;
  `--enable-protections` works during hyperopt; custom `space="risk"`
  hyperopt spaces work; `HyperOpt.stoploss_space()` bounds work; zip stats
  timestamps are ms; `max_open_trades_setting` vs the pairlist-capped display
  stat; "No good result found" is cosmetic when no epoch clears every gate
  (MazeGateLoss docstring).

## Portfolio ledger

Twelve plans. A plan is only real once it passes the maze's T5 vault + Phase
8. Terminal states: `DEAD` (verdict at `.agent/reports/<Name>/DEAD.md`) or
`DEPLOYED` (`FINAL.md`). Cross-run summary: `.agent/reports/PORTFOLIO.md`.

| # | Strategy | TF | Short | Phase | Status |
|---|----------|-----|-------|-------|--------|
| 1 | BBRSIMeanReversion | 15m | yes | 0 | RESET (DEAD 2026-09-26, archived; user-directed reset 2026-09-28 — re-enter via MAZE, Phase 0/1 rebuild) |
| 2 | KeltnerATRReversion | 15m | yes | 0 | NOT_STARTED |
| 3 | VWAPBandReversion | 15m | yes | 0 | NOT_STARTED |
| 4 | EWODipHunter | 15m | no | 0 | NOT_STARTED |
| 5 | MultiMATSL | 15m | yes | 0 | NOT_STARTED |
| 6 | SuperTrendBBCombo | 15m | yes | 0 | NOT_STARTED |
| 7 | ObeliskRSIRegime | 15m | yes | 0 | NOT_STARTED |
| 8 | FundingSkewCarry | 1h | yes | 0 | NOT_STARTED |
| 9 | LiquidationWickFade | 5m | yes | 0 | NOT_STARTED |
| 10 | DonchianATRBreakout | 15m | yes | 4 | RESET (pre-maze FAIL iter 1; re-enter via MAZE) |
| 11 | BBSqueezeBreakout | 15m | yes | 0 | NOT_STARTED |
| 12 | RelativeStrengthBTC | 15m | yes | 0 | NOT_STARTED |

## Infra baseline (verified 2026-09-24; maze tooling verified 2026-09-28 — do not re-verify unless something breaks)

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
| MAZE tooling | `maze.py` full lifecycle verified end-to-end (init/node/run/hyperopt/promote/mark/status/tree/gates/vault); promoted-epoch score == source hyperopt epoch score; `MazeGateLoss` gate gradient verified live |

`user_data/strategies/SmokeTestStrategy.py` is the infra canary. If it fails,
the problem is the environment, not the strategy.
`.agent/scripts/framework-check.sh` verifies all of the above in one run.
