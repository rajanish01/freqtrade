# Backtest Validation Checklist

## Purpose

This checklist ensures every backtest is evaluated rigorously against the hard constraints defined in AGENT.md. **No strategy proceeds to production or FreqAI without passing ALL checks.**

---

## Pre-Backtest Checklist

Before running any backtest, verify:

- [ ] **Data quality**: Data downloaded for full period without gaps
- [ ] **Timeframes**: All required timeframes available (primary + informative)
- [ ] **Pairs**: All target pairs have sufficient history
- [ ] **Config**: Correct config file with proper exchange/futures settings
- [ ] **Strategy**: No syntax errors, strategy loads cleanly

```bash
# Verify data availability
freqtrade list-data --config user_data/config.json --show-timerange

# Test strategy loads
python -c "from user_data.strategies.YourStrategy import YourStrategy; print('OK')"
```

---

## Backtest Execution

### Standard Backtest Command

```bash
freqtrade backtesting \
  --config user_data/config_<strategy>.json \
  --strategy <StrategyName> \
  --timerange 20220101-20241231 \
  --breakdown month \
  --cache none
```

### Required Periods

| Period | Purpose | Command Addition |
|--------|---------|------------------|
| Full (2+ years) | Overall performance | `--timerange 20220101-20241231` |
| Bear market | Stress test | `--timerange 20220101-20221231` |
| Bull market | Trend capture | `--timerange 20230101-20231231` |
| Out-of-sample | Final validation | `--timerange 20240701-20241231` |

---

## Post-Backtest Evaluation

### Step 1: Hard Constraint Check

Fill in this table after EVERY backtest:

```
## Strategy: _______________
## Period: ________ to ________ (_____ years)

### HARD CONSTRAINTS (All must PASS)

| # | Constraint | Required | Actual | Status |
|---|------------|----------|--------|--------|
| 1 | Backtest Duration | >= 2 years | | |
| 2 | Total Trades | >= 200 | | |
| 3 | Profit Factor | > 1.3 | | |
| 4 | Total Profit | > 0% | | |
| 5 | Max Drawdown | < 25% | | |
| 6 | Worst Month | > -15% | | |
| 7 | Win Rate | > 40% | | |

### VERDICT: [ ] PASS - All constraints met
             [ ] FAIL - Constraint(s) #___ failed
```

### Step 2: Quality Metrics

```
### QUALITY METRICS (For comparison, not pass/fail)

| Metric | Value | Rating |
|--------|-------|--------|
| Sharpe Ratio | | Poor(<0.5) / OK(0.5-1) / Good(1-2) / Excellent(2+) |
| Sortino Ratio | | Poor(<0.5) / OK(0.5-1.5) / Good(1.5-2.5) / Excellent(2.5+) |
| Calmar Ratio | | Poor(<0.5) / OK(0.5-1) / Good(1-2) / Excellent(2+) |
| Expectancy | | Negative / Low(0-0.5) / Good(0.5-1) / Excellent(1+) |
| Avg Trade Duration | | |
| Max Consecutive Losses | | |
```

### Step 3: Breakdown Analysis

```
### MONTHLY BREAKDOWN

| Month | Trades | Profit | PF | Win% | Notes |
|-------|--------|--------|-----|------|-------|
| Jan 2022 | | | | | |
| Feb 2022 | | | | | |
| ... | | | | | |

Months with PF < 1.0: ___
Months with > -10% loss: ___
Best month: ___ (+___%)
Worst month: ___ (-___%)
```

### Step 4: Long/Short Analysis

```
### DIRECTIONAL PERFORMANCE

| Direction | Trades | Profit | Win% | Assessment |
|-----------|--------|--------|------|------------|
| Long | | | | |
| Short | | | | |

ISSUE CHECK:
- [ ] Both directions profitable
- [ ] No hidden directional bias destroying returns
- [ ] If one side losing: consider disabling it
```

### Step 5: Exit Analysis

```
### EXIT REASON BREAKDOWN

| Exit Type | Count | Avg Profit | Total Profit | Assessment |
|-----------|-------|------------|--------------|------------|
| ROI | | | | Should be primary profit source |
| Stop Loss | | | | Should be < 30% of trades |
| Signal Exit | | | | |
| Trailing Stop | | | | Watch for issues |
| Force Exit | | | | Should be minimal |

ISSUE CHECK:
- [ ] ROI exits are main profit source
- [ ] Stop losses not exceeding ROI profits
- [ ] No trailing stop issues (unexpected losses)
```

---

## Decision Matrix

Based on backtest results, determine next action:

```
┌─────────────────────────────────────────────────────────┐
│           HAVE YOU COMPLETED SYSTEMATIC TESTING?        │
│           (See AGENT.md - Systematic Testing Matrix)    │
└─────────────────────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
             NO                        YES
              │                         │
              ▼                         ▼
    ┌─────────────────┐      ┌─────────────────────────┐
    │ STOP! Complete  │      │ Any config with PF>1.0? │
    │ systematic test │      └─────────────────────────┘
    │ matrix first    │                  │
    │ (10+ configs)   │        ┌─────────┴─────────┐
    └─────────────────┘        ▼                   ▼
                             YES                   NO
                              │                    │
                              ▼                    ▼
                    ┌─────────────────┐   ┌────────────────┐
                    │ RUN HYPEROPT on │   │ ABANDON        │
                    │ promising config│   │ strategy       │
                    │ before verdict  │   │ (document why) │
                    └─────────────────┘   └────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │ Test optimized  │
                    │ params on full  │
                    │ backtest period │
                    └─────────────────┘
                              │
                              ▼
              ┌───────────────────────────────────┐
              │      ALL HARD CONSTRAINTS MET?    │
              └───────────────────────────────────┘
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
               YES                        NO
                 │                         │
                 ▼                         ▼
       ┌─────────────────┐      ┌─────────────────────────┐
       │ Proceed to      │      │ Which constraint failed? │
       │ Out-of-Sample   │      └─────────────────────────┘
       │ Validation      │                  │
       └─────────────────┘        ┌─────────┴─────────┐
                 │                ▼                   ▼
                 │         Profit/PF Low        Drawdown High
                 │                │                   │
                 ▼                ▼                   ▼
       ┌─────────────────┐  ┌───────────────┐  ┌────────────────┐
       │ OOS also meets  │  │ Try different │  │ Reduce position│
       │ constraints?    │  │ configs from  │  │ size or add    │
       └─────────────────┘  │ test matrix   │  │ stop guards    │
                 │          └───────────────┘  └────────────────┘
       ┌─────────┴─────────┐
       ▼                   ▼
      YES                  NO
       │                   │
       ▼                   ▼
   ┌────────────┐    ┌─────────────┐
   │ STRATEGY   │    │ Overfitting │
   │ APPROVED   │    │ - Iterate   │
   │ for paper  │    │ - Or abandon│
   │ trading    │    └─────────────┘
   └────────────┘
```

---

## Systematic Testing Checklist

**MANDATORY before any strategy verdict. Reference: AGENT.md**

### Test Matrix Completion

- [ ] **Timeframe tests**: 5m, 15m, 1h, 4h all tested
- [ ] **Mode tests**: Breakout AND Reversion tested (if applicable)
- [ ] **Direction tests**: Both, Long-only, Short-only tested
- [ ] **Stoploss tests**: At least 3%, 5%, 8% tested
- [ ] **Filter tests**: With/without key filters tested
- [ ] **Total configs tested**: >= 10 configurations

### Results Documentation

```
| Test | TF | Mode | Dir | SL | Filter | Profit% | DD% | Trades | PF | Verdict |
|------|-----|------|-----|-----|--------|---------|-----|--------|-----|---------|
| 1 | | | | | | | | | | |
| 2 | | | | | | | | | | |
| 3 | | | | | | | | | | |
| 4 | | | | | | | | | | |
| 5 | | | | | | | | | | |
| 6 | | | | | | | | | | |
| 7 | | | | | | | | | | |
| 8 | | | | | | | | | | |
| 9 | | | | | | | | | | |
| 10 | | | | | | | | | | |
```

### Hyperopt Trigger Check

- [ ] **Any config with PF > 1.0?** → MUST run hyperopt before concluding
- [ ] **Any config with DD < 30% and trades > 100?** → PROMISING, run hyperopt
- [ ] **Hyperopt command provided to user?**
- [ ] **Optimized params tested on full backtest?**

### Final Verdict Requirements

Before declaring **NO EDGE**:
- [ ] 10+ configurations tested and documented
- [ ] Hyperopt run on any promising configs (PF > 1.0)
- [ ] All results documented in matrix format
- [ ] Clear evidence no configuration meets hard constraints

**DO NOT CONCLUDE WITHOUT:**
- Running systematic tests across all dimensions
- Testing optimized params (not just default hunches)
- Documenting all evidence

---

## Red Flags to Watch

### Immediate Rejection

- [ ] **Profit Factor < 1.0**: Strategy has negative edge
- [ ] **Max DD > 50%**: Unacceptable capital risk
- [ ] **< 50 trades**: Insufficient data for conclusions
- [ ] **All profit from one month**: Likely curve-fit to single event

### Warning Signs (Investigate Further)

- [ ] Win rate > 90%: Likely holding losers too long
- [ ] Win rate < 35%: May have execution issues
- [ ] Avg loser >> Avg winner: Inverted risk:reward
- [ ] Most profits from shorts in bull market: Counter-trend luck
- [ ] Huge gap between best and worst month: Inconsistent

### Signs of Overfitting

- [ ] Great in-sample, poor out-of-sample
- [ ] Only works on specific date ranges
- [ ] Requires very specific parameter values
- [ ] Many filters/conditions that rarely all align
- [ ] Performance degrades with ±10% parameter changes

---

## Out-of-Sample Validation Protocol

**Only perform after passing all hard constraints on in-sample data.**

### Split Ratios

| Total Period | Training | Validation |
|--------------|----------|------------|
| 3 years | 2 years (Jan 2022 - Dec 2023) | 1 year (Jan 2024 - Dec 2024) |
| 2 years | 18 months | 6 months |

### OOS Requirements

The out-of-sample period must ALSO meet:

- [ ] Profit Factor > 1.2 (slightly relaxed from 1.3)
- [ ] Total Profit > 0%
- [ ] Max Drawdown < 30% (slightly relaxed from 25%)
- [ ] No single month > -20% loss

### OOS Comparison

```
### IN-SAMPLE vs OUT-OF-SAMPLE

| Metric | In-Sample | Out-of-Sample | Degradation |
|--------|-----------|---------------|-------------|
| Profit Factor | | | |
| Total Profit | | | |
| Max Drawdown | | | |
| Win Rate | | | |

Acceptable degradation: < 30% worse on key metrics
Red flag: > 50% worse indicates overfitting
```

---

## Final Approval Checklist

Before declaring a strategy ready for paper trading:

- [ ] **In-sample**: All hard constraints met
- [ ] **Out-of-sample**: Relaxed constraints met
- [ ] **Multi-year**: Profitable in 2+ of 3 years
- [ ] **Directional**: Both long/short work OR losing side disabled
- [ ] **Monthly**: No single month > -15% loss
- [ ] **Parameter**: ±20% change doesn't break strategy
- [ ] **Documentation**: Strategy logic clearly documented

**Signature**: _________________ **Date**: _________________

---

## Appendix: Quick Reference Commands

```bash
# Full backtest with breakdown
freqtrade backtesting --config config.json --strategy Strategy \
  --timerange 20220101-20241231 --breakdown month --cache none

# Out-of-sample only
freqtrade backtesting --config config.json --strategy Strategy \
  --timerange 20240701-20241231 --breakdown month

# Show hyperopt best result
freqtrade hyperopt-show --config config.json --best --print-json

# List profitable hyperopt results
freqtrade hyperopt-list --config config.json --profitable --min-trades 100
```
