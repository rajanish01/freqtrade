# VWAPBandStrategy.py
# Iteration 1 — rule-based VWAP band strategy for USDT perpetual futures.
#
# Base logic (from AlgoTest VWAP template): VWAP crossover for direction.
# Refinements layered on top:
#   - Rolling VWAP + stddev bands (mean-reversion OR breakout modes)
#   - Regime filter (ADX + higher-timeframe EMA slope)
#   - Confirmation stack (RSI, volume surge, EMA relationship) — each hyperopt-toggleable
#   - ATR-anchored dynamic stoploss (custom_stoploss)
#   - Risk-based dynamic stake sizing (custom_stake_amount)
#   - Regime-aware dynamic leverage (leverage callback)
#   - Native protections (MaxDrawdown, StoplossGuard, CooldownPeriod, LowProfitPairs)
#
# Designed for hyperopt in categories: structural -> policy -> signal.

import logging
from datetime import datetime
from functools import reduce
from typing import Optional

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame, Series

from freqtrade.strategy import (
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    IStrategy,
    informative,
)

logger = logging.getLogger(__name__)


class VWAPBandStrategy(IStrategy):
    """
    Iteration 1: rule-based VWAP band strategy. No ML.
    Symmetric long/short on USDT perps.
    """

    INTERFACE_VERSION = 3

    timeframe = "5m"
    # Higher timeframe for regime context.
    informative_timeframe = "1h"

    can_short = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    # We rely on custom_stoploss, so set a wide static backstop.
    stoploss = -0.25
    use_custom_stoploss = True

    # ROI table is intentionally loose — dynamic exits do the real work.
    # Hyperopt can override. Kept as a safety ceiling on winners.
    minimal_roi = {
        "0": 0.10,
        "60": 0.05,
        "180": 0.02,
        "360": 0.005,
    }

    # Trailing is disabled by default; custom_stoploss handles the trail logic.
    trailing_stop = False

    process_only_new_candles = True
    # Needs enough history for the 50-period 1h EMA regime filter (50h) plus the
    # VWAP window; 400 5m candles (~33h of 1h context via the informative) is safe.
    startup_candle_count: int = 400

    # ----- Position adjustment / leverage config -----
    position_adjustment_enable = False
    # Conservative until validated. Reward:risk is leverage-invariant, so leverage
    # doesn't fix edge — it only sets blowup risk and noise-stopout frequency.
    # Keep at 2x until a window shows positive expectancy.
    max_leverage_cap = 2.0  # hard ceiling regardless of what dynamic logic computes

    # =========================================================================
    # HYPEROPT PARAMETERS — organized by category
    # =========================================================================

    # ---- STRUCTURAL (VWAP window, band width) ----
    # Band width sets reward geometry: entries at the band, target at VWAP, so a
    # wider band => more price distance to target. Range extended to 5.0 so
    # hyperopt can push entries far enough out to beat a noise-proof stop.
    vwap_window = IntParameter(20, 100, default=40, space="buy", optimize=True)
    band_mult = DecimalParameter(1.5, 5.0, default=2.5, decimals=1, space="buy", optimize=True)

    # ---- POLICY (which mode: mean-reversion vs breakout) ----
    entry_mode = CategoricalParameter(
        ["reversion", "breakout"], default="reversion", space="buy", optimize=True
    )

    # ---- REGIME FILTER ----
    adx_threshold = IntParameter(15, 40, default=25, space="buy", optimize=True)
    use_regime_filter = BooleanParameter(default=True, space="buy", optimize=True)

    # ---- SIGNAL CONFIRMATIONS (each toggleable) ----
    use_rsi_filter = BooleanParameter(default=True, space="buy", optimize=True)
    rsi_long_max = IntParameter(30, 60, default=45, space="buy", optimize=True)
    rsi_short_min = IntParameter(40, 70, default=55, space="buy", optimize=True)

    use_volume_filter = BooleanParameter(default=True, space="buy", optimize=True)
    volume_mult = DecimalParameter(1.0, 3.0, default=1.5, decimals=1, space="buy", optimize=True)

    use_ema_filter = BooleanParameter(default=False, space="buy", optimize=True)
    ema_fast = IntParameter(8, 21, default=9, space="buy", optimize=True)
    ema_slow = IntParameter(21, 50, default=21, space="buy", optimize=True)

    # ---- EXIT / RISK (ATR stop + risk sizing) ----
    atr_period = IntParameter(10, 30, default=14, space="sell", optimize=True)
    # Range opened down to 1.0 so hyperopt can try tighter stops to cut the
    # negative-skew tail (median trade is positive; the mean is dragged down by
    # a few wide stop-outs).
    atr_stop_mult = DecimalParameter(1.0, 6.0, default=3.5, decimals=1, space="sell", optimize=True)
    # Only trail after real profit cushion (in ATR units), not from tick 1.
    atr_trail_trigger = DecimalParameter(
        1.0, 4.0, default=2.0, decimals=1, space="sell", optimize=True
    )
    # Absolute floor on stop distance. Lowered to 0.008 so a tighter stop is
    # reachable if it improves the tail without over-triggering on noise.
    min_stop_pct = DecimalParameter(
        0.008, 0.05, default=0.025, decimals=3, space="sell", optimize=True
    )

    # Fraction of equity risked per trade (used by custom_stake_amount).
    risk_per_trade = DecimalParameter(
        0.005, 0.03, default=0.01, decimals=3, space="sell", optimize=False
    )

    # Exit when price crosses back through VWAP (mean-reversion take-profit).
    use_vwap_exit = BooleanParameter(default=True, space="sell", optimize=True)

    # Trailing stop. OFF by default: for mean-reversion the target IS vwap, so a
    # trailing stop only intercepts winners mid-reversion and books them as
    # losses (this was the -170% killer in the prior run). Hyperopt may re-enable
    # it for breakout mode, where trend-riding makes trailing appropriate.
    use_trailing = BooleanParameter(default=False, space="sell", optimize=True)

    # ---- TIME-CUT (tail control) ----
    # A reversion that hasn't reverted quickly is trending against us and heading
    # for the full stop. Cut stale-underwater trades early to convert a wide
    # stop loss into a small scratch, shrinking the negative tail. Defaults are
    # hardcoded for a clean first test; can be hyperopted later if it helps.
    use_time_cut = BooleanParameter(default=True, space="sell", optimize=True)
    stale_minutes = IntParameter(45, 180, default=90, space="sell", optimize=True)
    stale_loss = DecimalParameter(
        -0.03, -0.002, default=-0.005, decimals=3, space="sell", optimize=True
    )

    # =========================================================================
    # INDICATORS
    # =========================================================================

    @informative("1h")
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Higher-timeframe regime context: EMA slope + ADX.
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema50_slope"] = dataframe["ema50"].diff()
        dataframe["adx"] = ta.ADX(dataframe)
        return dataframe

    def _rolling_vwap(self, dataframe: DataFrame, window: int) -> Series:
        """
        Rolling VWAP over `window` candles.
        Freqtrade backtests aren't session-anchored, so we use a rolling
        window as a robust, pair-agnostic proxy.
        """
        typical = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3.0
        pv = typical * dataframe["volume"]
        cum_pv = pv.rolling(window=window, min_periods=1).sum()
        cum_vol = dataframe["volume"].rolling(window=window, min_periods=1).sum()
        vwap = cum_pv / cum_vol.replace(0, np.nan)
        return vwap

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        window = int(self.vwap_window.value)

        # ---- VWAP + stddev bands ----
        vwap = self._rolling_vwap(dataframe, window)
        # Explicit Series wrap guards against any array-return quirks.
        dataframe["vwap"] = Series(vwap, index=dataframe.index)

        typical = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3.0
        # Rolling stddev of typical price around the window.
        rolling_std = typical.rolling(window=window, min_periods=1).std()
        dataframe["vwap_std"] = Series(rolling_std, index=dataframe.index)

        mult = float(self.band_mult.value)
        dataframe["vwap_upper"] = dataframe["vwap"] + mult * dataframe["vwap_std"]
        dataframe["vwap_lower"] = dataframe["vwap"] - mult * dataframe["vwap_std"]

        # ---- ATR (for dynamic stop + sizing) ----
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=int(self.atr_period.value))
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        # ---- RSI ----
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # ---- Volume surge ----
        dataframe["volume_mean"] = dataframe["volume"].rolling(window=window, min_periods=1).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_mean"].replace(0, np.nan)

        # ---- EMAs ----
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=int(self.ema_fast.value))
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=int(self.ema_slow.value))

        # ---- Local ADX (in addition to HTF) ----
        dataframe["adx"] = ta.ADX(dataframe)

        return dataframe

    # =========================================================================
    # ENTRY LOGIC
    # =========================================================================

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe
        mode = self.entry_mode.value

        long_conditions = []
        short_conditions = []

        # ---- Base VWAP-band signal ----
        if mode == "reversion":
            # Fade the FIRST POKE past the band: current candle closes beyond the
            # band and the prior candle did not. This enters at maximum distance
            # from VWAP (restoring reward-to-target), while firing only once per
            # extension instead of every candle price sits outside the band.
            long_conditions.append(
                (df["close"] < df["vwap_lower"])
                & (df["close"].shift(1) >= df["vwap_lower"].shift(1))
            )
            short_conditions.append(
                (df["close"] > df["vwap_upper"])
                & (df["close"].shift(1) <= df["vwap_upper"].shift(1))
            )
        else:  # breakout
            # Ride reclaims: long on cross above VWAP, short on cross below.
            long_conditions.append(
                (df["close"] > df["vwap"]) & (df["close"].shift(1) <= df["vwap"].shift(1))
            )
            short_conditions.append(
                (df["close"] < df["vwap"]) & (df["close"].shift(1) >= df["vwap"].shift(1))
            )

        # ---- Regime filter ----
        if self.use_regime_filter.value:
            adx_ok = df["adx"] > int(self.adx_threshold.value)
            if mode == "breakout":
                # Only trade breakouts in trending regime aligned with HTF slope.
                long_conditions.append(adx_ok & (df["ema50_slope_1h"] > 0))
                short_conditions.append(adx_ok & (df["ema50_slope_1h"] < 0))
            else:
                # Reversion: only fade in the direction that isn't fighting the
                # higher-timeframe trend. Gate on price vs the 1h EMA50 — this
                # bites even in a slow grind (unlike an ADX gate, which stays
                # inert when the trend is gradual). Long-fades only when price is
                # at/above the 1h trend (buying dips in an uptrend); short-fades
                # only when at/below it (fading pops in a downtrend). In a true
                # range price oscillates across the 1h EMA, so both sides trade.
                htf_bear = df["close"] < df["ema50_1h"]
                htf_bull = df["close"] > df["ema50_1h"]
                long_conditions.append(~htf_bear)
                short_conditions.append(~htf_bull)

        # ---- RSI confirmation ----
        if self.use_rsi_filter.value:
            long_conditions.append(df["rsi"] < int(self.rsi_long_max.value))
            short_conditions.append(df["rsi"] > int(self.rsi_short_min.value))

        # ---- Volume surge confirmation ----
        if self.use_volume_filter.value:
            long_conditions.append(df["volume_ratio"] > float(self.volume_mult.value))
            short_conditions.append(df["volume_ratio"] > float(self.volume_mult.value))

        # ---- EMA relationship confirmation ----
        if self.use_ema_filter.value:
            long_conditions.append(df["ema_fast"] > df["ema_slow"])
            short_conditions.append(df["ema_fast"] < df["ema_slow"])

        # ---- Guards: valid volume and indicators present ----
        long_conditions.append(df["volume"] > 0)
        short_conditions.append(df["volume"] > 0)

        if long_conditions:
            df.loc[reduce(lambda a, b: a & b, long_conditions), ["enter_long", "enter_tag"]] = (
                1,
                f"vwap_{mode}_long",
            )
        if short_conditions:
            df.loc[reduce(lambda a, b: a & b, short_conditions), ["enter_short", "enter_tag"]] = (
                1,
                f"vwap_{mode}_short",
            )

        return df

    # =========================================================================
    # EXIT LOGIC
    # =========================================================================

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        df = dataframe

        if self.use_vwap_exit.value:
            # Mean-reversion take-profit: exit when price returns to VWAP.
            df.loc[
                (df["close"] >= df["vwap"]) & (df["volume"] > 0),
                ["exit_long", "exit_tag"],
            ] = (1, "vwap_reclaim")
            df.loc[
                (df["close"] <= df["vwap"]) & (df["volume"] > 0),
                ["exit_short", "exit_tag"],
            ] = (1, "vwap_reclaim")

        return df

    # =========================================================================
    # TIME-CUT EXIT (tail control)
    # =========================================================================

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> Optional[str]:
        """
        Cut stale, underwater trades before they ride to the full stop.
        A mean reversion should resolve quickly; a trade still underwater after
        `stale_minutes` is trending against us. Exiting it small converts a
        wide -2.4% stop into a minor scratch, shrinking the negative tail.
        """
        if not self.use_time_cut.value:
            return None
        age_min = (current_time - trade.open_date_utc).total_seconds() / 60.0
        if age_min >= int(self.stale_minutes.value) and current_profit <= float(
            self.stale_loss.value
        ):
            return "stale_cut"
        return None

    # =========================================================================
    # DYNAMIC STOPLOSS (ATR-anchored trailing)
    # =========================================================================

    def custom_stoploss(
        self,
        pair: str,
        trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs,
    ) -> Optional[float]:
        """
        ATR-anchored stop. Initial stop = atr_stop_mult * ATR from entry.
        Once profit exceeds atr_trail_trigger * ATR (in price terms), trail.
        Returns a relative stoploss (negative fraction) from current_rate.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return None

        last_candle = dataframe.iloc[-1].squeeze()
        atr = last_candle["atr"]
        if atr is None or np.isnan(atr) or current_rate == 0 or trade.open_rate == 0:
            return None

        atr_pct = atr / current_rate
        stop_mult = float(self.atr_stop_mult.value)

        # Initial stop distance: ATR-scaled but floored so it can never be
        # sub-noise. This is the distance from the ENTRY price.
        init_dist = max(stop_mult * atr_pct, float(self.min_stop_pct.value))

        # Trailing only activates after profit exceeds the trigger cushion,
        # AND only if trailing is enabled. For reversion (default) trailing is
        # off: the vwap_reclaim take-profit is the exit, and the entry-anchored
        # stop below is the only downside protection.
        trail_trigger_pct = float(self.atr_trail_trigger.value) * atr_pct

        if self.use_trailing.value and current_profit > trail_trigger_pct:
            # Lock in gains: trail at stop_mult*ATR behind CURRENT price.
            # Returned relative to current_rate; Freqtrade ratchets (never loosens).
            return -max(atr_pct * stop_mult, float(self.min_stop_pct.value))

        # Not yet in profit cushion: hold an ENTRY-ANCHORED stop.
        # Express the fixed entry-anchored stop price relative to current_rate.
        # As price moves favorably this ratio widens, Freqtrade ignores the
        # loosening, so the absolute stop stays pinned at entry -/+ init_dist.
        if trade.is_short:
            desired_stop_price = trade.open_rate * (1.0 + init_dist)
            rel = -(desired_stop_price / current_rate - 1.0)
        else:
            desired_stop_price = trade.open_rate * (1.0 - init_dist)
            rel = desired_stop_price / current_rate - 1.0

        # Guard: must be a protective (negative) value.
        if rel >= 0:
            return None
        return rel

    # =========================================================================
    # DYNAMIC STAKE (risk-based sizing off ATR stop distance)
    # =========================================================================

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: Optional[float],
        max_stake: float,
        leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        """
        Size so that hitting the ATR stop loses ~risk_per_trade of equity.
        stake = (equity * risk_per_trade) / stop_distance_fraction
        Capped by max_stake and floored by min_stake.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or len(dataframe) == 0:
            return proposed_stake

        last_candle = dataframe.iloc[-1].squeeze()
        atr = last_candle["atr"]
        if atr is None or np.isnan(atr) or current_rate == 0:
            return proposed_stake

        atr_pct = atr / current_rate
        stop_distance = float(self.atr_stop_mult.value) * atr_pct
        if stop_distance <= 0:
            return proposed_stake

        try:
            total_equity = self.wallets.get_total_stake_amount()
        except Exception:
            return proposed_stake

        risk_amount = total_equity * float(self.risk_per_trade.value)
        # Stake before leverage; the risk is on the notional, stop is on price.
        desired_stake = risk_amount / stop_distance

        # Respect exchange/backtest bounds.
        if min_stake:
            desired_stake = max(desired_stake, min_stake)
        desired_stake = min(desired_stake, max_stake)
        return desired_stake

    # =========================================================================
    # DYNAMIC LEVERAGE (regime-aware, conservative)
    # =========================================================================

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: Optional[str],
        side: str,
        **kwargs,
    ) -> float:
        """
        Lower leverage when volatility (ATR%) is high; raise (capped) when calm.
        Never exceeds max_leverage_cap.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        cap = min(self.max_leverage_cap, max_leverage)
        if dataframe is None or len(dataframe) == 0:
            return min(2.0, cap)

        last_candle = dataframe.iloc[-1].squeeze()
        atr_pct = last_candle.get("atr_pct", np.nan)
        if atr_pct is None or np.isnan(atr_pct):
            return min(2.0, cap)

        # Inverse-vol scaling, conservative: target ~1% ATR as "normal" -> 1.5x.
        # Higher vol -> less leverage. Capped at max_leverage_cap (2x).
        if atr_pct <= 0:
            return min(1.5, cap)
        target = 0.01 / atr_pct * 1.5
        lev = float(np.clip(target, 1.0, cap))
        return lev

    # =========================================================================
    # PROTECTIONS
    # =========================================================================

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 3},
            {
                # Bound bad-regime bleed: a 10% drawdown over a day halts trading
                # for ~2 days, so a sustained adverse regime pauses the strategy
                # instead of resetting the circuit breaker and bleeding on.
                "method": "MaxDrawdown",
                "lookback_period_candles": 288,  # ~1 day on 5m
                "trade_limit": 8,
                "stop_duration_candles": 576,  # ~2 days
                "max_allowed_drawdown": 0.10,
            },
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 144,
                "trade_limit": 4,
                "stop_duration_candles": 72,
                "only_per_pair": False,
            },
            {
                "method": "LowProfitPairs",
                "lookback_period_candles": 288,
                "trade_limit": 4,
                "stop_duration_candles": 60,
                "required_profit": -0.02,
            },
        ]