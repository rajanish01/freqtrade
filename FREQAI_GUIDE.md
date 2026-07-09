# FreqAI Integration Guide

## CRITICAL: Prerequisites Before FreqAI

**DO NOT START FreqAI UNTIL YOU HAVE A PROFITABLE RULE-BASED STRATEGY.**

FreqAI should ENHANCE a working strategy, NOT RESCUE a broken one.

### Mandatory Prerequisites (from AGENT.md)

Before ANY FreqAI work, your rule-based strategy MUST:

| Requirement | Threshold | Your Strategy |
|-------------|-----------|---------------|
| Backtest Period | >= 2 years | |
| Total Trades | >= 200 | |
| Profit Factor | > 1.3 | |
| Total Profit | > 0% | |
| Max Drawdown | < 25% | |
| Out-of-Sample Profit | > 0% | |

**If ANY box above is empty or fails, STOP. Go back to rule-based development.**

---

## Overview

FreqAI is Freqtrade's machine learning module for building adaptive trading strategies. This guide covers when to use FreqAI and how to integrate it properly.

## When to Use FreqAI

### Good Use Cases (AFTER rule-based is profitable)
- Regime classification (trending/ranging/volatile)
- Probability estimation for entry signals
- Adaptive parameter selection
- Multi-factor signal combination

### NOT Recommended For
- First iteration of a new strategy (start rule-based FIRST)
- Strategies with <6 months of training data
- Broken strategies hoping ML will "fix" them
- Replacing fundamental strategy logic
- Live trading without extensive backtesting

### The FreqAI Trap

Many developers think: "My rule-based strategy doesn't work, maybe ML will find patterns I can't see."

**This is almost always wrong.**

If your rule-based strategy has negative edge, FreqAI will likely:
1. Overfit to historical noise
2. Find spurious correlations that don't persist
3. Create a more complex system that's harder to debug
4. Lose money faster with higher confidence

**ML amplifies what's already there. If there's no edge, ML amplifies noise.**

## Development Workflow

```
Phase 1: Rule-Based Strategy (REQUIRED)
    │
    ├─> Must meet ALL hard constraints from AGENT.md
    │
    └─> Only proceed if profitable over 2+ years
    
Phase 2: Feature Engineering
    │
    ├─> Identify what the rule-based strategy does well/poorly
    │
    └─> Design features that could help with weak areas
    
Phase 3: Model Training & Validation
    │
    ├─> Walk-forward validation (no look-ahead)
    │
    └─> Compare ML version vs rule-based version
    
Phase 4: Hybrid Strategy
    │
    ├─> ML enhances, doesn't replace core rules
    │
    └─> Rule-based should work without ML (fallback)
    
Phase 5: Extended Validation
    │
    ├─> Paper trade 4+ weeks
    │
    └─> Monitor for model degradation
```

### Phase Gate: Rule-Based → FreqAI

**Explicit approval required before proceeding:**

```
PHASE 1 EXIT CRITERIA CHECKLIST

Rule-based strategy name: _______________
Backtest period: ________ to ________

[ ] Profit Factor > 1.3 (Actual: _____)
[ ] Total Profit > 0% (Actual: _____%)
[ ] Max Drawdown < 25% (Actual: _____%)
[ ] Out-of-Sample positive (Actual: _____%)
[ ] Profitable in 2+ of 3 years

VERDICT: [ ] APPROVED for FreqAI  [ ] NOT APPROVED - continue rule-based work

Approved by: _____________ Date: _____________
```

---

## FreqAI Configuration

### Basic Config Structure

```json
{
    "freqai": {
        "enabled": true,
        "identifier": "unique-model-id",
        "purge_old_models": 2,
        "train_period_days": 60,
        "backtest_period_days": 7,
        "live_retrain_hours": 12,
        "expiration_hours": 24,
        "fit_live_predictions_candles": 300,
        "data_kitchen_thread_count": 4,
        
        "feature_parameters": {
            "include_timeframes": ["1h", "4h", "1d"],
            "include_corr_pairlist": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
            "label_period_candles": 12,
            "include_shifted_candles": 2,
            "indicator_periods_candles": [10, 20, 50],
            "weight_factor": 0.9,
            "principal_component_analysis": false,
            "use_SVM_to_remove_outliers": true,
            "DI_threshold": 2,
            "plot_feature_importances": 10
        },
        
        "data_split_parameters": {
            "test_size": 0.25,
            "shuffle": false
        },
        
        "model_training_parameters": {
            "n_estimators": 600,
            "learning_rate": 0.02,
            "num_leaves": 64,
            "max_depth": 8,
            "min_child_samples": 50,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": 0.1,
            "reg_lambda": 0.1,
            "n_jobs": 4,
            "verbosity": -1
        }
    }
}
```

### Key Parameters Explained

| Parameter | Purpose | Recommended Value |
|-----------|---------|-------------------|
| `train_period_days` | Training window | 30-90 days |
| `backtest_period_days` | Prediction window | 3-14 days |
| `live_retrain_hours` | Retrain frequency | 6-24 hours |
| `label_period_candles` | Forward look for labels | 6-24 candles |
| `DI_threshold` | Outlier removal | 1-3 |

---

## Model Types

### Classification (Recommended for beginners)

**Use Case**: Predict direction (up/down/neutral)

```python
# In strategy
freqai_model = "LightGBMClassifier"

# Label generation
def set_freqai_targets(self, dataframe, **kwargs):
    # 3-class classification
    dataframe["&s-up_or_down"] = np.where(
        dataframe["close"].shift(-self.freqai_info["feature_parameters"]["label_period_candles"]) 
        > dataframe["close"] * 1.01,  # 1% up
        "up",
        np.where(
            dataframe["close"].shift(-self.freqai_info["feature_parameters"]["label_period_candles"]) 
            < dataframe["close"] * 0.99,  # 1% down
            "down",
            "neutral"
        )
    )
    return dataframe
```

### Regression

**Use Case**: Predict exact return or price target

```python
freqai_model = "LightGBMRegressor"

def set_freqai_targets(self, dataframe, **kwargs):
    # Predict return
    future_close = dataframe["close"].shift(-12)
    dataframe["&-return"] = (future_close - dataframe["close"]) / dataframe["close"]
    return dataframe
```

### Available Models

| Model | Type | Speed | Accuracy | Use Case |
|-------|------|-------|----------|----------|
| LightGBMClassifier | Classification | Fast | Good | General purpose |
| LightGBMRegressor | Regression | Fast | Good | Return prediction |
| XGBoostClassifier | Classification | Medium | Good | Complex patterns |
| CatBoostClassifier | Classification | Slow | Best | Categorical features |
| PyTorch models | Both | Slow | Varies | Deep learning |

---

## Feature Engineering

### Standard Features (Auto-generated)

FreqAI automatically generates features from:
- Raw OHLCV data
- Shifted candles (lagged values)
- Multiple timeframes
- Correlated pairs

### Custom Features

```python
def feature_engineering_expand_all(self, dataframe, period, **kwargs):
    """
    Features that use the full history (expanding window)
    Called once per pair per timeframe
    """
    dataframe["%-rsi"] = ta.RSI(dataframe, timeperiod=period)
    dataframe["%-mfi"] = ta.MFI(dataframe, timeperiod=period)
    dataframe["%-adx"] = ta.ADX(dataframe, timeperiod=period)
    
    # Bollinger Bands
    bollinger = ta.BBANDS(dataframe, timeperiod=period)
    dataframe["%-bb_width"] = (bollinger["upperband"] - bollinger["lowerband"]) / bollinger["middleband"]
    dataframe["%-bb_position"] = (dataframe["close"] - bollinger["lowerband"]) / (bollinger["upperband"] - bollinger["lowerband"])
    
    return dataframe

def feature_engineering_expand_basic(self, dataframe, **kwargs):
    """
    Features that need all data but don't vary by period
    Called once per pair per timeframe
    """
    dataframe["%-pct_change"] = dataframe["close"].pct_change()
    dataframe["%-raw_volume"] = dataframe["volume"]
    dataframe["%-raw_price"] = dataframe["close"]
    
    return dataframe

def feature_engineering_standard(self, dataframe, **kwargs):
    """
    Features added after indicator periods
    Called once per pair per timeframe
    """
    dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek
    dataframe["%-hour_of_day"] = dataframe["date"].dt.hour
    
    return dataframe
```

### Feature Naming Convention

- `%-feature_name` - Standard feature
- `&-target_name` - Regression target
- `&s-target_name` - Classification target

---

## Label Generation Best Practices

### Avoid Look-Ahead Bias
```python
# WRONG - uses future data directly
dataframe["target"] = dataframe["close"].shift(-10) > dataframe["close"]

# CORRECT - use FreqAI's shift mechanism
def set_freqai_targets(self, dataframe, **kwargs):
    # FreqAI handles the shift internally
    dataframe["&-future_return"] = (
        dataframe["close"].shift(-self.freqai_info["feature_parameters"]["label_period_candles"]) 
        - dataframe["close"]
    ) / dataframe["close"]
    return dataframe
```

### ATR-Relative Labels (Recommended)
```python
def set_freqai_targets(self, dataframe, **kwargs):
    """
    Use ATR-relative thresholds for regime-independent labels
    """
    atr = ta.ATR(dataframe, timeperiod=14)
    future_close = dataframe["close"].shift(-12)
    price_change = future_close - dataframe["close"]
    
    # Classify based on ATR multiples
    dataframe["&s-direction"] = np.where(
        price_change > 1.5 * atr, "strong_up",
        np.where(
            price_change > 0.5 * atr, "up",
            np.where(
                price_change < -1.5 * atr, "strong_down",
                np.where(
                    price_change < -0.5 * atr, "down",
                    "neutral"
                )
            )
        )
    )
    return dataframe
```

---

## Strategy Integration

### Basic FreqAI Strategy Structure

```python
class FreqAIStrategy(IStrategy):
    
    # Enable FreqAI
    freqai_info = {
        "feature_parameters": {...},
        "data_split_parameters": {...},
        "model_training_parameters": {...},
    }
    
    def feature_engineering_expand_all(self, dataframe, period, **kwargs):
        # Add features
        return dataframe
    
    def set_freqai_targets(self, dataframe, **kwargs):
        # Define prediction targets
        return dataframe
    
    def populate_indicators(self, dataframe, metadata):
        # Get FreqAI predictions
        dataframe = self.freqai.start(dataframe, metadata, self)
        return dataframe
    
    def populate_entry_trend(self, dataframe, metadata):
        # Use predictions for entry
        dataframe.loc[
            (dataframe["&s-direction"] == "up") &
            (dataframe["do_predict"] == 1),  # Model confidence check
            "enter_long"
        ] = 1
        return dataframe
```

### Hybrid Strategy (Recommended)

```python
def populate_entry_trend(self, dataframe, metadata):
    """
    Combine rule-based signals with ML predictions
    """
    # Rule-based primary signal
    rule_signal = (
        (dataframe["ema_fast"] > dataframe["ema_slow"]) &
        (dataframe["rsi"] < 70)
    )
    
    # ML confirmation
    ml_confirms = (
        (dataframe["&s-direction"].isin(["up", "strong_up"])) &
        (dataframe["do_predict"] == 1)
    )
    
    # Combined entry
    dataframe.loc[
        rule_signal & ml_confirms,
        ["enter_long", "enter_tag"]
    ] = (1, "rule_plus_ml")
    
    return dataframe
```

---

## Backtesting FreqAI

### Important Considerations

1. **Walk-Forward Analysis**: FreqAI backtesting simulates retraining
2. **Longer Backtests**: Need more data due to training periods
3. **Realistic Expectations**: Backtest may differ from live

### Backtest Command
```bash
freqtrade backtesting \
  --config config_freqai.json \
  --strategy FreqAIStrategy \
  --timerange 20230101-20241231 \
  --breakdown month
```

### Validation Checklist
- [ ] Model retrains as expected during backtest
- [ ] `do_predict` column filters low-confidence predictions
- [ ] Performance consistent across retraining periods
- [ ] No dramatic performance difference train vs predict periods

---

## Common Pitfalls

### 1. Overfitting
**Problem**: Model memorizes training data
**Solution**: 
- Reduce model complexity
- Increase regularization (reg_alpha, reg_lambda)
- Use fewer features
- Increase DI_threshold

### 2. Data Leakage
**Problem**: Future information in features
**Solution**:
- Review all feature calculations
- Use proper shift for labels
- Don't include target-correlated features

### 3. Regime Change
**Problem**: Model trained on old regime
**Solution**:
- Shorter training periods
- More frequent retraining
- Regime-aware features

### 4. Overconfidence
**Problem**: Taking all model predictions
**Solution**:
- Use `do_predict` filtering
- Require minimum probability threshold
- Combine with rule-based confirmation

---

## Production Checklist

### Before Going Live
- [ ] Backtested on 2+ years of data
- [ ] Walk-forward validation passed
- [ ] Paper traded for 4+ weeks
- [ ] Retraining works smoothly
- [ ] Model persistence configured
- [ ] Fallback strategy defined (if model fails)

### Monitoring
- [ ] Track prediction accuracy over time
- [ ] Monitor feature importance drift
- [ ] Alert on model staleness
- [ ] Log all retraining events
