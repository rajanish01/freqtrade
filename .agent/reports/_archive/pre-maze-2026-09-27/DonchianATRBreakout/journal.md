# JOURNAL — DonchianATRBreakout

Plan: `user_data/strategies/plan/DonchianATRBreakout.md` (#10, breakout family)
Branch: `rj/strategy/DonchianATRBreakout` (forked from `rj/develop` 2026-09-27)
Config: `configs/strategies/DonchianATRBreakout.json`

---

## 2026-09-27 — Phase 0: DATA-READINESS

**Setup:** branch forked from `rj/develop` (working tree clean). Run pick
user-approved: plan #10 DonchianATRBreakout; dead BBRSIMeanReversion branch kept.

**Commands run + evidence:**

- `freqtrade list-data --config configs/strategies/DonchianATRBreakout.json --show-timerange`
  — all 10 whitelist pairs present at 15m and 1m, full range
  2022-01-01 → 2026-09-23 (covers IS end 20250630 and OOS end 20260709).
- `freqtrade list-strategies --config configs/strategies/DonchianATRBreakout.json`
  — exactly two configs loaded (`DonchianATRBreakout.json` + `../base.futures.json`),
  no `config.json`. Strategy discovery OK, no DUPLICATE NAME.
- Canary backtest (SmokeTestStrategy config, 20250601-20250701, `--cache none`)
  — 50 trades.
- `bash .agent/scripts/framework-check.sh` — **10 PASS / 0 FAIL**, including:
  config isolation, strategy discovery, 10×1h futures/funding/mark datasets,
  no stray strategy files, canary 50 trades, no funding warnings,
  funding fees applied (39/50 canary trades non-zero).
- Note: DonchianATRBreakout.json omits a local `api_server` block — fine:
  base.futures.json's block is complete (includes `enabled`) and is inherited
  (gotcha #2 verified non-issue this run).

**Exit criteria (Phase 0):**

| Criterion | Verdict |
|-----------|---------|
| Every pair in the plan has data at the strategy timeframe (15m, and 1m for the detail pass) | PASS |
| Only the strategy config + base config loaded — no `config.json` | PASS |
| `pair_whitelist` uses futures notation and matches the plan (10 majors) | PASS |
| Canary backtest produced a results table with > 0 trades (50) | PASS |
| IS and OOS timeranges stated and non-overlapping (IS 20220101-20250630 / OOS 20250701-20260709) | PASS |
| 10 funding-rate files present, no funding warnings | PASS |
| `.agent/STATE.md` updated: `current_phase: 1` | PASS (done) |

**VERDICT: PASS — proceed to Phase 1 (SCAFFOLD).**

Carry-forward notes for later phases:
- No new data needed for this plan (OHLCV 15m only, no informative TFs).
- Phase 3 smoke: 0 trades ⇒ check the Donchian `shift(1)` first, not thresholds.
- Phase 2: add the pre-approved Donchian catalog row to
  `.agent/reference/indicator-catalog.md` (YELLOW pre-approved in-plan).
- Plan's Phase-7 comparison vs MultiMATSL is deferred (#5 not built).

---

## 2026-09-27 — Phase 1: SCAFFOLD

**File created:** `user_data/strategies/DonchianATRBreakout.py` (structure only,
no logic; empty-scaffold style, initialise-then-assign).

**Risk-layer verification (Kotegawa, computed at scaffold time):**

| Check | Formula | Value | Verdict |
|-------|---------|-------|---------|
| K1 reserve | tradable_balance_ratio (base config) | 0.5 (verified in base.futures.json) | PASS |
| K2 per-trade risk | (0.5 / 5) x 0.12 | 1.2% equity | <= 2% PASS |
| K7 liquidation headroom | 0.12 / 2 = 6.0% price vs 1/2 = 50% | 8.3x margin | PASS |
| K4 trailing giveback | trailing disabled; exit channel is the giveback mechanism | n/a (structural) | PASS |
| ROI precedes trailing | ROI disabled (`{"0": 100}`) | trivially true | PASS |
| K6 no averaging down | position_adjustment_enable = False | declared | PASS |

**Protections recorded (15m candle counts):** CooldownPeriod 2; StoplossGuard
lookback 96 / trade_limit 1 / stop 96, only_per_pair=False, only_per_side=False
(K2 account-wide 24h); MaxDrawdown lookback 2000 / trade_limit 5 / 0.10,
calculation_mode "equity", stop 288 (3-day pause). `--enable-protections` on
every backtest from Phase 4 onward.

**Leverage:** NATR-targeted, `target_vol_pct=0.5`, `max_leverage_cap=2.0`
(plan: breakouts enter at elevated local volatility, lower cap than reversion
plans). Callback floors at 1.0, never hyperopt-optimised. Requires
`ind_natr_14` from Phase 2.

**Exit criteria (Phase 1):**

| Criterion | Verdict |
|-----------|---------|
| File exists at user_data/strategies/DonchianATRBreakout.py | PASS |
| pyflakes clean (no undefined names) | PASS (CLEAN) |
| list-strategies shows strategy OK (INTERFACE v3, can_short Yes) | PASS |
| Smoke backtest runs clean, 0 trades (20250601-20250701, --cache none) | PASS (0 trades) |
| populate_indicators returns dataframe unchanged | PASS |
| No entry/exit conditions present | PASS |
| All opt_* params declared (opt_dc_entry_len, opt_dc_exit_len, opt_adx_min, opt_vol_mult) | PASS |
| Risk-layer checks computed and recorded (no violation) | PASS |
| STATE.md updated | PASS (done) |

**VERDICT: PASS — proceed to Phase 2 (INDICATORS).**

---

## 2026-09-27 — Phase 2: INDICATORS

**Edited:** `user_data/strategies/DonchianATRBreakout.py` — imports
(`import talib.abstract as ta`) + `populate_indicators()` only. Entry/exit
methods untouched.

**Fix within the phase (1):** first import attempt was
`from talib.abstract import ta` — module does not export the name `ta`
(cannot-import-name at list-strategies). Correct convention is aliasing the
module: `import talib.abstract as ta`. Fixed, re-run clean.

**Indicators implemented:**

| Indicator | Method | Columns |
|-----------|--------|---------|
| Entry-channel high | `high.rolling(n).max().shift(1)`, n in {20,40,60,80,100,120} | `ind_dc_high_{n}` |
| Entry-channel low | `low.rolling(n).min().shift(1)`, n in {20,40,60,80,100,120} | `ind_dc_low_{n}` |
| Exit-channel low | `low.rolling(m).min().shift(1)`, m in {5,10,...,40} | `ind_dc_exit_low_{m}` |
| Exit-channel high | `high.rolling(m).max().shift(1)`, m in {5,...,40} | `ind_dc_exit_high_{m}` |
| ADX (14) | `ta.ADX(dataframe, timeperiod=14)` | `ind_adx_14` |
| Volume SMA (50) | `volume.rolling(50).mean()` | `ind_vol_sma_50` |
| Volume spike | `volume / ind_vol_sma_50` | `ind_vol_spike` |
| NATR (14) | `ta.NATR(dataframe, timeperiod=14)` | `ind_natr_14` |

- The `shift(1)` is load-bearing (prior-N extreme; without it close > rolling
  max is never true -> silent 0 trades). Plan-documented, catalog-documented.
- Both channel sweeps precomputed once (6 entry + 8 exit columns per pair);
  `opt_*` select columns at signal time -> `--analyze-per-epoch` NOT needed.
- Catalog: the Donchian row + shift(1) note already exist in
  indicator-catalog.md (added during the 2026-09-26 blueprint overhaul) —
  the plan's "add one catalog row on implementation" was already satisfied;
  no catalog edit made.
- `startup_candle_count`: rule = max lookback (120) + 50 = 170; set **200**
  (plan value, covers ADX Wilder-smoothing convergence). recursive-analysis
  confirms stability at 200.

**Verification:**
- pyflakes: CLEAN
- Smoke backtest (20250601-20250701, --cache none): runs clean, 0 trades —
  correct, signals arrive Phase 3.
- recursive-analysis (20250101-20250701): `ind_adx_14` 0.000%, `ind_natr_14`
  0.000% across 199/200/399/499/999/1999 — no unstable indicators. (Only
  ta-lib indicators are analyzed; the rolling extremes are plain
  pandas-rolling calls, no recursion concern.)

**Exit criteria (Phase 2):**

| Criterion | Verdict |
|-----------|---------|
| Every indicator from the strategy idea implemented, ind_ prefixed | PASS (8 families, 16+ columns) |
| No indicator outside the approved catalog | PASS (Donchian row pre-existing) |
| startup_candle_count = max lookback + 50 | PASS (200 >= 170; plan value, covers ADX convergence) |
| Smoke backtest runs without error | PASS |
| recursive-analysis reports no unstable indicators | PASS (none) |
| Entry/exit methods untouched | PASS |
| STATE.md updated | PASS (done) |

**VERDICT: PASS — proceed to Phase 3 (SIGNALS).**

---

## 2026-09-27 — Phase 3: SIGNALS

**Edited:** `user_data/strategies/DonchianATRBreakout.py` —
`populate_entry_trend()` / `populate_exit_trend()` only.

**Entry logic (level test, not a cross — any close beyond the prior extreme is
a valid breakout state; CooldownPeriod prevents re-entry churn):**
- Long: `close > ind_dc_high_{opt_dc_entry_len}` AND `ind_adx_14 > opt_adx_min`
  AND `ind_vol_spike > opt_vol_mult` AND `volume > 0` -> tag `dc_breakout_long`
- Short (mirror): `close < ind_dc_low_{opt_dc_entry_len}` + same conjuncts ->
  tag `dc_breakout_short`
- NaN warm-up region naturally excluded (NaN comparisons are False).

**Exit logic (exit channel is the exit thesis, Turtle-style trailing):**
- Long: `close < ind_dc_exit_low_{opt_dc_exit_len}` -> tag `dc_trail_exit`
- Short: `close > ind_dc_exit_high_{opt_dc_exit_len}` -> tag `dc_trail_exit`
- `minimal_roi` disabled, no trailing stop — the channel gives back more than a
  trail would, by design, in exchange for not capping winners.

**Smoke backtest (20250601-20250701, --cache none, defaults N=40/M=15, ADX 25,
vol 1.5):** 215 trades | win 35.8% | avg -0.15% | avg duration 8h12m | DD 5.60%.

**Trade count band:** 215 is marginally above the 1-200 "reasonable" guidance
band, far below the >2000 noise FAIL. ~21.5 trades/pair/month (~0.7/day/pair)
at 15m with ADX+volume conjuncts is a sane breakout rate; the plan expects
few large winners and a low win rate (expected 35-45% — measured 35.8%).
Explicit PASS with justification, not an implicit one. Phase 4 remains the gate.

**Exit criteria (Phase 3):**

| Criterion | Verdict |
|-----------|---------|
| populate_entry_trend sets at least one entry condition | PASS (two: long + short mirror) |
| populate_exit_trend sets at least one exit condition | PASS (two: channel low/high) |
| Every threshold uses an opt_* parameter (zero magic numbers) | PASS (4 params, .value read; channel period selects precomputed column) |
| Every entry and exit is tagged | PASS (dc_breakout_long/short, dc_trail_exit) |
| volume > 0 guard present on entries | PASS |
| 1-month smoke backtest trade count in sane band | PASS (215 — marginally above 1-200 guidance, far below 2000 noise FAIL; justified above) |
| No indicator calculations added to the signal methods | PASS |
| STATE.md updated | PASS (done) |

**VERDICT: PASS — proceed to Phase 4 (BACKTEST).**

---

## 2026-09-27 — Phase 4: BACKTEST — FAIL (iteration 1)

**No strategy file modified in this phase.** Full analysis in
`phase4-iter1.md`. Summary of the real numbers:

- Bias checks (run FIRST, before any profit number): lookahead CLEAN
  (has_bias=No, 20 signals, 0 biased); recursive CLEAN (adx 0.001% at
  warm-up edge only, 0.000% by 399).
- Full IS (20220101-20250630, defaults, protections ON): 3688 trades,
  win 33.5%, **PF 0.9068**, total **-31.02%**, **DD 45.65%** (848 days),
  Sharpe -0.59, funding -7.47 USDT (2.41% of |gross|), avg lev 1.182x.
- 1m detail (REDUCED: H1 2025, SOL/ETH/BNB): PF 1.0621 vs main-TF same
  window 1.0621 — divergence 0.0% (detail flag verified active; no trailing
  stop / custom stoploss exist, so 1m has nothing to change here).
- Gates: PF FAIL, DD FAIL, Sharpe FAIL, profitable pairs FAIL (3/10);
  trades PASS (3688), stoploss loss-share PASS (2.0%), funding PASS (2.41%),
  payoff PASS (avg_win 2.44 > avg_loss 1.33).
- Cost decomposition: raw price edge +36.60 USDT at zero costs (PF 1.0118,
  win 35.2%); fees 339.34 USDT consume it ~10x over. Win rate 33.5% vs
  35.7% break-even at payoff 1.81.
- Monthly: 16/42 positive; profit concentrated in 2022-01/02; 848-day DD.
- Exit mix: dc_trail_exit 99.8% of exits, stoploss 6 trades — the exit
  channel works; the ENTRY conjuncts admit chop.

**Risk numbers mirrored to global journal (per CONVENTIONS.md).**

**VERDICT: FAIL — 4 gates failed. Fix proposal in phase4-iter1.md;
awaiting approval before re-entering Phase 3.**

Proposed ONE change (ranked #1 of 3): `opt_adx_min` default 25 -> 30
(Phase 3, threshold within declared range). Expected: win rate +2-4pp toward
the 35.7% break-even, trades -25-40%. Risk: fewer trades.

---

## 2026-09-27 — Phase 4 iteration 2 (fix: opt_adx_min 25 -> 30) — STILL FAILING

**Fix applied (user-approved):** `opt_adx_min` default 25 -> 30 — Phase 3
re-entered, threshold within declared range 15-35. One change only.
Phase 3 re-verification: smoke clean, 164 trades (was 215; band PASS).

**Full IS re-backtest (20220101-20250630, --cache none --enable-protections,
--breakdown month, export to results/backtests):**

| Metric | iter 1 (ADX 25) | iter 2 (ADX 30) | Delta |
|--------|-----------------|-----------------|-------|
| Trades | 3688 | 3843 | +155 (shorts +128) |
| Win rate | 33.5% | 34.3% | +0.8pp |
| Profit factor | 0.9068 | 0.9217 | +0.015 |
| Total profit | -31.02% | -27.21% | +3.8pp |
| Max drawdown | 45.65% | 35.16% | -10.5pp |
| Sharpe (daily) | -0.59 | -0.46 | +0.13 |
| Funding | -7.47 | -14.08 | -6.6 (more shorts) |
| Profitable pairs | 3/10 | 2/10 | WORSE |
| Edge at zero costs | +36.6 USDT | +98.0 USDT | +2.7x |
| PF at zero costs | 1.0118 | 1.0302 | +0.018 |
| Long / Short profit | -12.22% / -18.80% | -7.71% / -19.51% | long better, short same |
| Payoff | 1.81 (BE 35.7%) | 1.78 (BE 36.0%) | win 34.3% still 1.7pp short |

**Gates (iter 2):** PF 0.9217 FAIL (<1.2) · DD 35.16% FAIL (>25%) ·
Sharpe -0.46 FAIL · profitable pairs 2/10 FAIL · trades PASS (3843) ·
stoploss/funding/payoff PASS (unchanged mechanisms).

**Reading:** the ADX conjunct hypothesis was only marginally right — +0.015 PF.
The structural problem is unchanged: raw edge +0.025%/trade vs fee cost
~0.115%/trade (4.5x). The short side remains the bigger drag (-19.51% vs
-7.71%). Profitable pairs got worse (2/10) — the strategy is not a one-pair
story either; it loses nearly everywhere.

**VERDICT: STILL FAILING.** Kill criterion #1 ("PF < 1.2 in-sample after one
round of tuning") is now arguably MET — the ADX round was one round of tuning
and PF is 0.92. Fix attempts used: 1 of 3. Next-step decision escalated to
the user: one more ranked fix (structural, opt_dc_entry_len 40 -> 80) or
terminal verdict.
