# Kotegawa Risk Layer — Deterministic "Always In Control" Contract

Source: the user-provided Takashi Kotegawa risk-management transcript
(Scribd/ValueBull). Every rule below is a deterministic freqtrade mechanism.
Nothing in this layer is ML-driven or discretionary.

The layer applies to **every** strategy built from `user_data/strategies/plan/`.
It is mandatory reading at Phase 1 and is checked at every phase gate.

**Policy note (MAZE, 2026-09-27) — read this once, then read each section's
own note for the specific detail.** The old text here said "nothing in this
layer is hyperopt-optimised." That conflated the risk MECHANISM (which stays
exactly this deterministic — fixed-fractional sizing, half-capital reserve,
which protection methods exist, the K4 payoff floor as a hard gate) with the
specific NUMBERS (stoploss magnitude, leverage cap, protection
lookback/trade_limit/duration). From `.agent/phases/04M-MAZE.md` tier T2
onward, those numbers are a bounded search dimension, scored every epoch by
`.agent/scripts/hyperopt/MazeGateLoss.py` against the exact formulas below —
an epoch that violates K2 or K7 fails exactly like one that fails profit
factor, it does not get a pass because hyperopt found it. This is a wider,
formula-gated search, not a looser risk layer. Read `04M-MAZE.md`'s "T2"
section for the full reasoning before treating this as a contradiction.

---

## The source rules (as given)

With capital of 100,000 (any currency):
1. Trade daily with **50% of capital** (50,000); keep the remaining 50% as backup.
2. Risk only **2% of active capital per day** (1,000). If the day's risk is
   spent, stop trading for the day.
3. **Position size = daily risk budget / stoploss distance.**
   (SL 10 points, budget 1,000 -> quantity 100.)
4. **Risk:reward 1:3 on every trade** (risk 10, target 30).
5. The asymmetry math: losing 15 of 30 days at 1:3 still nets +30% on capital.

## The mapping to freqtrade mechanics

| # | Kotegawa rule | Freqtrade mechanism | Where |
|---|---------------|--------------------|-------|
| K1 | 50% capital, 50% reserve | `tradable_balance_ratio: 0.5` in `configs/base.futures.json` | shared base config |
| K2 | 2% daily risk budget | per-trade bound (formula below) + `StoplossGuard` protection | strategy class |
| K3 | size = budget / SL | fixed fractional slots: stake = equity x 0.5 / max_open_trades; risk = stake x \|stoploss\| | structural, verified Phase 1 |
| K4 | 1:3 reward structure | hard gate `avg_loss < 3 x avg_win` (Phase 4) + trailing-giveback rule | Phase 4 gates |
| K5 | stop when the day is spent | `StoplossGuard` (24h window) + `MaxDrawdown` + `CooldownPeriod` | strategy `@property protections` |
| K6 | never average down | `position_adjustment_enable = False` | strategy class attribute |
| K7 | always in control | stoploss fires far before liquidation; `confirm_trade_exit` never blocks a stoploss exit | Phase 1 + callbacks rules |

---

## K1 — Half-capital reserve

`configs/base.futures.json` sets `"tradable_balance_ratio": 0.5`.

Freqtrade docs (Configuration / Tradable balance): "the bot will use a maximum
amount of [50%] for trading and considers this as an available balance. The
rest of the wallet is untouched by the trades."

With `stake_amount: "unlimited"` and `max_open_trades: 5` the deployed capital
splits evenly: **each trade uses ~10% of equity as margin**. Worst case — all
five positions go to zero — loses at most half the wallet. The reserve is
never deployable by a trade.

## K2 — The 2% daily risk budget

**Per-trade bound (hard formula check at Phase 1 and on any risk-param change;
enforced per-epoch as a hyperopt gate from T2 onward — see the MAZE policy
note above):**

```
stake_fraction  = tradable_balance_ratio / max_open_trades   # 0.5 / 5 = 0.10
risk_per_trade  = stake_fraction * |stoploss|                  # equity terms
REQUIREMENT:    risk_per_trade <= 0.02
```

With the house settings this means **|stoploss| <= 0.20** for any strategy at
`max_open_trades = 5`; the bound moves with whatever `max_open_trades` a node
actually uses (a node testing `max_open_trades = 3` has a tighter stoploss
ceiling of ~0.033 at the same 2% budget — the formula, not a fixed number, is
the invariant). All plans built so far comply (stops range -0.08 to -0.15).
Record the actual number in the strategy's journal at Phase 1, and let
`MazeGateLoss`'s `risk_k2` gate enforce it automatically for every searched
value from T2 onward.

**Daily enforcement — StoplossGuard.** Kotegawa's example sizes ONE trade to
the full daily budget; after one full stoploss the day is spent. The
structural equivalent: `trade_limit: 1` on a 24-hour window. One stopped trade
(x ~1.2% risk) stays inside the 2% budget; a second same-day full loss cannot
happen because entries pause for 24h.

Hand-tuning `trade_limit` is allowed (record it in the journal): raising it to
2 admits a worst day of ~2.4% — slightly over budget; only do it if the
strategy's stoploss share of exits is well under 50% AND the journal shows the
guard is strangling an otherwise clean strategy.

## K3 — Position size = risk budget / stoploss distance

Kotegawa sizes each trade so that `quantity x SL = daily budget`. Freqtrade's
fixed-fractional slots are the same invariant in disguise:

```
stake  = equity x tradable_balance_ratio / max_open_trades
loss   = stake x |stoploss|        # freqtrade stoploss is account-risk,
                                   # leverage does not change it
```

Risk per trade is therefore **constant as a fraction of equity** and
compounds automatically. This replaces per-trade quantity arithmetic; do not
add a `custom_stake_amount()` callback on top of it.

## K4 — The 1:3 reward structure

A literal per-trade 1:3 (target = 3x the stoploss) is incompatible with the
plans' ROI-ladder exits on 15m futures — it would require ROI@0 = 36% at
stoploss -0.12. The rule is enforced in three honest pieces:

1. **Hard gate (Phase 4, and every hyperopt epoch from T2 onward via
   `MazeGateLoss`'s `payoff_k4` term):** `avg_loss < 3 x avg_win` — the
   payoff floor. A strategy whose average loss is 3x its average win is the
   inverted-RR catastrophe (anti-pattern #5) and fails regardless of win
   rate. An epoch that would violate this never wins the search — it scores
   past `GATE_FAIL_BASE` exactly like a profit-factor failure.
2. **Trailing-giveback rule:** `trailing_stop_positive <=
   trailing_stop_positive_offset / 3` — giveback at most one third of the
   gain locked in. BBRSI: 0.01 giveback vs 0.03 offset = exactly 1:3.
3. **Reported ratio:** every Phase 4 report states `ROI@0 : |stoploss|`.
   Mean-reversion families invert the per-trade ratio by design (many small
   wins, rare full losses). That is a *justified deviation*, recorded in the
   journal and defended by realized expectancy — not a silent breach.

The 15-of-30-losing-days math is enforced portfolio-wide by the existing
gates: profit factor > 1.2, expectancy > 0, stoploss share < 50%.

## K5 — Circuit breakers (protections)

Standard template, defined as a `@property` on every strategy class
(protections NEVER live in a config file — gotcha #3). The set of METHODS
(CooldownPeriod/StoplossGuard/MaxDrawdown) is fixed by hand at Phase 1 and
never changes without YELLOW approval. The specific VALUES
(`stop_duration_candles`, `trade_limit`, `lookback_period_candles`,
`max_allowed_drawdown`) are hand-tuned starting points at Phase 1, recorded
in the journal, and from MAZE tier T2 onward are a bounded hyperopt space
(`--spaces protection`) — see the policy note at the top of this file.
Expose them as `opt_*` parameters read inside the `protections` property
(e.g. `opt_cd = IntParameter(1, 6, default=2, space="protection")`) to make
them searchable; a strategy that leaves them as plain literals simply has
nothing in that space, which is a valid choice too.

```python
@property
def protections(self):
    return [
        {   # re-entry cooldown after any exit on the same pair
            "method": "CooldownPeriod",
            "stop_duration_candles": 2,
        },
        {   # K2: one full stoploss spends the day's risk budget
            "method": "StoplossGuard",
            "lookback_period_candles": 96,   # 24h on 15m (see conversion table)
            "trade_limit": 1,
            "stop_duration_candles": 96,     # pause entries for 24h
            "only_per_pair": False,          # the budget is account-wide
            "only_per_side": False,
        },
        {   # K7 backstop: equity drawdown breaker, well inside the 25% gate
            "method": "MaxDrawdown",
            "lookback_period_candles": 2000,
            "trade_limit": 5,
            "max_allowed_drawdown": 0.10,
            "calculation_mode": "equity",
            "stop_duration_candles": 288,    # 3-day pause, then reassess
        },
    ]
```

Candle -> wall-clock conversion (adjust per strategy timeframe):

| Timeframe | 24h | 3 days | ~21 days |
|-----------|-----|--------|----------|
| 5m        | 288 | 864    | 6048     |
| 15m       | 96  | 288    | 2000 (approx) |
| 1h        | 24  | 72     | 500 (approx) |

Protection semantics (freqtrade 2026.6, docs /plugins):
- `StoplossGuard` counts exits with reason `stop_loss`,
  `stoploss_on_exchange` or `trailing_stop_loss` **when profit was negative**.
- `MaxDrawdown` with `calculation_mode: "equity"` measures peak-to-trough on
  the account equity curve (recommended for new setups).
- Protections are evaluated in order; end times round up to the next candle.
- **Backtesting requires `--enable-protections`** or they are silently absent.
  The hyperopt `protection` space stays excluded — the risk layer is never
  optimised.

## K6 — Never average down

`position_adjustment_enable = False` on every strategy. No `adjust_trade_position`
callback. If a future user-approved strategy ever enables DCA, it is a YELLOW
decision logged in the journal, and the K2 budget math must be redone.

## K7 — Always in control

- **Liquidation distance:** isolated-margin liquidation sits near
  `-1/leverage` in price terms; the stoploss fires at `|stoploss|/leverage`
  in price terms. Check at Phase 1: `|stoploss| / leverage <= 0.5 / leverage`
  (i.e. stop at <= half the distance to liquidation), plus the default
  `liquidation_buffer: 0.05` safety margin. BBRSI: -0.12 stop at 3x = 4%
  price move vs ~33% liquidation — 8x margin of safety.
  **Note the algebra:** leverage appears on both sides of that inequality and
  cancels — the check simplifies to `|stoploss| <= 0.5`, independent of
  leverage. That is not a mistake in the original formula; it is *why*
  freqtrade's own `profit_ratio = price_change x leverage` design makes the
  stoploss ratio a leverage-independent account-risk figure once you have
  already fixed the "half the liquidation distance" margin. It does mean the
  leverage cap itself is not doing liquidation-distance work — its job is
  purely K2/volatility-targeting (below) and the funding-cost/holding-period
  tradeoff (`futures-playbook.md` §2, §4). `MazeGateLoss`'s `liquidation_k7`
  gate implements the simplified, leverage-independent form directly.
- **Leverage cap is now a bounded search dimension.** `max_leverage_cap` (the
  hard ceiling inside `leverage()`) can be a `DecimalParameter(...,
  space="risk")` from MAZE tier T2 onward instead of a fixed hand-picked
  constant — still capped (default ceiling 3.0x, matching
  `futures-playbook.md` §4), still floored at 1.0, still formula-bound by K2
  through the stoploss/max_open_trades relationship above. The
  volatility-TARGETING FORMULA (`lev = target_vol_pct / natr`, floored/capped)
  stays fixed — what moves is the cap and, if declared as its own `opt_*`,
  `target_vol_pct` itself.
- **Never block a stoploss exit** in `confirm_trade_exit` (docs warning:
  blocking stoploss exits can cause significant losses; the callback is not
  called for liquidations).
- **Fees/funding stay inside the budget:** funding is charged on notional and
  scales with leverage — report `funding_fees` at Phase 4 and keep the
  existing <20%-of-gross-profit gate (exception: FundingSkewCarry, where
  funding is revenue).

## Verification checklist (Phase 1, and any YELLOW risk change)

- [ ] `tradable_balance_ratio` is 0.5 (base config) — not overridden higher
- [ ] `risk_per_trade = 0.5 / max_open_trades x |stoploss| <= 0.02` — number recorded
- [ ] `|stoploss| / max_leverage_cap <= 0.5 x (1 / max_leverage_cap)` (stop at
      <= half the liquidation distance) — number recorded
- [ ] `trailing_stop_positive_offset < minimal_roi["0"]` (docs rule, else ROI
      always fires first) — checked
- [ ] `trailing_stop_positive <= trailing_stop_positive_offset / 3` (K4)
- [ ] `position_adjustment_enable = False`
- [ ] protections property present, values recorded, `--enable-protections`
      used in every backtest from Phase 4 onward
- [ ] if any of stoploss/leverage-cap/protection-values are hyperopted (T2+),
      `MazeGateLoss` (or an equivalent gate-aligned loss) is the loss function
      used — a generic return-based loss does not enforce K2/K4/K7
