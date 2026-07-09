# Freqtrade Strategy Development Template

## Before You Start: Critical Questions

### 1. Does Your Strategy Concept Have Empirical Backing?

**DO NOT** start coding until you can answer YES to at least one:

- [ ] Based on academic research (momentum, mean-reversion, carry, etc.)
- [ ] Has documented track record in similar markets
- [ ] Based on clear market microstructure inefficiency
- [ ] Exploits behavioral bias with logical explanation

**RED FLAGS** - Strategy concepts that usually FAIL:
- "VWAP cross" or "Moving average cross" alone (too simple, no edge)
- "Buy oversold RSI" without context (everyone does this)
- "Pattern recognition" without statistical validation
- Anything that sounds too simple to be true

### 2. Strategy Design Checklist

| Question | Your Answer |
|----------|-------------|
| What market inefficiency am I exploiting? | |
| Why does this inefficiency exist? | |
| Why hasn't it been arbitraged away? | |
| What are the expected win rate and risk:reward? | |
| In what market conditions will this FAIL? | |

---

## Strategy Design Document Template

### Section 1: Hypothesis

```
INEFFICIENCY: [What market behavior are you exploiting?]
  - Example: "Trend continuation after consolidation breakouts"
  - NOT: "Buy when indicator crosses" (this is not an inefficiency)

WHY IT EXISTS: [Why does this opportunity persist?]
  - Example: "Institutional order flow causes momentum after breakouts"
  - NOT: "Because the indicator said so"

EXPECTED EDGE: [Quantify your expected advantage]
  - Win Rate: [Realistic estimate, e.g., 45-55%]
  - Risk:Reward: [Target, e.g., 1:2 or better]
  - Trade Frequency: [Per day/week]

FAILURE CONDITIONS: [When will this strategy lose money?]
  - Example: "Choppy, range-bound markets with false breakouts"
```

### Section 2: Entry Logic

```
PRIMARY SIGNAL:
  - Specific condition that triggers entry
  - Must be unambiguous and testable

CONFIRMATION FILTERS (choose wisely - each filter reduces trades):
  - Trend alignment: [Higher timeframe direction]
  - Volume confirmation: [Above average volume]
  - Momentum confirmation: [RSI/MACD alignment]
  - Volatility filter: [ATR within range]

REGIME FILTER (CRITICAL for profitability):
  - How do you detect favorable conditions?
  - How do you AVOID unfavorable conditions?
  - Example: "Only trade when daily trend is established (price > EMA50)"
```

### Section 3: Exit Logic

```
TAKE PROFIT:
  - Primary method: [ROI table / Signal-based / Target price]
  - Expected holding time: [Minutes / Hours / Days]

STOP LOSS:
  - Type: [Fixed % / ATR-based / Structure-based]
  - Value: [Specific number, e.g., 3% or 2*ATR]
  - Rationale: [Why this stop distance?]

TRAILING STOP (use with caution):
  - Enable: [Yes/No] 
  - WARNING: Freqtrade trails can cause unexpected losses
  - If Yes, specify activation and trail distance
```

### Section 4: Risk Management

```
POSITION SIZING:
  - Method: [Fixed stake / Risk-based / Kelly]
  - Risk per trade: [% of equity, recommend 1-2%]

LEVERAGE (futures only):
  - Maximum: [Recommend <= 3x for beginners]
  - Dynamic: [Based on volatility? Y/N]

PORTFOLIO PROTECTION:
  - Max concurrent trades: [Number]
  - Max drawdown halt: [% to pause trading]
  - Stoploss guard: [Consecutive losses to pause]
```

---

## Risk:Reward Mathematics

**Before building, verify your math makes sense:**

```
Break-even Win Rate = 1 / (1 + Risk:Reward Ratio)

Example:
- If your avg winner = 2% and avg loser = 3%
- Risk:Reward = 2/3 = 0.67
- Break-even = 1 / (1 + 0.67) = 60%
- You need > 60% win rate just to break even!

Target:
- Risk:Reward >= 1.0 (avg winner >= avg loser)
- OR Win Rate high enough to compensate
- Profit Factor = (Win Rate * Avg Win) / ((1 - Win Rate) * Avg Loss) > 1.3
```

---

## Strategy Code Template

```python
# {StrategyName}.py
# 
# HYPOTHESIS: {What market inefficiency are you exploiting?}
# TIMEFRAME: {Primary timeframe}
# MARKET: {Futures/Spot, which pairs}
# EXPECTED: Win Rate ~{X}%, Risk:Reward ~{Y}:1
#
# HARD CONSTRAINTS CHECK (from AGENT.md):
# - [ ] Backtest >= 2 years
# - [ ] Trades >= 200
# - [ ] Profit Factor > 1.3
# - [ ] Max Drawdown < 25%
# - [ ] Worst Month > -15%

import logging
from datetime import datetime
from functools import reduce
from typing import Optional

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import (
    BooleanParameter,
    DecimalParameter,
    IntParameter,
    IStrategy,
    informative,
)

logger = logging.getLogger(__name__)


class {StrategyName}(IStrategy):
    """
    {One-line description}
    
    Entry: {Brief entry logic}
    Exit: {Brief exit logic}
    Risk: {Brief risk approach}
    """

    INTERFACE_VERSION = 3

    # === BASIC SETTINGS ===
    timeframe = "15m"  # Avoid 5m unless you have specific reason
    
    can_short = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False  # Let ROI work
    process_only_new_candles = True
    
    startup_candle_count: int = 200

    # === STOPLOSS ===
    # IMPORTANT: Keep it simple. Avoid custom_stoploss unless necessary.
    stoploss = -0.05  # 5% - adjust based on your strategy
    use_custom_stoploss = False  # Set True only if you NEED dynamic stops
    
    # === ROI TABLE ===
    # Tighter ROI = lock in profits faster
    # Looser ROI = let winners run
    minimal_roi = {
        "0": 0.04,      # 4% immediate
        "60": 0.025,    # 2.5% after 1 hour
        "180": 0.015,   # 1.5% after 3 hours
        "360": 0.01,    # 1% after 6 hours
    }
    
    # === TRAILING STOP ===
    # WARNING: Can cause unexpected losses. Use with caution.
    trailing_stop = False
    
    # === HYPEROPT PARAMETERS ===
    # LIMIT: Maximum 10 optimizable parameters (see AGENT.md)
    
    # Example parameters - customize for your strategy
    # signal_period = IntParameter(10, 50, default=20, space="buy", optimize=True)
    # use_filter = BooleanParameter(default=True, space="buy", optimize=True)

    # === INFORMATIVE TIMEFRAMES ===
    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Daily timeframe for MAJOR trend direction.
        CRITICAL: Use this to prevent counter-trend trades.
        """
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["trend_bullish"] = dataframe["close"] > dataframe["ema50"]
        dataframe["trend_bearish"] = dataframe["close"] < dataframe["ema50"]
        return dataframe

    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Hourly for medium-term context"""
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["adx"] = ta.ADX(dataframe)
        return dataframe

    # === INDICATORS ===
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Calculate indicators on primary timeframe"""
        
        # Core indicators
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        
        # Your strategy-specific indicators here
        
        return dataframe

    # === ENTRY LOGIC ===
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define entry conditions.
        
        IMPORTANT: Always include trend alignment filter!
        """
        df = dataframe
        
        # === LONG CONDITIONS ===
        long_conditions = [
            # 1. TREND ALIGNMENT (CRITICAL)
            df["trend_bullish_1d"] == True,  # Only long in uptrend
            
            # 2. Primary signal
            # df["your_signal"] == True,
            
            # 3. Confirmations (optional, but helpful)
            # df["rsi"] < 70,
            
            # 4. Validity
            df["volume"] > 0,
        ]
        
        if long_conditions:
            df.loc[
                reduce(lambda a, b: a & b, long_conditions),
                ["enter_long", "enter_tag"]
            ] = (1, "long_signal")
        
        # === SHORT CONDITIONS ===
        short_conditions = [
            # 1. TREND ALIGNMENT (CRITICAL)
            df["trend_bearish_1d"] == True,  # Only short in downtrend
            
            # 2. Primary signal
            # df["your_signal"] == True,
            
            # 3. Confirmations
            # df["rsi"] > 30,
            
            # 4. Validity
            df["volume"] > 0,
        ]
        
        if short_conditions:
            df.loc[
                reduce(lambda a, b: a & b, short_conditions),
                ["enter_short", "enter_tag"]
            ] = (1, "short_signal")
        
        return df

    # === EXIT LOGIC ===
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """Signal-based exits (beyond ROI/stoploss)"""
        
        # Example: Exit long on RSI overbought
        # dataframe.loc[
        #     (dataframe["rsi"] > 75),
        #     ["exit_long", "exit_tag"]
        # ] = (1, "rsi_exit")
        
        return dataframe

    # === PROTECTIONS ===
    @property
    def protections(self):
        """Portfolio-level risk management"""
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 3},
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 288,
                "trade_limit": 10,
                "stop_duration_candles": 288,
                "max_allowed_drawdown": 0.15,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 48,
                "trade_limit": 3,
                "stop_duration_candles": 48,
                "only_per_pair": False,
            },
        ]
```

---

## Hyperopt Guidelines

### Anti-Overfitting Rules (from AGENT.md)

| Rule | Limit |
|------|-------|
| Max epochs per run | 300 |
| Max optimizable parameters | 10 |
| Min trades required | 100 |
| Train/Validate split | 70/30 chronological |

### Recommended Workflow

**CRITICAL**: Before hyperopt, you MUST complete the Systematic Testing Matrix (see AGENT.md).
Do NOT run hyperopt on random configurations - test systematically first to find promising setups.

```bash
# PREREQUISITE: Complete Systematic Testing Matrix first!
# Test across: timeframes (5m,15m,1h,4h) × modes × directions × stoplosses
# Only proceed to hyperopt when you find a config with PF > 1.0 or DD < 30%

# Step 1: Optimize entry parameters on PROMISING config
freqtrade hyperopt \
  --config user_data/config.json \
  --strategy YourStrategy \
  --timerange 20220101-20231231 \
  --spaces buy \
  --hyperopt-loss SharpeHyperOptLossDaily \
  --epochs 200 \
  --min-trades 100 \
  --random-state 42 \
  -j 4

# Step 2: Optimize exit parameters (with best buy params)
freqtrade hyperopt \
  --config user_data/config.json \
  --strategy YourStrategy \
  --timerange 20220101-20231231 \
  --spaces sell \
  --hyperopt-loss SharpeHyperOptLossDaily \
  --epochs 200 \
  --min-trades 100 \
  --random-state 42 \
  -j 4

# Step 3: Backtest OPTIMIZED params on FULL period (not just training)
freqtrade backtesting \
  --config user_data/config.json \
  --strategy YourStrategy \
  --timerange 20220101-20241231 \
  --breakdown month \
  --cache none

# Step 4: Validate on out-of-sample
freqtrade backtesting \
  --config user_data/config.json \
  --strategy YourStrategy \
  --timerange 20240101-20241231 \
  --breakdown month
```

### CRITICAL: Test Changes on Optimized Params

**DO NOT** test configuration changes with default/hunch-based params if you haven't optimized.

```
WRONG WORKFLOW:
1. Change timeframe from 15m to 1h
2. Run backtest with default params
3. See bad results, conclude "1h doesn't work"
4. Never actually optimized for 1h

RIGHT WORKFLOW:
1. Change timeframe from 15m to 1h  
2. Run hyperopt to find optimal params FOR 1h
3. Backtest with optimized 1h params
4. THEN conclude whether 1h works
```

### When to Run Hyperopt

| Situation | Action |
|-----------|--------|
| Testing new timeframe | MUST run hyperopt for that timeframe |
| Testing new mode (breakout vs reversion) | MUST run hyperopt for that mode |
| Found config with PF > 1.0 | MUST run hyperopt to optimize |
| Found config with DD < 30% | SHOULD run hyperopt (promising) |
| All configs show PF < 0.8, DD > 50% | Can conclude no edge (after 10+ tests) |

### Loss Functions

| Function | Best For |
|----------|----------|
| `CalmarHyperOptLoss` | Balanced (recommended default) |
| `SharpeHyperOptLoss` | Risk-adjusted returns |
| `SortinoHyperOptLoss` | Minimize downside |
| `MaxDrawDownHyperOptLoss` | Capital preservation |

---

---

## Systematic Testing Matrix (MANDATORY)

**CRITICAL**: Before concluding ANY strategy has no edge, you MUST complete systematic testing.
Reference: AGENT.md for full requirements.

### Required Test Dimensions

| Dimension | Values | Why |
|-----------|--------|-----|
| Timeframe | 5m, 15m, 1h, 4h | Noise levels vary dramatically |
| Mode | Breakout, Reversion | Opposite philosophies need separate testing |
| Direction | Both, Long-only, Short-only | Market regime affects direction profitability |
| Stoploss | 2%, 3%, 5%, 8%, 10% | Critical for profitability |
| Filters | On/Off for key filters | Filter effectiveness varies by config |

### Minimum Test Coverage

Run AT LEAST these 10 configurations before any verdict:

```
 1. 15m / Breakout  / Both      / 5% SL / Filters ON
 2. 15m / Reversion / Both      / 5% SL / Filters ON
 3. 1h  / Breakout  / Both      / 5% SL / Filters ON
 4. 1h  / Reversion / Both      / 5% SL / Filters ON
 5. 4h  / Breakout  / Both      / 5% SL / Filters ON
 6. 4h  / Reversion / Both      / 5% SL / Filters ON
 7. Best TF / Best Mode / Long-only  / 5% SL / Filters ON
 8. Best TF / Best Mode / Short-only / 5% SL / Filters ON
 9. Best TF / Best Mode / Best Dir   / 3% SL / Filters ON
10. Best TF / Best Mode / Best Dir   / 8% SL / Filters ON
```

### Results Matrix Template

```
| # | TF | Mode | Dir | SL | Filter | Profit% | DD% | Trades | PF | Verdict |
|---|-----|------|-----|-----|--------|---------|-----|--------|-----|---------|
| 1 | 15m | Break | Both | 5% | ON | | | | | |
| 2 | 15m | Rever | Both | 5% | ON | | | | | |
| 3 | 1h | Break | Both | 5% | ON | | | | | |
| 4 | 1h | Rever | Both | 5% | ON | | | | | |
| 5 | 4h | Break | Both | 5% | ON | | | | | |
| 6 | 4h | Rever | Both | 5% | ON | | | | | |
| 7 | | | Long | 5% | ON | | | | | |
| 8 | | | Short | 5% | ON | | | | | |
| 9 | | | | 3% | ON | | | | | |
| 10 | | | | 8% | ON | | | | | |
```

### Hyperopt Trigger Criteria

**IF ANY of these are true, MUST run hyperopt before concluding:**

- [ ] Profit Factor > 1.0 (even slightly profitable)
- [ ] Max Drawdown < 30% with >100 trades
- [ ] Win rate > 60% (even if total negative)

**Hyperopt Request Template:**

```
PROMISING CONFIG FOUND:
- Configuration: [TF] / [Mode] / [Direction] / [Stoploss]
- Results: PF [X.XX], DD [X%], [XXX] trades, [X%] profit

Please run hyperopt in separate terminal:

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

After completion, share:
1. Best epoch number and metrics
2. The optimized parameters
```

---

## Common Mistakes to Avoid

### 1. No Trend Filter
**Wrong**: Taking longs AND shorts without checking market direction
**Right**: Only long in uptrends, only short in downtrends

### 2. Too Many Filters
**Wrong**: 5+ confirmation filters that never all align
**Right**: 1-2 key filters that improve signal quality

### 3. Ignoring Risk:Reward
**Wrong**: 80% win rate with 1% winners and 5% losers
**Right**: Ensure avg_win * win_rate > avg_loss * (1 - win_rate)

### 4. Overfitting Hyperopt
**Wrong**: 1000 epochs until you find profitable parameters
**Right**: 150-200 epochs max, validate on unseen data

### 5. Complex Custom Stoploss
**Wrong**: Dynamic trailing that causes unexpected exits
**Right**: Simple fixed percentage, let ROI handle profits

### 6. Testing with Default Params Only (NEW)
**Wrong**: Change config, test with default params, conclude "doesn't work"
**Right**: Change config, run hyperopt to find optimal params, THEN conclude

### 7. Incomplete Testing Matrix (NEW)
**Wrong**: Test 2-3 configs, see failures, abandon strategy
**Right**: Test 10+ configs systematically, hyperopt promising ones, THEN decide
