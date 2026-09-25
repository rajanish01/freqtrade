# RESEARCH-BACKLOG — Candidate Futures Strategies (scored, 2026-09-26)

One-pass online research + portfolio-gap analysis. Sources: freqtrade/freqtrade-
strategies (5.5k stars, the official community repo), iterativv/NostalgiaForInfinity
(3.4k stars, 8 maintained generations — the most battle-tested freqtrade strategy),
the Donchian/Turtle lineage, the TTM-squeeze lineage, and cross-asset lead-lag
literature applied to BTC as the crypto market factor.

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
