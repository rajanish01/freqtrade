# RESEARCH-BACKLOG — Candidate Futures Strategies (scored; first pass 2026-09-26, second pass 2026-09-27)

Two research passes + portfolio-gap analysis. First pass (2026-09-26): sources
freqtrade/freqtrade-strategies (5.5k stars, the official community repo),
iterativv/NostalgiaForInfinity (3.4k stars, 8 maintained generations — the most
battle-tested freqtrade strategy), the Donchian/Turtle lineage, the TTM-squeeze
lineage, and cross-asset lead-lag literature applied to BTC as the crypto market
factor. Second pass (2026-09-27, at the bottom): academic verification (NBER/RFS,
arXiv) + local data-feasibility checks; its sources are in the table in that
section.

**Confidence scale** (1-5): how much external evidence the *mechanism* has —
NOT an expected-profit estimate. A 3/5 here with a clean mechanism beats a
5/5 with magic attached. Every entry states its blockers honestly.

**Promotion path:** backlog entry -> full plan in this folder (`00-TEMPLATE.md`)
-> the 0-8 loop. Only three entries are promoted now (below). Nothing else on
this list is pre-approved; promoting one is a normal new-plan decision.

---

## Promoted to full plans (this batch)

| Plan | Family | Confidence | Why promoted |
|------|--------|-----------|--------------|
| #10 `DonchianATRBreakout` | breakout | **4/5** | Trend-following/channel-breakout premia are among the best-documented futures anomalies (Turtle lineage, decades of CTA evidence; strong crypto trend premia 2022-2026 data window). Fills the portfolio's missing *enter-on-strength* style. |
| #11 `BBSqueezeBreakout` | vol compression -> expansion | **3/5** | Mechanistically grounded in crypto volatility clustering; thinner standalone expectancy evidence, so it carries a hard must-beat-the-control kill criterion. Reuses the band family's width filter, inverted. |
| #12 `RelativeStrengthBTC` | cross-pair lead-lag | **3/5** | BTC-as-market-factor is empirically solid (alt beta to BTC, capital rotation waves); the unproven part is freqtrade's cross-pair informative mechanics, which Phase 0/2 prove cheaply. Teaches the one data pattern no other plan uses. |

---

## The backlog (not promoted — with the reason each waits)

| Candidate | Family / source | Confidence | Why not now / dependency |
|-----------|-----------------|-----------|--------------------------|
| `ETHBTCRatioReversion` (z-score mean reversion of the ETH/BTC ratio) | cross-pair stat-meanreversion | **4/5 mechanism**, 3/5 overall | Genuine cointegration-style anchor, but freqtrade trades one pair per position — the ratio version approximates it. **Dependency: build only after #12 proves the cross-pair data path end-to-end.** Reuses #12's plumbing with an inverted signal. |
| `FreqAIMomentumGate` (LightGBM forward-return gate on a deterministic base) | ML overlay, freqtrade-native | **3/5** | FreqAI infra is battle-tested (LightGBM*/XGBoost*/SKLearnRF installed here, verified); standalone expectancy evidence is mixed. **Rule: first run Phase 6 on the best deterministic plan.** A FreqAI-first plan is premature. |
| `UniversalMACDTrend` (MACD zero-line cross + trend filter; freqtrade-strategies `UniversalMACD`) | momentum-trend | **3/5** | Battle-tested as community material, but adjacent to #5/#6/#10 — adopt only if the trend family shows one clear winner and MACD offers a *different* signal horizon. |
| Candlestick pattern confirmation (ta-lib CDL*, repo `PatternRecognition`) | pattern confirmation | **2/5 standalone, 4/5 as FreqAI features** | Weak standalone expectancy; strong as `%-cdl_*` feature columns feeding a Phase-6 model. Do not build a strategy around patterns alone. |
| `Session/hour-of-day` timing (repo `HourBasedStrategy`) | seasonality | **2/5** | Real but weak intraday structure; enormous data-mining surface (24 buckets). Note: Phase 6 already emits `%-day_of_week` / `%-hour_of_day` — the seasonality question is answered better *inside* FreqAI than as a standalone plan. |
| NostalgiaForInfinity-style multi-condition dip buying | dip buying at scale | **2/5 as a port, 4/5 as design input** | The most battle-tested freqtrade strategy in the world, and it *cannot* be ported: it needs DCA/rebuys (banned by Kotegawa K6, no exceptions), a 40-80-pair volume pairlist (we have 10 static majors), 5m spot long-only, and `exit_profit_only` machinery. Its transferable lessons — many independent tagged entry conditions, protective exits — already live in `EWODipHunter` and the protections layer. |
| PSAR-trailing trend rider (repo `CustomStoplossWithPSAR`) | dynamic-stop trend | **2/5** | A custom stoploss driven by a price-series indicator conflicts with the deterministic risk layer (YELLOW by default, compounding with dynamic leverage). If a trend plan passes Phase 5, a PSAR-trail A/B is a cheaper experiment than a new plan. |
| OBV / volume-divergence trend | volume divergence | **2/5** | Divergence detection needs swing pivots — fragile in vectorised form (lookahead-prone pivot detection is anti-pattern #1 bait). Revisit only via FreqAI features. |

## Researched and excluded (recorded so nobody re-researches)

| Candidate | Why out |
|-----------|---------|
| TWAP / AlmgrenChriss "strategy" (in the community repo) | Execution algorithms, not signal strategies — outside the 0-8 loop's purpose. |
| Cross-exchange arbitrage | Requires two exchange feeds; this repo is binanceusdm-only. |
| Open-interest-based signals | No historical OI on disk; freqtrade's downloader does not produce the needed history. Would require a new dataset (YELLOW, user decision). |
| Maker/grid range strategies | Need order-book-level fills; candle backtests cannot resolve them honestly. |
| Funding-timestamp momentum fade (fade the move into 00/08/16 UTC) | A *variant* of #8 FundingSkewCarry, not a plan — recorded here as a Phase-5 experiment note for that strategy. |
| Taker-buy / CVD order-flow proxies (buy/sell volume imbalance, cumulative volume delta) | Candle feathers carry OHLCV only (verified 2026-09-27: `date/open/high/low/close/volume`); freqtrade's downloader drops taker-buy volume. Needs a new dataset (YELLOW, user decision). |
| Mark-vs-last basis reversion (futures last vs 1h mark) | Mark price is 1h-blended; a basis-vs-mark signal cannot be resolved honestly in candle backtests. A Phase-5 experiment note for #8, not a plan. |

## Portfolio coverage after this batch

| Family | Plans | Note |
|--------|-------|------|
| band reversion | 1, 2, 3 | control + 2 challengers |
| dip buying | 4 | long-only by design |
| trend pullback | 5, 6, 7 | regime-gated variants |
| futures-native | 8, 9 | funding carry + liquidation fade |
| breakout | **10** | enter-on-strength was missing |
| vol compression->expansion | **11** | width filter inverted |
| cross-pair | **12** | only external-data signal |

Twelve plans, seven families. Before adding a thirteenth: the honest prior is
that most of these die at Phase 4-7 — *wait for the deaths to teach you what
family thirteen should be.*

Second pass (2026-09-27, below) was a user-requested deeper pass: five more
candidates covering the remaining portfolio gaps. They enter the backlog like
every other entry — nothing is pre-approved, and the same death-first prior
binds their promotion.

---

## Second research pass (2026-09-27)

User-requested deep analysis to extend the candidate list beyond the first
pass. Method: academic verification of mechanism evidence (NBER/RFS + arXiv via
verified fetches), local data-feasibility checks, and a portfolio-gap analysis
against the twelve plans' families, timeframes and data usage. Backlog only —
nothing promoted.

### Portfolio gaps found (why these candidates)

| Gap | Evidence |
|-----|----------|
| **No multi-day horizon** — all 12 plans are 5m-1h, minutes-to-hours holds | INDEX.md plan table |
| Band reversion death may be a **frequency artifact, not a mechanism failure** — the cost-floor lesson (0.2% win vs 0.1% cost) only binds at 15m; at 1d typical reversion wins are several % | `.agent/reports/BBRSIMeanReversion/DEAD.md` |
| No **session-anchored** levels — #10 is a rolling N-bar anchor; prior-day highs/lows are a session-boundary anchor (different mechanism, deterministic, no lookahead) | first-pass coverage table |
| Funding data on disk is used by **one** plan (#8, single-pair); a **cross-pair funding differential** is a distinct, untested mechanism | ENVIRONMENT.md data section |
| Protections cheat-sheet has **no 4h/1d conversions** (StoplossGuard 24h: 4h->6 / 1d->1 candles; MaxDrawdown 21d: 4h->126 / 1d->21, stop 3d: 4h->18 / 1d->3) — must precede any A1/A2 promotion | `00-TEMPLATE.md` cheat-sheet |
| Candle feathers carry **only `date/open/high/low/close/volume`** — no taker-buy, no quote volume | verified 2026-09-27 via pandas read_feather |

### Verified sources (second pass)

| Source | Verified | Finding |
|--------|----------|---------|
| Liu & Tsyvinski, "Risks and Returns of Cryptocurrency", RFS 34(6) 2021 (NBER w24877) | 2026-09-27 | "Strong time-series momentum effect" specific to crypto markets — anchors A1's mechanism |
| arXiv 2602.11708 (Feb 2026, "Systematic Trend-Following with Adaptive Portfolio Construction") | 2026-09-27 | Trend-following on **6-hour intervals** with vol-regime-calibrated trailing stops, rolling-Sharpe asset selection, long-short allocation; benchmarks against TSMOM. Validates A1's 4h design. Its asymmetric 70/30 allocation is drift-justified — our template requires that justification to be explicit (§3), and single-paper backtest Sharpe claims (2.41 on 150+ pairs) do not transfer to 10 static majors |
| arXiv 2212.06888 (He, Manela, Ross, von Wachter, "Fundamentals of Perpetual Futures") | 2026-09-27 | Perpetual no-arbitrage pricing with trading-cost bounds; "an implied arbitrage strategy yields high Sharpe ratios" — direct academic evidence the funding/basis premium is harvestable; anchors A4 |
| arXiv 2209.03307 (Angeris, Chitra, Evans, Lorig, "A primer on perpetuals") | 2026-09-27 | Funding-rate mechanics and replication — mechanism documentation for A4/#8 |
| Local venv + feathers | 2026-09-27 | `talib 0.6.8`, `pandas_ta 0.3.16` (ft fork), `technical/qtpylib 1.6.0` all importable — every candidate below needs no indicator beyond the approved catalog; candle files carry OHLCV only |

### Candidates (scored, best-first — backlog only)

| # | Candidate | Family | TF | Conf. | Hypothesis & the other side | Blockers (honest) |
|---|-----------|--------|-----|-------|------------------------------|-------------------|
| A1 | `TSMOMSwing` — sign of the N-day absolute return, long/short symmetric, vol-targeted leverage | time-series momentum (new horizon) | 4h | **4/5** | Crypto's documented time-series momentum (Liu & Tsyvinski RFS 2021; arXiv 2602.11708 validates the 4h-adjacent design). Other side: slow capital reallocation vs fast mean-reversion flow. Fills the portfolio's missing multi-day horizon; stress-tests funding-cost honesty (8h funding hits every multi-day hold). | Fewer trades (~100-400 on 10 pairs of 4h candles); needs the 4h protections conversions above before promotion; funding becomes a material cost, not noise; the paper's vol-regime trailing stop belongs in a Phase-5 A/B, not the deterministic risk layer |
| A2 | `DailyBandReversion` — BB z-score + RSI reversion at 1d | band reversion, higher-TF | 1d | **3/5** | Directly tests whether the BBRSIMeanReversion DEAD verdict (PF 0.79) was frequency- or mechanism-driven — what the portfolio ledger says deaths are for. Other side: same as plan 1. | Low trade count on 10 pairs (lookahead-analysis needs >= 10 trades, gotcha #9); must carry a clean kill criterion despite the family's DEAD prior; band plans 2/3 at 15m stay queued — this is the 1d variant, not a replacement |
| A3 | `PrevDayLevelBreakout` — break of prior-day high/low (PDH/PDL), optional floor-trader pivot fallback | session-anchored levels | 15m | **3/5** | 24/7 crypto still structures institutional daily flow; level-breakout is classic futures day-trading. Deterministic (prior day completed -> no lookahead). Other side: stop-cluster liquidity resting at prior-day extremes. | Adjacent to #10 — must beat it or offer a different signal horizon to justify a slot; 15m fees still bind on tight level targets; needs a 1d informative on 15m (~200 startup candles; MultiMATSL startup lesson applies) |
| A4 | `FundingSpreadRotation` — long deepest-negative funding / short most-positive across the 10 majors, BTC-regime-gated | futures-native cross-pair | 1h | **3/5** | Funding/basis carry has academic evidence (arXiv 2212.06888: "implied arbitrage strategy yields high Sharpe ratios"; arXiv 2209.03307 mechanics) and industrial scale (Ethena, CME cash-and-carry). Other side: leveraged directional traders paying funding to stay positioned. | **Dependency: build only after #8's Phase 4 verdict** — if single-pair carry dies on costs, the plumbing transfers but the mechanism needs re-scoring; reuses #8's funding plumbing + #12's rotation pattern |
| A5 | `VolRegimeSwitch` — NATR-percentile regime selects trend vs reversion sub-mode | vol-of-vol regime | 15m | 2/5 | Volatility clustering and regime-dependent behaviour (arXiv 2602.11708 documents regime-dependence). Other side: static-parameter traders in the wrong regime. | Adjacent to #7 ObeliskRSIRegime (two parameter sets) and #11 (squeeze) — redundancy risk (anti-pattern #7); promote only if both die and the vol-regime lesson survives |

Two new exclusions were added to the main excluded table above: taker-buy/CVD
order-flow proxies (no data on disk) and mark-vs-last basis reversion (honesty
risk -> Phase-5 experiment note for #8).

### Promotion note

Backlog only. Nothing on this list is pre-approved; promoting one is a normal
new-plan decision (YELLOW). Before promoting A1 or A2: add the 4h/1d
conversions to the `00-TEMPLATE.md` protections cheat-sheet (StoplossGuard 24h
lookback: 4h -> 6 / 1d -> 1 candles; MaxDrawdown 21d: 4h -> 126 / 1d -> 21,
stop 3d: 4h -> 18 / 1d -> 3). Framework fit is verified for all five:
futures-only mechanisms, candle backtests, approved-catalog indicators only,
data already on disk.
