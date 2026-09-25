# Callbacks Reference — freqtrade 2026.6 (verified against stable docs)

Semantics that matter for risk control. Read at Phase 1 (scaffold) and before
touching any callback. Scope note from CONVENTIONS.md still applies: in
callbacks, `df["col"].iat[-1]` is the correct per-trade pattern; the
vectorised-only rule applies to `populate_*` methods.

All callbacks are evaluated per bot-iteration (~5s) live/dry and **once per
candle in backtesting** (`timeframe`, or `timeframe_detail` when
`--timeframe-detail` is used).

---

## custom_stoploss — time-varying / structural stops
- Requires `use_custom_stoploss = True`. The static `stoploss` attribute is
  both the absolute floor and the initial value.
- Return value is a ratio relative to `current_rate`; sign ignored;
  `None`/`NaN`/inf = "keep current".
- **The stop price can only move up** (down for shorts) — it ratchets; lower
  values are ignored.
- **Disable `trailing_stop` when using it** — combining the two is conflicting
  behavior (docs).
- **Futures:** the returned value is the **risk of the trade including
  leverage** — `profit_ratio = price_change x leverage`. A -0.04 return at 2x
  fires after a 2% adverse price move.
- Backtesting nuance: `current_rate`/`current_profit` evaluate against the
  candle's high (low for shorts), the resulting stop against the candle's
  low (high for shorts).
- `after_fill: bool` parameter (only if present in the signature): callback
  re-runs after order fills and may move the stop in **any** direction.
- Helpers: `stoploss_from_open()`, `stoploss_from_absolute()`.
- Strategy that uses it: `ObeliskRSIRegime` (time-ramped stop).

## custom_exit
- Called per candle for every open trade. Return a string (<= 64 chars,
  becomes the exit reason) or `True` to full-exit.
- Not called when an exit signal is already set or `use_exit_signal=False`;
  ignores `exit_profit_only`.
- Docs: rate-based exits are approximate in backtesting; for stop-like
  behavior prefer `custom_stoploss` (it supports stoploss-on-exchange,
  `custom_exit` does not).

## confirm_trade_entry
- Last call before placing an entry order. Return `False` to abort (default
  `True`). Use for final veto checks; never for sizing (K3 covers that).

## confirm_trade_exit
- Last call before an exit order. May fire multiple times per iteration.
- Exit-reason evaluation order: `exit_signal`/`custom_exit` -> `stop_loss`
  -> `roi` -> `trailing_stop_loss`.
- **Never block a stoploss exit** (K7). Not called for liquidations at all.

## adjust_trade_position — DISABLED by house rule
- Requires `position_adjustment_enable = True` (we keep it `False` — Kotegawa
  K6, see `kotegawa-risk-layer.md`).
- For reference only: positive return increases the position, negative
  partial-exits; stake is pre-leverage; extra orders do not count toward
  `max_open_trades`; the stoploss keeps calculating from the **initial**
  opening price, not the averaged price — which is exactly why averaging down
  breaks the K2 budget math.

## custom_entry_price / custom_exit_price
- Limit orders only; fallback to `proposed_rate` on `None`/invalid.
- Max distance from current price: `custom_price_max_distance_ratio`
  (default 0.02).
- Backtest fills only if the price is within the candle's low/high — a
  backtest cannot see the book, so keep conservative distances.

## leverage — futures only
- Only called in futures mode. Return clamped to `[1.0, max_leverage]`;
  default 1x when unimplemented.
- Canonical implementation: `futures-playbook.md` §4 (NATR volatility
  targeting, hard cap). Never hyperopt-optimised.

## custom_roi — new in this version
- Requires `use_custom_roi = True`. When both `minimal_roi` and `custom_roi`
  are defined, **the lower one triggers the exit**.
- House rule: we do not use it; the ROI ladder is deterministic and Phase-4
  measured. Noted here so a stray implementation is recognised in review.

## Protections — in-strategy, backtest-flagged
- Defined as `@property protections` on the strategy class (never in config
  — gotcha #3). Template: `kotegawa-risk-layer.md` §K5.
- **Backtesting/hyperopt silently ignore protections unless
  `--enable-protections` is passed.** Every Phase 4/5/7 backtest passes it.
- Available: `CooldownPeriod`, `StoplossGuard`, `MaxDrawdown`
  (`calculation_mode: "equity"` recommended), `LowProfitPairs`.
- The hyperopt `protection` space stays excluded (risk layer is never
  optimised).

## Production-only notes (Phase 8)
- `stoploss_on_exchange: true` places the stop on the exchange so it survives
  bot crashes. Default **off** during development to keep backtest parity;
  consider at live time (needs exchange support; futures price type via
  `stoploss_price_type`: last/mark/index).
- `unfilledtimeout` — sane entry/exit order timeouts; check at Phase 8.
- `cancel_open_orders_on_exit: true` in dryrun configs (already standard).
