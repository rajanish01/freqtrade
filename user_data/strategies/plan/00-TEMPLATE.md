# 00-TEMPLATE — Canonical Futures Strategy Plan Template

Every plan in this folder follows this structure. Read
`.agent/reference/futures-playbook.md` and
`.agent/reference/kotegawa-risk-layer.md` before writing one.

A plan is the **contract for the whole 0-8 loop**: everything the building
agent writes in Phases 1-3 must trace back to this file, and every gate in
Phases 4-7 judges what this file declared. If a section is missing, the agent
improvises — and improvised detail at Phase 1 is how risk layers drift. Write
plans completely.

This template supersedes `.agent/prompts/strategy-idea.md` for full plans.
`strategy-idea.md` remains the intake form for a raw new idea; promotion from
idea to plan means rewriting it in this format.

---

## Required file header

```markdown
# <StrategyName> — Futures Strategy Plan
## Based on: <source strategy / paper / mechanism>
## Absorbs: <any older plans this one replaces>
## FUTURES-NATIVE      <- only if the mechanism cannot exist on spot
```

- Class name = filename = config filename. PascalCase, no exceptions.
- One plan, one strategy, one config (`configs/strategies/<Name>.json`).

## Section order (mandatory, in this order)

1. **Character line** — one sentence distinguishing it from every other plan.
2. **Hypothesis** — what market behaviour is exploited and why it persists.
   Include **Who is on the other side** (the flow that loses to you).
3. **Direction & symmetry claim** — long only / both, and *why* per
   `futures-playbook.md` §3. `can_short = True` is a hypothesis claim, not a
   feature toggle. Where shorts are on, short thresholds are **derived** from
   long ones (`100 - x`) unless the plan justifies asymmetry explicitly.
4. **Futures deltas** — table vs the spot/original version (timeframe, stop,
   ROI, direction), with one-line reasons.
5. **Timeframe** — default 15m. Any deviation is justified by the mechanism's
   time structure (funding = 1h, liquidation cascades = 5m), not by taste.
6. **Data requirements** — candle types beyond OHLCV (funding_rate, mark) and
   cross-pair informative needs, with the exact `self.dp.get_pair_dataframe` /
   `@informative` call and its warmup consequence.
7. **Indicators** — table: Indicator | Method (exact code) | Column (`ind_*`).
   Every column used in entries/exits is declared here. Informatives get their
   own table. If an indicator is not in `.agent/reference/indicator-catalog.md`
   the plan must flag it (Phase 2 else halts).
8. **Entry logic** — long and short blocks, each condition on its own line,
   each entry tagged. Crosses (`qtpylib.crossed_above/below`) vs level tests
   are chosen deliberately and the choice is explained.
9. **Exit logic** — structural exit vs target exit distinguished; tags for
   every reason so `backtesting-analysis` can attribute P&L.
10. **Hyperopt parameters** — table: Parameter | Type | Range | Default | Space.
    3-9 params. If more, the plan names which is cut first on overfit flags.
11. **Hyperopt execution notes** — see decision rule below. Mandatory.
12. **Risk parameters** — the hardcoded block (stoploss, trailing, ROI,
    startup_candle_count, target_vol_pct, max_leverage_cap).
13. **Risk verification** — the precomputed table below. Phase 1 re-verifies,
    never re-derives.
14. **Protections** — the exact `@property protections` block, candle counts
    converted to the plan's timeframe per the cheat-sheet below.
15. **Strategy configuration** — the class-attribute block + config path.
16. **Phase map** — anything the building agent must know per phase (expected
    smoke-test trade counts, Phase 4 watch items, Phase 5 epoch budget, Phase 7
    emphasis). Optional but strongly preferred.
17. **Key patterns to learn** — what this plan teaches that transfers.
18. **Expected behaviour** — works in / struggles in / watch for.
19. **Kill criteria** — pre-registered, before any number is seen. These are
    the defence against rationalising a bad backtest.
20. **Changelog** — dated one-liners for every correction applied after the
    plan was first written. Never silently edit a plan.

---

## Risk verification — precomputed block every plan carries

Formula source: `kotegawa-risk-layer.md` §K2/K4/K7. Base config values:
`tradable_balance_ratio: 0.5`, `max_open_trades: 5` → stake fraction 0.10.

| Check | Formula | Verdict criteria |
|-------|---------|------------------|
| Per-trade risk (K2) | `0.10 x \|stoploss\|` | <= 0.02 (2% equity) |
| Liquidation headroom (K7) | `\|stoploss\| / max_leverage_cap` vs `1 / max_leverage_cap` | stop at <= half the liquidation distance |
| Trailing giveback (K4) | `trailing_stop_positive <= trailing_stop_positive_offset / 3` | if trailing enabled |
| ROI/trailing precedence | `trailing_stop_positive_offset < minimal_roi["0"]` | if trailing enabled; trivially true when ROI is disabled (`{"0": 100}`) |

Fill with actual numbers. A FAIL here means the plan is wrong, not the check —
fix the plan before Phase 1, never relax the rules silently.

## Protections cheat-sheet (Kotegawa K5, per timeframe)

CooldownPeriod is `2` on all timeframes. Convert guard/drawdown windows:

| Timeframe | StoplossGuard lookback / stop (24h) | MaxDrawdown lookback (~21d) / stop (3d) |
|-----------|--------------------------------------|------------------------------------------|
| 15m | 96 / 96 | 2000 / 288 |
| 5m | 288 / 288 | 6048 / 864 |
| 1h | 24 / 24 | 500 / 72 |

```python
@property
def protections(self):
    return [
        {"method": "CooldownPeriod", "stop_duration_candles": 2},
        {"method": "StoplossGuard", "lookback_period_candles": <24h>,
         "trade_limit": 1, "stop_duration_candles": <24h>,
         "only_per_pair": False, "only_per_side": False},
        {"method": "MaxDrawdown", "lookback_period_candles": <21d>,
         "trade_limit": 5, "max_allowed_drawdown": 0.10,
         "calculation_mode": "equity", "stop_duration_candles": <3d>},
    ]
```

Protections are hand-tuned per strategy (the plan states values), never
hyperopted, and backtests only honour them with `--enable-protections`.

## Hyperopt execution notes — mandatory decision rule

**`--analyze-per-epoch` rule (ENVIRONMENT.md gotcha #0c):**
- Any `opt_*` read **inside** `populate_indicators` (period of a rolling, a
  multiplier in a channel formula, a z-score lookback) -> the flag is
  MANDATORY. Without it hyperopt optimises against columns computed once with
  default values: silently garbage.
- `opt_*` used only **at signal time** to select among precomputed columns
  (the EWO/MultiMA sweep pattern) -> flag NOT needed.

State which case applies and why. If the flag is needed, say so in bold —
budget 3-10x hyperopt time, or use the stepped-sweep alternative below.

**Stepped sweeps (verified API facts, 2026-09-26):**
- `IntParameter(5, 80, default=15, space="buy", step=5)` works — extra kwargs
  pass through to the optuna `IntDistribution`.
- BUT the parameter's `.range` property ignores `step` and returns every
  integer — so when precomputing a column sweep, hardcode the matching
  `range(5, 81, 5)` in `populate_indicators`; do not iterate `.range`.
- The selected period at signal time is `f"ind_ema_{self.opt_x.value}"` and in
  backtest (non-hyperopt) mode `.value` equals `default` or the json-loaded
  value — both must be members of the stepped set.

## Changelog convention

```markdown
## Changelog
- 2026-09-26: <what changed, why, and what finding/bug motivated it>
```

Numbers, params and risk values may only move with a changelog entry naming
the evidence. A plan with silent edits is untrustworthy.

---

## Style rules for this folder

- Plain numbers, no estimates. If a fact comes from data, name the source
  (`ENVIRONMENT.md`, a verified command, a completed run).
- One plan teaches at least one **transferable pattern** — say which.
- Kill criteria are written before results exist. Never soften them
  afterwards; change them only before the relevant phase runs.
- A plan that dies at Phase 4 with a clean postmortem is a success of the
  process. Write plans that can die cleanly.
