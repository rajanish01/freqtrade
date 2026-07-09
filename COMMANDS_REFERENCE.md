# Freqtrade Commands Reference

## Quick Reference for Common Tasks

---

## Data Management

### Download Historical Data
```bash
# Download OHLCV data
freqtrade download-data \
  --config user_data/config.json \
  --timeframes 5m 15m 1h 4h 1d \
  --timerange 20230101- \
  --trading-mode futures

# Download for specific pairs
freqtrade download-data \
  --config user_data/config.json \
  --pairs BTC/USDT:USDT ETH/USDT:USDT \
  --timeframes 5m 1h \
  --timerange 20230101-

# Include funding rate (futures)
freqtrade download-data \
  --config user_data/config.json \
  --timeframes 8h \
  --data-format-ohlcv feather \
  --include-funding-rate
```

### List Available Data
```bash
freqtrade list-data \
  --config user_data/config.json \
  --show-timerange
```

---

## Backtesting

### Basic Backtest
```bash
freqtrade backtesting \
  --config user_data/config_strategy.json \
  --strategy StrategyName \
  --timerange 20240101-20241231
```

### Detailed Backtest with Analysis
```bash
freqtrade backtesting \
  --config user_data/config_strategy.json \
  --strategy StrategyName \
  --timerange 20240101-20241231 \
  --breakdown month week \
  --export trades \
  --export-filename user_data/backtest_results/trades_export.json
```

### Multi-Strategy Comparison
```bash
freqtrade backtesting \
  --config user_data/config.json \
  --strategy-list Strategy1 Strategy2 Strategy3 \
  --timerange 20240101-20241231
```

### Backtest with Fresh Indicators
```bash
freqtrade backtesting \
  --config user_data/config.json \
  --strategy StrategyName \
  --timerange 20240101-20241231 \
  --cache none
```

---

## Hyperopt

### Basic Hyperopt
```bash
freqtrade hyperopt \
  --config user_data/config_strategy.json \
  --strategy StrategyName \
  --timerange 20240101-20240901 \
  --spaces buy sell \
  --hyperopt-loss SharpeHyperOptLoss \
  --epochs 100 \
  --random-state 42 \
  -j 4
```

### Hyperopt with Minimum Trades
```bash
freqtrade hyperopt \
  --config user_data/config_strategy.json \
  --strategy StrategyName \
  --timerange 20240101-20240901 \
  --spaces buy sell \
  --hyperopt-loss CalmarHyperOptLoss \
  --epochs 150 \
  --min-trades 100 \
  --random-state 42 \
  -j 4
```

### Hyperopt Spaces

| Space | What it Optimizes |
|-------|-------------------|
| `buy` | Entry signal parameters |
| `sell` | Exit signal parameters |
| `roi` | ROI table values |
| `stoploss` | Stoploss value |
| `trailing` | Trailing stop parameters |
| `protection` | Protection parameters |
| `all` | Everything |

### Loss Functions

| Function | Optimizes For |
|----------|---------------|
| `ShortTradeDurHyperOptLoss` | Short trade duration |
| `OnlyProfitHyperOptLoss` | Pure profit |
| `SharpeHyperOptLoss` | Risk-adjusted returns |
| `SortinoHyperOptLoss` | Downside risk-adjusted |
| `CalmarHyperOptLoss` | Profit/MaxDD ratio |
| `MaxDrawDownHyperOptLoss` | Minimize drawdown |
| `MaxDrawDownRelativeHyperOptLoss` | Relative drawdown |
| `ProfitDrawDownHyperOptLoss` | Balance profit & DD |

### Show Hyperopt Results
```bash
# Show best result
freqtrade hyperopt-show \
  --config user_data/config.json \
  --best

# Show top 10 results
freqtrade hyperopt-show \
  --config user_data/config.json \
  --profitable \
  -n 10

# Export best parameters
freqtrade hyperopt-show \
  --config user_data/config.json \
  --best \
  --print-json
```

### List Hyperopt Results
```bash
freqtrade hyperopt-list \
  --config user_data/config.json \
  --profitable \
  --min-trades 50 \
  --no-color
```

---

## Live/Dry Run Trading

### Dry Run (Paper Trading)
```bash
freqtrade trade \
  --config user_data/config_strategy.json \
  --strategy StrategyName \
  --dry-run
```

### Live Trading
```bash
freqtrade trade \
  --config user_data/config_strategy.json \
  --strategy StrategyName
```

### With Detailed Logging
```bash
freqtrade trade \
  --config user_data/config_strategy.json \
  --strategy StrategyName \
  --logfile user_data/logs/freqtrade.log \
  -vvv
```

---

## Analysis & Plotting

### Plot Profit
```bash
freqtrade plot-profit \
  --config user_data/config.json \
  --strategy StrategyName \
  --timerange 20240101-20241231 \
  --export-filename user_data/plot/profit.html
```

### Plot Dataframe (Charts)
```bash
freqtrade plot-dataframe \
  --config user_data/config.json \
  --strategy StrategyName \
  --timerange 20240101-20240115 \
  --pairs BTC/USDT:USDT \
  --indicators1 ema_fast ema_slow \
  --indicators2 rsi
```

### Analyze Trades
```bash
freqtrade backtesting-analysis \
  --config user_data/config.json \
  --analysis-groups 0 1 2 3 4 \
  --indicator-list rsi atr volume
```

---

## Strategy Management

### List Strategies
```bash
freqtrade list-strategies \
  --strategy-path user_data/strategies
```

### Create New Strategy
```bash
freqtrade new-strategy \
  --strategy NewStrategyName \
  --strategy-path user_data/strategies
```

### Show Strategy Parameters
```bash
freqtrade show-trades \
  --config user_data/config.json \
  --db-url sqlite:///tradesv3.sqlite
```

---

## FreqAI Specific

### Train Model (Backtest)
```bash
freqtrade backtesting \
  --config user_data/config_freqai.json \
  --strategy FreqAIStrategy \
  --timerange 20230101-20241231 \
  --breakdown month
```

### Purge Old Models
```bash
# Automatically handled by purge_old_models config
# Or manually delete from user_data/models/
```

---

## Utility Commands

### Test Configuration
```bash
freqtrade test-pairlist \
  --config user_data/config.json
```

### Show Trade Statistics
```bash
freqtrade show-trades \
  --config user_data/config.json \
  --db-url sqlite:///tradesv3.sqlite \
  --print-json
```

### Convert Data Format
```bash
freqtrade convert-data \
  --config user_data/config.json \
  --format-from json \
  --format-to feather
```

### Check Exchange
```bash
freqtrade list-markets \
  --config user_data/config.json \
  --exchange binanceusdm \
  --trading-mode futures
```

---

## Systematic Testing Workflow (MANDATORY)

**CRITICAL**: Before concluding ANY strategy has no edge, agents MUST follow this systematic testing workflow.
Reference: AGENT.md for full requirements.

### Step 1: Quick Test Matrix (Agent runs these)

```bash
# Test different timeframes with same params
for TF in 15m 1h 4h; do
  freqtrade backtesting \
    --config user_data/config_strategy.json \
    --strategy StrategyName \
    --timerange 20220101-20241231 \
    --cache none 2>&1 | tail -20
done
```

### Step 2: Document Results Matrix

```
| # | TF | Mode | Dir | SL | Filter | Profit% | DD% | Trades | PF |
|---|-----|------|-----|-----|--------|---------|-----|--------|-----|
| 1 | 15m | Break | Both | 5% | ON | | | | |
| 2 | 1h | Break | Both | 5% | ON | | | | |
| 3 | 4h | Break | Both | 5% | ON | | | | |
...
```

### Step 3: Identify Promising Configs

**Promising criteria (MUST run hyperopt if ANY of these):**
- Profit Factor > 1.0
- Max Drawdown < 30% with >100 trades
- Win Rate > 60%

### Step 4: Request Hyperopt for Promising Config

If a promising config is found, agent provides this to user:

```
PROMISING CONFIG FOUND - HYPEROPT REQUIRED

Configuration: [TF] / [Mode] / [Direction] / [Stoploss]
Results: PF [X.XX], DD [X%], [XXX] trades

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

After completion, please share:
1. Best epoch number and metrics
2. The optimized parameters (from hyperopt-show --best --print-json)
```

### Step 5: Test Optimized Params

After receiving hyperopt results, agent MUST test on full period:

```bash
freqtrade backtesting \
  --config user_data/config_strategy.json \
  --strategy StrategyName \
  --timerange 20220101-20241231 \
  --breakdown month \
  --cache none
```

---

## Long-Running Commands Protocol

For commands that take >10 minutes, use this workflow:

### 1. Agent Provides Command
```bash
# Example hyperopt command
cd /Users/rajanish/Workspace/freqtrade && freqtrade hyperopt \
  --config user_data/config_vwap.json \
  --strategy VWAPBandStrategy \
  --timerange 20220101-20231231 \
  --spaces buy sell \
  --hyperopt-loss SharpeHyperOptLossDaily \
  --epochs 200 \
  --min-trades 100 \
  --random-state 42 \
  -j 4
```

### 2. User Runs in Separate Shell
- Open new terminal
- Run command
- Monitor progress

### 3. User Reports Back
Share with agent:
- Best result summary
- Key metrics (trades, profit, drawdown)
- The optimized parameters

### 4. Agent Continues
- Tests optimized params on FULL backtest period
- Validates on out-of-sample
- Documents in test matrix
- Iterates as needed

---

## Environment Variables

```bash
# Set in shell or .env file
export FREQTRADE__EXCHANGE__KEY="your_api_key"
export FREQTRADE__EXCHANGE__SECRET="your_api_secret"
export FREQTRADE__TELEGRAM__TOKEN="telegram_bot_token"
export FREQTRADE__TELEGRAM__CHAT_ID="your_chat_id"
```

---

## Debugging Tips

### Verbose Output
```bash
# Add -v flags for more detail
freqtrade backtesting -vvv ...
```

### Check Strategy Syntax
```bash
python -c "from user_data.strategies.StrategyName import StrategyName"
```

### Test Indicators
```bash
freqtrade list-strategies --print-colorized
```
