# PORTFOLIO.md — Cross-Run Summary

One row per strategy plan. Updated after every terminal verdict (pass or fail).
This is the portfolio-level view: what was built, what died, and why.

The honest prior is that **most plans will fail**. A plan that dies at Phase 4
with a clear postmortem and a final verdict is a successful use of this
process — it is evidence, not waste.

## Status

| # | Strategy | TF | Short | Phase | Verdict | Report |
|---|----------|-----|-------|-------|---------|--------|
| 1 | BBRSIMeanReversion | 15m | yes | 4 | DEAD | .agent/reports/BBRSIMeanReversion/DEAD.md |
| 2 | KeltnerATRReversion | 15m | yes | 0 | NOT_STARTED | — |
| 3 | VWAPBandReversion | 15m | yes | 0 | NOT_STARTED | — |
| 4 | EWODipHunter | 15m | no | 0 | NOT_STARTED | — |
| 5 | MultiMATSL | 15m | yes | 0 | NOT_STARTED | — |
| 6 | SuperTrendBBCombo | 15m | yes | 0 | NOT_STARTED | — |
| 7 | ObeliskRSIRegime | 15m | yes | 0 | NOT_STARTED | — |
| 8 | FundingSkewCarry | 1h | yes | 0 | NOT_STARTED | — |
| 9 | LiquidationWickFade | 5m | yes | 0 | NOT_STARTED | — |

Verdict values: `DEPLOYED` (passed Phase 7, dry-run candidate — link FINAL.md)
| `DEAD` (hypothesis not supported — link DEAD.md) | `NOT_STARTED`.

## Family scorecard

Band-reversion vs trend vs futures-native: if one family produces every
deployment and another produces every death, that is a portfolio-level finding
— record it here after each verdict.

| Family | Plans | Deployed | Dead | Lesson so far |
|--------|-------|----------|------|---------------|
| band reversion | 3 (1,2,3) | 0 | 0 | — |
| dip buying | 1 (4) | 0 | 0 | — |
| trend / trend+band | 3 (5,6,7) | 0 | 0 | — |
| futures-native | 2 (8,9) | 0 | 0 | — |

## Lessons ledger

One line per terminal verdict. Newest at the bottom.

- (2026-09-24, preserved from the reset BBRSIMeanReversion attempt — full run
  not completed, diagnosis survives in `.agent/JOURNAL.md`): band-reversion
  entries that fire on the knife candle without confirmation grind ~28h into
  a distant stop; 70% win rate with inverted payoff (loss 3.9x win) loses
  decisively. When plan 1 is picked up, restart from Phase 1 and propose the
  rejection-confirmed entry at Phase 3.
- (2026-09-26, BBRSIMeanReversion — terminal, plan 1 DEAD, three Phase-4
  measurements): the reversion edge is real but tiny — fixes moved PF
  0.61 -> 0.73 -> 0.79 and K4 3.85x -> 3.14x -> 2.13x (passing) without ever
  crossing PF 1.0. LESSON: a +0.2% median reversion win cannot clear a 0.1%
  round-trip cost floor at 15m; faster exits free slots that re-enter into
  the same shallow edge. Binds band-family plans 2, 3, 11: answer the
  cost-floor question before Phase 4.

## Rules

- Rows are updated only by terminal verdicts (from `.agent/prompts/final-verdict.md`
  or Phase 8's FINAL.md) — not by phase progress (that lives in STATE.md).
- Never delete or edit a lesson entry. Append only.
- A strategy deleted on death keeps its verdict here forever.
