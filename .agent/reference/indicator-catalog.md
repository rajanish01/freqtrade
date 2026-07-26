# Approved Indicator Catalog

Use these. Adding an indicator that is not listed here is a YELLOW action —
propose it and wait for approval.

Import as:
```python
import talib.abstract as ta
import pandas_ta as pta          # ft-pandas-ta, only where ta-lib has no equivalent
from technical import qtpylib
```

## Trend
| Indicator | Library | Params | Column |
|-----------|---------|--------|--------|
| SMA | ta-lib | period | `ind_sma_{p}` |
| EMA | ta-lib | period | `ind_ema_{p}` |
| ADX | ta-lib | period | `ind_adx_{p}` |
| PLUS_DI / MINUS_DI | ta-lib | period | `ind_plus_di_{p}` / `ind_minus_di_{p}` |
| SAR | ta-lib | accel, max | `ind_sar` |
| Supertrend | pandas-ta | period, mult | `ind_supertrend` |

## Momentum
| Indicator | Library | Params | Column |
|-----------|---------|--------|--------|
| RSI | ta-lib | period | `ind_rsi_{p}` |
| MACD | ta-lib | fast, slow, signal | `ind_macd`, `ind_macd_signal`, `ind_macd_hist` |
| Stochastic | ta-lib | k, d, smooth | `ind_stoch_k`, `ind_stoch_d` |
| CCI | ta-lib | period | `ind_cci_{p}` |
| ROC | ta-lib | period | `ind_roc_{p}` |

## Volatility
| Indicator | Library | Params | Column |
|-----------|---------|--------|--------|
| Bollinger | qtpylib | period, std | `ind_bb_upper`, `ind_bb_mid`, `ind_bb_lower` |
| ATR | ta-lib | period | `ind_atr_{p}` |
| NATR (normalised ATR) | ta-lib | period | `ind_natr_{p}` |
| Keltner | pandas-ta | period, mult | `ind_kc_upper`, `ind_kc_lower` |

Prefer **NATR** over ATR when comparing volatility across pairs — raw ATR is in
price units, so BTC and ADA are not comparable.

## Volume
| Indicator | Library | Params | Column |
|-----------|---------|--------|--------|
| Volume SMA | pandas rolling | period | `ind_vol_sma_{p}` |
| OBV | ta-lib | — | `ind_obv` |
| MFI | ta-lib | period | `ind_mfi_{p}` |
| VWAP (rolling) | qtpylib | period | `ind_vwap` |

**VWAP warning:** true VWAP resets each session. `qtpylib.rolling_vwap` is a
rolling approximation. On 24/7 crypto futures there is no session boundary, so
a rolling window is the correct choice — but say which you used, and make the
window an `opt_*` parameter.

## Selection rules
1. One indicator per concept. Two momentum oscillators is redundancy
   (anti-pattern #7), not confirmation.
2. Aim to cover distinct dimensions: trend, momentum, volatility, volume.
3. Every indicator must earn its place — if removing it does not change the
   backtest, remove it.
4. Prefer bounded/normalised indicators (RSI, ADX, NATR, percentiles) over
   unbounded price-unit ones, especially as FreqAI features.
