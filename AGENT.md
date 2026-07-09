# Freqtrade Strategy Development Agent Guide

## Purpose

This document serves as the **primary guardrail** for AI agents assisting with Freqtrade strategy development. The goal is to build **production-ready, profitable trading strategies** through rigorous, evidence-based development.

**CRITICAL**: This is NOT a guide for quick profits. It's a framework for systematic strategy development with hard constraints to prevent common failures.

## Project Context

- **Framework**: Freqtrade (https://www.freqtrade.io/en/stable/)
- **Trading Modes**: USDT Perpetual Futures (primary), Spot (secondary)
- **Exchange**: Binance USDM Futures
- **Approach**: Iterative development with rigorous validation

---

## HARD CONSTRAINTS (Non-Negotiable)

These constraints MUST be met before ANY strategy is considered for production or FreqAI enhancement.

### 1. Minimum Backtest Requirements

| Requirement | Threshold | Rationale |
|-------------|-----------|-----------|
| **Backtest Duration** | >= 2 years | Must include bull, bear, and sideways markets |
| **Minimum Trades** | >= 200 total | Statistical significance requires sample size |
| **Trades per Month** | >= 8 average | Strategy must be active, not curve-fit to few trades |
| **Out-of-Sample Period** | >= 6 months | Final validation on unseen data |

### 2. Performance Thresholds (MUST PASS ALL)

| Metric | Hard Minimum | Rationale |
|--------|--------------|-----------|
| **Profit Factor** | > 1.3 | Must have positive edge after fees |
| **Total Profit** | > 0% | Cannot lose money over full backtest |
| **Max Drawdown** | < 25% | Capital preservation is paramount |
| **Worst Month** | > -15% | No catastrophic single-month losses |
| **Win Rate** | > 40% | Must win enough to be psychologically tradeable |

### 3. Robustness Checks (MUST PASS ALL)

| Check | Requirement | Rationale |
|-------|-------------|-----------|
| **Multi-Year Consistency** | Profitable in 2+ out of 3 years | Not dependent on single regime |
| **Long/Short Balance** | Both sides profitable OR one disabled | No hidden directional bias killing returns |
| **Parameter Sensitivity** | ±20% param change keeps PF > 1.0 | Not over-optimized to exact values |
| **Multiple Pairs** | Works on 3+ pairs | Not curve-fit to single instrument |

### 4. Anti-Overfitting Rules

| Rule | Constraint |
|------|------------|
| **Hyperopt Epochs** | Maximum 300 epochs per run |
| **Parameters** | Maximum 10 optimizable parameters |
| **Timerange Split** | Train: 70%, Validate: 30% (chronological) |
| **No Cherry-Picking** | Report ALL backtest results, not just best ones |

---

## Development Phases

### Phase 1: Rule-Based Strategy (REQUIRED)

**Goal**: Prove the core trading idea has edge WITHOUT machine learning.

```
1. Define clear hypothesis
   └─> "VWAP breakouts with trend filter should capture momentum"

2. Implement minimal viable strategy
   └─> Basic entry/exit rules, standard stoploss

3. **SYSTEMATIC TESTING MATRIX** (MANDATORY - see below)
   └─> Test ALL major configuration combinations
   └─> DO NOT rely on hunches or single configurations

4. If ANY configuration shows promise (PF > 1.0, DD < 30%):
   └─> RUN HYPEROPT on that configuration
   └─> Ask user to run hyperopt in separate shell
   └─> Test optimized params before concluding

5. If ALL configurations fail: Abandon strategy concept
   └─> Document evidence and move to different strategy

6. If PASS after hyperopt: Validate on out-of-sample
   └─> Must meet HARD CONSTRAINTS on unseen data
```

**EXIT CRITERIA FOR PHASE 1:**
- [ ] Profit Factor > 1.3 on 2+ year backtest
- [ ] Max Drawdown < 25%
- [ ] Profitable in at least 2 of 3 years tested
- [ ] Out-of-sample validation positive

---

## SYSTEMATIC TESTING MATRIX (MANDATORY)

**CRITICAL**: Before concluding ANY strategy has no edge, you MUST test across ALL major configuration dimensions. Do NOT make conclusions based on single configurations or hunches.

### Required Test Dimensions

| Dimension | Values to Test | Rationale |
|-----------|----------------|-----------|
| **Timeframe** | 5m, 15m, 1h, 4h | Different noise levels, signal quality |
| **Mode** | Breakout, Reversion (if applicable) | Opposite trading philosophies |
| **Direction** | Both, Long-only, Short-only | Market regime sensitivity |
| **Stoploss** | 2%, 3%, 5%, 8%, 10% | Risk tolerance vs. noise |
| **Filters** | With/without trend filter | Filter effectiveness |

### Minimum Test Coverage

You MUST run at least these configurations:

```
1. Primary timeframe (15m) × Both modes × Both directions × 5% SL
2. Higher timeframe (1h) × Both modes × Both directions × 5% SL  
3. Even higher timeframe (4h) × Both modes × Both directions × 5% SL
4. Best timeframe × Long-only × Different stoplosses (3%, 5%, 8%)
5. Best timeframe × With/without trend filter
```

**Minimum: 10-15 backtests before any verdict**

### Test Results Matrix Template

Document ALL results in this format:

```
| Test | TF | Mode | Direction | SL | Filter | Profit% | DD% | Trades | PF | Verdict |
|------|-----|------|-----------|-----|--------|---------|-----|--------|-----|---------|
| 1 | 15m | Breakout | Both | 5% | ON | -X% | X% | XXX | X.XX | FAIL |
| 2 | 1h | Reversion | Long | 5% | ON | +X% | X% | XXX | X.XX | PROMISING |
...
```

### When to Run Hyperopt

**TRIGGER**: If ANY configuration shows:
- Profit Factor > 1.0 (even slightly profitable)
- Max Drawdown < 30%
- Reasonable trade count (>100)

**ACTION**: 
1. Stop testing other configurations
2. Ask user to run hyperopt on the promising configuration
3. Provide exact hyperopt command
4. Wait for optimized parameters
5. Backtest with optimized params
6. THEN continue evaluation

### Hyperopt Request Template

```
A promising configuration was found:
- Config: [timeframe] / [mode] / [direction] / [stoploss]
- Result: PF [X.XX], DD [X%], [XXX] trades

Please run hyperopt to optimize this configuration:

cd /Users/rajanish/Workspace/freqtrade && freqtrade hyperopt \
  --config user_data/config_<strategy>.json \
  --strategy <StrategyName> \
  --timerange 20220101-20231231 \
  --spaces buy sell \
  --hyperopt-loss SharpeHyperOptLossDaily \
  --epochs 200 \
  --min-trades 100 \
  --random-state 42 \
  -j 4

After hyperopt completes, please share:
1. Best epoch results
2. The generated params
```

### Final Verdict Requirements

Before declaring a strategy has **NO EDGE**, you MUST have:

1. **Tested 10+ configurations** across the matrix dimensions
2. **Run hyperopt** on any configuration with PF > 1.0
3. **Documented all results** in the matrix format
4. **Clear evidence** that no configuration meets hard constraints

**DO NOT** conclude based on:
- Single configuration failures
- Hunches about what "should" work
- Untested parameter combinations
- Non-optimized default parameters

### Phase 2: FreqAI Enhancement (OPTIONAL)

**PREREQUISITE**: Phase 1 strategy MUST meet all exit criteria.

**Goal**: Use ML to improve an ALREADY PROFITABLE strategy.

```
1. Start with profitable rule-based strategy
   └─> FreqAI should ENHANCE, not RESCUE

2. Add ML for specific improvements:
   - Regime classification (when to trade)
   - Entry timing refinement
   - Position sizing optimization

3. Backtest FreqAI version on SAME full period
   └─> Must still meet all HARD CONSTRAINTS

4. Compare: FreqAI vs Rule-Based
   └─> FreqAI must show meaningful improvement (>20% better PF)

5. Extended validation
   └─> Paper trade 4+ weeks before live
```

**EXIT CRITERIA FOR PHASE 2:**
- [ ] All Phase 1 criteria still met
- [ ] FreqAI version shows >20% improvement in Profit Factor
- [ ] No degradation in worst-case metrics (max DD, worst month)
- [ ] 4+ weeks successful paper trading

---

## Strategy Evaluation Template

When evaluating ANY strategy backtest, report in this format:

```
## Strategy: [Name]
## Period: [Start] - [End] ([X] years)
## Market Conditions: [Bull/Bear/Mixed]

### HARD CONSTRAINT CHECK
| Constraint | Required | Actual | Status |
|------------|----------|--------|--------|
| Backtest Duration | >= 2 years | X.X years | PASS/FAIL |
| Total Trades | >= 200 | XXX | PASS/FAIL |
| Profit Factor | > 1.3 | X.XX | PASS/FAIL |
| Total Profit | > 0% | +/-X.XX% | PASS/FAIL |
| Max Drawdown | < 25% | X.XX% | PASS/FAIL |
| Worst Month | > -15% | -X.XX% | PASS/FAIL |

### VERDICT: [PASS/FAIL] - [Ready for Phase 2 / Needs iteration / Abandon]
```

---

## Common Failure Modes (Lessons Learned)

### 1. The "High Win Rate Trap"
- **Symptom**: 80%+ win rate but negative total profit
- **Cause**: Small winners, large losers (inverted risk:reward)
- **Solution**: Ensure avg_win > avg_loss * (1 - win_rate) / win_rate

### 2. The "Hyperopt Illusion"
- **Symptom**: Amazing in-sample results, terrible out-of-sample
- **Cause**: Over-optimized to specific price patterns
- **Solution**: Limit epochs, parameters, and always validate OOS

### 3. The "Trailing Stop Killer"
- **Symptom**: Trailing stops cause more losses than they prevent
- **Cause**: Freqtrade ratchets stops - any tighter value locks in
- **Solution**: Avoid custom_stoploss trailing; use fixed stops

### 4. The "Counter-Trend Destroyer"
- **Symptom**: Strategy profitable in ranging markets, destroyed in trends
- **Cause**: Taking both long/short without trend filter
- **Solution**: Add higher-timeframe trend alignment (daily EMA)

### 5. The "Noise Trading Trap"
- **Symptom**: Many trades, consistent small losses
- **Cause**: Signal (e.g., VWAP cross) fires on noise, not real moves
- **Solution**: Use higher timeframe (15m/1h) or stricter filters

---

## Long-Running Commands Protocol

For hyperopt and extensive backtests that take >10 minutes:

1. **Agent provides the command** with full parameters
2. **User runs in separate shell** to avoid timeout
3. **User reports back** with results summary
4. **Agent analyzes and continues** iteration

### Hyperopt Command Template
```bash
cd /Users/rajanish/Workspace/freqtrade && freqtrade hyperopt \
  --config user_data/config_<strategy>.json \
  --strategy <StrategyName> \
  --timerange <YYYYMMDD>-<YYYYMMDD> \
  --spaces buy sell \
  --hyperopt-loss CalmarHyperOptLoss \
  --epochs 200 \
  --min-trades 100 \
  --random-state 42 \
  -j 4
```

### Multi-Year Backtest Template
```bash
cd /Users/rajanish/Workspace/freqtrade && freqtrade backtesting \
  --config user_data/config_<strategy>.json \
  --strategy <StrategyName> \
  --timerange 20220101-20241231 \
  --breakdown month \
  --cache none
```

---

## File Organization

```
freqtrade/
├── user_data/
│   ├── strategies/           # Strategy files
│   │   ├── <Strategy>.py
│   │   └── <Strategy>.json   # Hyperopt params (auto-generated)
│   ├── config_<strategy>.json # Strategy-specific config
│   ├── data/                 # Historical data
│   ├── backtest_results/     # Backtest outputs
│   └── hyperopt_results/     # Hyperopt outputs
├── AGENT.md                  # This file (PRIMARY GUARDRAILS)
├── STRATEGY_TEMPLATE.md      # Strategy design template
├── BACKTEST_CHECKLIST.md     # Validation checklist
├── FREQAI_GUIDE.md          # FreqAI integration guide
└── COMMANDS_REFERENCE.md     # Common commands
```

---

## Decision Tree: What To Do Next

```
Is strategy profitable over 2+ years?
├── NO → Is the core concept sound?
│        ├── NO → Abandon, try different strategy concept
│        └── YES → Iterate: adjust parameters, add filters
│
└── YES → Does it meet ALL hard constraints?
          ├── NO → Which constraint fails?
          │        ├── Drawdown too high → Reduce position size or add stops
          │        ├── Profit factor low → Improve entry quality or exit timing
          │        └── Too few trades → Relax filters (carefully)
          │
          └── YES → CONGRATULATIONS! Strategy ready for:
                    1. Out-of-sample validation
                    2. Paper trading (2+ weeks)
                    3. (Optional) FreqAI enhancement
```

---

## Reference Documentation

- Freqtrade Docs: https://www.freqtrade.io/en/stable/
- Strategy Customization: https://www.freqtrade.io/en/stable/strategy-customization/
- Hyperopt: https://www.freqtrade.io/en/stable/hyperopt/
- FreqAI: https://www.freqtrade.io/en/stable/freqai/
- Backtesting: https://www.freqtrade.io/en/stable/backtesting/
