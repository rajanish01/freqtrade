# ============================================================================
# RegimeAdaptiveTrend v2.1 — FreqAI Regime-Adaptive Trend Following
# ============================================================================
# Changes vs v2 (driven by the 2026-01/04 1h backtest):
#
#  1. CONFIDENCE BAND ENTRY. Two independent backtests confirmed the model
#     is inversely calibrated at the high end (prob >= 0.80 entries lose;
#     0.65-0.80 entries are profitable). Entries now require
#     floor <= prob < ceiling. Sub-band tags (_lower/_upper) keep measuring
#     calibration inside the tradable band.
#
#  2. R-MULTIPLE FIX. Realized winners averaged ~0.24R vs 1R losers —
#     unwinnable at any achievable win rate. Main cause: confidence_decay
#     exits scratching would-be runners at ~+0.04%. Decay exit now only
#     fires BEFORE the trade has proven itself (before trail trigger);
#     once trailing is active, the trail manages the exit.
#
#  3. STOP AUDIT INSTRUMENTATION. Entry snapshot (ATR, stop price, stake,
#     leverage, intended risk) stored as trade custom data and logged, and
#     realized-vs-intended risk logged at exit fill. NOTE: trade-level
#     arithmetic on the last run shows per-stop EQUITY loss was ~0.73%
#     (on target); the earlier "sizing chain broken" hypothesis was wrong —
#     the -4.63% figure is position ratio, not equity. Instrumentation
#     stays to verify this continuously.
#
#  4. DAILY BREAKER, BACKTEST-COMPATIBLE. The python daily-loss check can
#     silently no-op in backtesting. A MaxDrawdown protection with 1-day
#     lookback now implements the daily halt in a way backtesting honors
#     (with --enable-protections). The runtime python check remains as a
#     live-mode belt-and-braces layer.
#
#  5. HTF MACRO FILTER. Longs require close > EMA200(1h) (~8-day
#     structure), shorts require close < EMA200. All 16 longs lost in the
#     bear quarter; the classifier should not fight macro tide alone.
#
#  Also folds in the environment fixes discovered during bring-up:
#  BBANDS numpy->Series wrapping, and explicit object dtype on the label
#  column (pandas 3 string-inference compatibility).
#
#  FEATURES AND LABELS ARE UNCHANGED vs v2 — keep the SAME identifier so
#  cached models are reused (entry/exit logic changes never require
#  retraining).
#
# Usage:
#   freqtrade backtesting --strategy RegimeAdaptiveTrend \
#       --config config_freqai_regime.json \
#       --freqaimodel LightGBMClassifier \
#       --timerange 20260101-20260401 \
#       --enable-protections
# ============================================================================

import logging
from datetime import datetime, timezone
from functools import reduce
from typing import Optional

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import DecimalParameter, IStrategy

logger = logging.getLogger(__name__)


class RegimeAdaptiveTrendV2(IStrategy):

    INTERFACE_VERSION = 3

    # ------------------------------------------------------------------
    # Core settings
    # ------------------------------------------------------------------
    timeframe = "1h"
    can_short = True
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    stoploss = -0.12
    use_custom_stoploss = True
    minimal_roi = {"0": 1.0}

    startup_candle_count: int = 220

    # ------------------------------------------------------------------
    # [SIGNAL] Hyperoptable parameters
    # ------------------------------------------------------------------
    entry_confidence_floor = DecimalParameter(
        0.55, 0.75, default=0.65, decimals=2, space="buy", optimize=True)
    # Ceiling implements the calibration finding: prob >= ceiling is SKIPPED.
    entry_confidence_ceiling = DecimalParameter(
        0.76, 0.95, default=0.80, decimals=2, space="buy", optimize=True)
    regime_flip_prob = DecimalParameter(
        0.40, 0.65, default=0.50, decimals=2, space="sell", optimize=True)
    confidence_decay_exit = DecimalParameter(
        0.30, 0.50, default=0.40, decimals=2, space="sell", optimize=True)
    atr_stop_multiplier = DecimalParameter(
        1.5, 3.5, default=2.5, decimals=1, space="sell", optimize=True)
    atr_trail_trigger = DecimalParameter(
        0.5, 2.0, default=1.0, decimals=1, space="sell", optimize=True)
    atr_trail_distance = DecimalParameter(
        1.0, 3.0, default=1.5, decimals=1, space="sell", optimize=True)

    # ------------------------------------------------------------------
    # [STRUCTURAL] Label construction — bump identifier if changed
    # ------------------------------------------------------------------
    label_atr_multiplier = 1.5
    label_atr_period = 14

    # ------------------------------------------------------------------
    # [POLICY] Fixed risk parameters — never hyperopt targets
    # ------------------------------------------------------------------
    di_full_size_threshold = 1.0
    di_zero_size_threshold = 2.0        # must equal DI_threshold in config

    base_risk_per_trade = 0.0075
    max_risk_per_trade = 0.015
    conf_scale_min = 1.0                # flat until calibration proves otherwise
    conf_scale_max = 1.0

    lev_low_vol = 3.0
    lev_mid_vol = 2.0
    lev_high_vol = 1.0
    max_leverage_cap = 5.0

    max_same_direction_trades = 3
    max_daily_loss_pct = 0.035

    # Fixed sub-band boundary for calibration tagging (measurement only)
    tag_band_split = 0.72

    # ------------------------------------------------------------------
    # Protections (require --enable-protections in backtests)
    # ------------------------------------------------------------------
    @property
    def protections(self):
        return [
            {   # per-pair cooldown after every close
                "method": "CooldownPeriod",
                "stop_duration_candles": 3,
            },
            {   # 3 stoplosses in 24h on a pair -> pair paused 12h
                "method": "StoplossGuard",
                "lookback_period_candles": 24,
                "trade_limit": 3,
                "stop_duration_candles": 12,
                "only_per_pair": True,
            },
            {   # DAILY BREAKER (backtest-compatible): ~3.5% drawdown within
                # a rolling day halts the whole bot for the rest of that day.
                "method": "MaxDrawdown",
                "lookback_period_candles": 24,
                "trade_limit": 4,
                "max_allowed_drawdown": 0.035,
                "stop_duration_candles": 24,
            },
            {   # WEEKLY BREAKER: 8% over rolling week -> stop 2 days
                "method": "MaxDrawdown",
                "lookback_period_candles": 168,
                "trade_limit": 10,
                "max_allowed_drawdown": 0.08,
                "stop_duration_candles": 48,
            },
        ]

    # ==================================================================
    # FreqAI feature engineering (UNCHANGED vs v2 — models stay valid)
    # ==================================================================
    def feature_engineering_expand_all(
        self, dataframe: DataFrame, period: int, metadata: dict, **kwargs
    ) -> DataFrame:
        dataframe["%-adx-period"] = ta.ADX(dataframe, timeperiod=period)
        dataframe["%-plus_di-period"] = ta.PLUS_DI(dataframe, timeperiod=period)
        dataframe["%-minus_di-period"] = ta.MINUS_DI(dataframe, timeperiod=period)

        ema = ta.EMA(dataframe, timeperiod=period)
        dataframe["%-ema_dist-period"] = (dataframe["close"] - ema) / dataframe["close"]
        dataframe["%-ema_slope-period"] = ema.pct_change(3, fill_method=None)

        dataframe["%-rsi-period"] = ta.RSI(dataframe, timeperiod=period)
        dataframe["%-roc-period"] = ta.ROC(dataframe, timeperiod=period)
        dataframe["%-mfi-period"] = ta.MFI(dataframe, timeperiod=period)

        atr = ta.ATR(dataframe, timeperiod=period)
        dataframe["%-atr_pct-period"] = atr / dataframe["close"]
        atr_fast = ta.ATR(dataframe, timeperiod=max(2, period // 3))
        dataframe["%-atr_ratio-period"] = atr_fast / atr

        upper, mid, lower = ta.BBANDS(
            dataframe["close"], timeperiod=period, nbdevup=2.0, nbdevdn=2.0
        )
        # raw-Series talib path returns numpy arrays — wrap back into Series
        upper = pd.Series(upper, index=dataframe.index)
        mid = pd.Series(mid, index=dataframe.index)
        lower = pd.Series(lower, index=dataframe.index)

        bb_width = (upper - lower) / mid
        dataframe["%-bb_width-period"] = bb_width
        dataframe["%-bb_width_roc-period"] = bb_width.pct_change(3, fill_method=None)
        dataframe["%-bb_position-period"] = (dataframe["close"] - lower) / (
            (upper - lower).replace(0, np.nan)
        )

        vol_sma = dataframe["volume"].rolling(period).mean()
        dataframe["%-rel_volume-period"] = dataframe["volume"] / vol_sma.replace(0, np.nan)
        dataframe["%-green_ratio-period"] = (
            (dataframe["close"] > dataframe["open"]).rolling(period).mean()
        )

        roll_high = dataframe["high"].rolling(period).max()
        roll_low = dataframe["low"].rolling(period).min()
        rng = (roll_high - roll_low).replace(0, np.nan)

        dataframe["%-range_position-period"] = (dataframe["close"] - roll_low) / rng
        dataframe["%-drawup-period"] = (dataframe["close"] - roll_low) / dataframe["close"]
        dataframe["%-drawdown-period"] = (roll_high - dataframe["close"]) / dataframe["close"]
        dataframe["%-bars_since_high-period"] = (
            dataframe["high"].rolling(period)
            .apply(lambda x: period - 1 - int(np.argmax(x)), raw=True) / period
        )
        dataframe["%-bars_since_low-period"] = (
            dataframe["low"].rolling(period)
            .apply(lambda x: period - 1 - int(np.argmin(x)), raw=True) / period
        )
        direction = np.sign(dataframe["close"].diff())
        streak = direction.groupby((direction != direction.shift()).cumsum()).cumcount() + 1
        dataframe["%-streak_norm-period"] = (streak * direction) / period

        return dataframe

    def feature_engineering_expand_basic(
        self, dataframe: DataFrame, metadata: dict, **kwargs
    ) -> DataFrame:
        dataframe["%-pct_change"] = dataframe["close"].pct_change()
        dataframe["%-raw_volume"] = dataframe["volume"]
        dataframe["%-hl_range"] = (dataframe["high"] - dataframe["low"]) / dataframe["close"]
        dataframe["%-close_to_high"] = (dataframe["high"] - dataframe["close"]) / (
            (dataframe["high"] - dataframe["low"]).replace(0, np.nan)
        )
        return dataframe

    def feature_engineering_standard(
        self, dataframe: DataFrame, metadata: dict, **kwargs
    ) -> DataFrame:
        dataframe["%-day_of_week"] = dataframe["date"].dt.dayofweek / 6.0
        dataframe["%-hour_of_day"] = dataframe["date"].dt.hour / 23.0

        ema20 = ta.EMA(dataframe, timeperiod=20)
        ema50 = ta.EMA(dataframe, timeperiod=50)
        ema100 = ta.EMA(dataframe, timeperiod=100)
        dataframe["%-ema_alignment"] = (
            np.sign(ema20 - ema50) + np.sign(ema50 - ema100)
        ) / 2.0

        aligned = np.sign(ema20 - ema50)
        age = aligned.groupby((aligned != aligned.shift()).cumsum()).cumcount() + 1
        dataframe["%-alignment_age"] = np.clip(age / 100.0, 0, 1)
        return dataframe

    # ==================================================================
    # FreqAI targets (UNCHANGED vs v2)
    # ==================================================================
    def set_freqai_targets(self, dataframe: DataFrame, metadata: dict, **kwargs) -> DataFrame:
        label_period = self.freqai_info["feature_parameters"]["label_period_candles"]

        future_close = dataframe["close"].shift(-label_period)
        fwd_return = (future_close - dataframe["close"]) / dataframe["close"]

        atr_pct = ta.ATR(dataframe, timeperiod=self.label_atr_period) / dataframe["close"]
        horizon_scale = np.sqrt(label_period / self.label_atr_period)
        threshold = self.label_atr_multiplier * atr_pct * horizon_scale

        # explicit object dtype: pandas-3 string inference otherwise breaks
        # freqtrade's classifier label handling (fit_labels / append checks)
        dataframe["&-regime"] = pd.Series(
            np.select(
                [fwd_return > threshold, fwd_return < -threshold],
                ["up", "down"],
                default="range",
            ),
            index=dataframe.index,
            dtype=object,
        )

        try:
            dist = dataframe["&-regime"].value_counts(normalize=True).to_dict()
            logger.info(
                f"{metadata.get('pair', '?')} label distribution: "
                + ", ".join(f"{k}={v:.1%}" for k, v in sorted(dist.items()))
            )
        except Exception:
            pass

        return dataframe

    # ==================================================================
    # Strategy pipeline
    # ==================================================================
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.freqai.start(dataframe, metadata, self)

        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
        dataframe["vol_percentile"] = (
            dataframe["atr_pct"].rolling(720, min_periods=240).rank(pct=True)
        )
        # HTF macro structure filter (~8 days on 1h)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_entry_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        floor = self.entry_confidence_floor.value
        ceiling = self.entry_confidence_ceiling.value
        split = self.tag_band_split

        # ----------------------------- LONG ------------------------------
        long_conditions = [
            df["do_predict"] == 1,
            df["&-regime"] == "up",
            df["up"] >= floor,
            df["up"] < ceiling,                 # calibration ceiling
            df["close"] > df["ema200"],         # macro filter
            df["DI_values"] < self.di_zero_size_threshold,
            df["volume"] > 0,
        ]
        df.loc[
            reduce(lambda x, y: x & y, long_conditions),
            ["enter_long", "enter_tag"],
        ] = (1, "regime_up_lower")
        df.loc[
            (df["enter_long"] == 1) & (df["up"] >= split), "enter_tag"
        ] = "regime_up_upper"

        # ----------------------------- SHORT -----------------------------
        short_conditions = [
            df["do_predict"] == 1,
            df["&-regime"] == "down",
            df["down"] >= floor,
            df["down"] < ceiling,               # calibration ceiling
            df["close"] < df["ema200"],         # macro filter
            df["DI_values"] < self.di_zero_size_threshold,
            df["volume"] > 0,
        ]
        df.loc[
            reduce(lambda x, y: x & y, short_conditions),
            ["enter_short", "enter_tag"],
        ] = (1, "regime_down_lower")
        df.loc[
            (df["enter_short"] == 1) & (df["down"] >= split), "enter_tag"
        ] = "regime_down_upper"

        return df

    def populate_exit_trend(self, df: DataFrame, metadata: dict) -> DataFrame:
        flip = self.regime_flip_prob.value
        df.loc[
            (df["do_predict"] == 1)
            & (df["&-regime"] == "down")
            & (df["down"] >= flip),
            "exit_long",
        ] = 1
        df.loc[
            (df["do_predict"] == 1)
            & (df["&-regime"] == "up")
            & (df["up"] >= flip),
            "exit_short",
        ] = 1
        return df

    # ==================================================================
    # Helpers
    # ==================================================================
    def _last_candle(self, pair: str) -> Optional[pd.Series]:
        try:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if df is None or df.empty:
                return None
            return df.iloc[-1]
        except Exception as e:
            logger.warning(f"{pair}: could not fetch analyzed dataframe: {e}")
            return None

    def _candle_at(self, pair: str, when: datetime) -> Optional[pd.Series]:
        """Candle at (or immediately before) a specific time — deterministic
        fallback for entry-time values if custom data is unavailable."""
        try:
            df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            if df is None or df.empty:
                return None
            sel = df[df["date"] <= when]
            if sel.empty:
                return None
            return sel.iloc[-1]
        except Exception:
            return None

    def _daily_realized_pnl_pct(self) -> float:
        """Live-mode daily loss check. In backtesting the MaxDrawdown
        daily protection is authoritative; this may no-op there."""
        try:
            day_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            closed_today = Trade.get_trades_proxy(is_open=False, close_date=day_start)
            realized = sum(t.close_profit_abs or 0.0 for t in closed_today)
            equity = self.wallets.get_total_stake_amount() if self.wallets else 0.0
            if equity <= 0:
                return 0.0
            pnl_pct = realized / equity
            if pnl_pct <= -self.max_daily_loss_pct:
                logger.warning(f"Daily loss check: {pnl_pct:.2%} - limit reached.")
            return pnl_pct
        except Exception as e:
            logger.warning(f"Daily PnL check failed (failing safe -> 0): {e}")
            return 0.0

    def _entry_atr_pct(self, trade: Trade) -> Optional[float]:
        """Entry-time ATR%: custom data first, then the candle at open time
        (deterministic), then current candle (last resort, logged)."""
        try:
            stored = trade.get_custom_data("atr_pct_entry")
            if stored is not None and float(stored) > 0:
                return float(stored)
        except Exception:
            pass

        candle = self._candle_at(trade.pair, trade.open_date_utc)
        if candle is not None:
            atr = float(candle.get("atr_pct", np.nan))
            if not np.isnan(atr) and atr > 0:
                logger.info(
                    f"{trade.pair}: entry ATR custom data missing - "
                    f"using open-date candle ATR ({atr:.4%}) [AUDIT]"
                )
                return atr

        candle = self._last_candle(trade.pair)
        if candle is not None:
            atr = float(candle.get("atr_pct", np.nan))
            if not np.isnan(atr) and atr > 0:
                logger.warning(
                    f"{trade.pair}: falling back to CURRENT candle ATR "
                    f"({atr:.4%}) - stop no longer entry-anchored! [AUDIT]"
                )
                return atr
        return None

    # ==================================================================
    # Risk management callbacks
    # ==================================================================
    def order_filled(self, pair: str, trade: Trade, order, current_time: datetime, **kwargs) -> None:
        try:
            if order.ft_order_side == trade.entry_side:
                if not trade.get_custom_data("atr_pct_entry"):
                    candle = self._last_candle(pair)
                    if candle is not None:
                        atr = float(candle.get("atr_pct", np.nan))
                        if not np.isnan(atr) and atr > 0:
                            trade.set_custom_data("atr_pct_entry", atr)
                            stop_mult = self.atr_stop_multiplier.value
                            stop_price = (
                                trade.open_rate * (1 + stop_mult * atr)
                                if trade.is_short
                                else trade.open_rate * (1 - stop_mult * atr)
                            )
                            intended_risk = (
                                trade.stake_amount * (trade.leverage or 1.0)
                                * stop_mult * atr
                            )
                            trade.set_custom_data("intended_risk", intended_risk)
                            logger.info(
                                f"[AUDIT-ENTRY] {pair} {trade.trade_direction} "
                                f"open={trade.open_rate:.6g} atr={atr:.4%} "
                                f"stop={stop_price:.6g} stake={trade.stake_amount:.2f} "
                                f"lev={trade.leverage} intended_risk={intended_risk:.2f} USDT"
                            )
            else:
                # exit fill: realized vs intended risk
                intended = trade.get_custom_data("intended_risk")
                realized = trade.close_profit_abs
                if intended and realized is not None and realized < 0:
                    logger.info(
                        f"[AUDIT-EXIT] {pair} loss={realized:.2f} USDT "
                        f"intended_max_risk={float(intended):.2f} USDT "
                        f"ratio={abs(realized) / float(intended):.2f}"
                    )
        except Exception as e:
            logger.warning(f"{pair}: order_filled audit failed: {e}")

    def confirm_trade_entry(
        self, pair: str, order_type: str, amount: float, rate: float,
        time_in_force: str, current_time: datetime,
        entry_tag: Optional[str], side: str, **kwargs,
    ) -> bool:
        if self._daily_realized_pnl_pct() <= -self.max_daily_loss_pct:
            logger.warning(f"{pair}: entry rejected - daily loss limit reached.")
            return False

        open_trades = Trade.get_open_trades()
        same_dir = sum(
            1 for t in open_trades
            if (t.is_short and side == "short") or (not t.is_short and side == "long")
        )
        if same_dir >= self.max_same_direction_trades:
            logger.info(f"{pair}: entry rejected - {same_dir} open {side} positions.")
            return False

        candle = self._last_candle(pair)
        if candle is None or candle.get("do_predict", 0) != 1:
            return False
        return True

    def custom_stake_amount(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_stake: float, min_stake: Optional[float], max_stake: float,
        leverage: float, entry_tag: Optional[str], side: str, **kwargs,
    ) -> float:
        candle = self._last_candle(pair)
        if candle is None:
            return proposed_stake

        try:
            equity = self.wallets.get_total_stake_amount()
            conf_scale = self.conf_scale_min

            di = float(candle.get("DI_values", 0.0))
            if di <= self.di_full_size_threshold:
                di_scale = 1.0
            else:
                di_scale = max(
                    0.0,
                    (self.di_zero_size_threshold - di)
                    / (self.di_zero_size_threshold - self.di_full_size_threshold),
                )
            if di_scale <= 0:
                return 0.0

            risk_pct = min(
                self.base_risk_per_trade * conf_scale * di_scale,
                self.max_risk_per_trade,
            )
            risk_amount = equity * risk_pct

            atr_pct = float(candle["atr_pct"])
            stop_distance_pct = self.atr_stop_multiplier.value * atr_pct
            if stop_distance_pct <= 0 or np.isnan(stop_distance_pct):
                return proposed_stake

            stake = risk_amount / (leverage * stop_distance_pct)
            stake = min(stake, max_stake)
            if min_stake:
                stake = max(stake, min_stake)

            logger.info(
                f"{pair} {side}: DI={di:.2f} di_scale={di_scale:.2f} "
                f"risk={risk_pct:.3%} lev={leverage:.1f} stake={stake:.2f}"
            )
            return stake
        except Exception as e:
            logger.warning(f"{pair}: custom_stake_amount failed ({e}).")
            return proposed_stake

    def leverage(
        self, pair: str, current_time: datetime, current_rate: float,
        proposed_leverage: float, max_leverage: float,
        entry_tag: Optional[str], side: str, **kwargs,
    ) -> float:
        candle = self._last_candle(pair)
        lev = self.lev_mid_vol
        if candle is not None:
            vol_pct = candle.get("vol_percentile", np.nan)
            if not np.isnan(vol_pct):
                if vol_pct < 0.40:
                    lev = self.lev_low_vol
                elif vol_pct <= 0.70:
                    lev = self.lev_mid_vol
                else:
                    lev = self.lev_high_vol
        return float(min(lev, self.max_leverage_cap, max_leverage))

    def custom_stoploss(
        self, pair: str, trade: Trade, current_time: datetime,
        current_rate: float, current_profit: float, after_fill: bool, **kwargs,
    ) -> Optional[float]:
        atr_entry = self._entry_atr_pct(trade)
        if atr_entry is None:
            return None

        lev = trade.leverage or 1.0
        price_profit = current_profit / lev

        # Phase 2: trailing after the trade has proven itself
        if price_profit >= self.atr_trail_trigger.value * atr_entry:
            return -(self.atr_trail_distance.value * atr_entry * lev)

        # Phase 1: fixed, entry-anchored stop
        stop_mult = self.atr_stop_multiplier.value
        if trade.is_short:
            stop_price = trade.open_rate * (1 + stop_mult * atr_entry)
            rel = (stop_price - current_rate) / current_rate
        else:
            stop_price = trade.open_rate * (1 - stop_mult * atr_entry)
            rel = (current_rate - stop_price) / current_rate

        rel = max(rel, 0.0005)
        return -(rel * lev)

    def custom_exit(
        self, pair: str, trade: Trade, current_time: datetime,
        current_rate: float, current_profit: float, **kwargs,
    ) -> Optional[str]:
        candle = self._last_candle(pair)
        if candle is None or candle.get("do_predict", 0) != 1:
            return None

        is_short = trade.is_short
        entry_class_prob = candle["down"] if is_short else candle["up"]
        opposing_prob = candle["up"] if is_short else candle["down"]
        predicted_regime = candle["&-regime"]
        flip = self.regime_flip_prob.value

        # 1) Regime flip — always active, overrides everything
        if is_short and predicted_regime == "up" and opposing_prob >= flip:
            return "regime_flip"
        if not is_short and predicted_regime == "down" and opposing_prob >= flip:
            return "regime_flip"

        # 2) Confidence decay — ONLY before the trade proves itself.
        #    Once price profit has reached the trail trigger, the trailing
        #    stop manages the exit; decay no longer scratches runners.
        atr_entry = self._entry_atr_pct(trade)
        lev = trade.leverage or 1.0
        price_profit = current_profit / lev
        trailing_active = (
            atr_entry is not None
            and price_profit >= self.atr_trail_trigger.value * atr_entry
        )
        if not trailing_active and entry_class_prob < self.confidence_decay_exit.value:
            return "confidence_decay"

        # 3) DI blowout — always active
        if candle.get("DI_values", 0.0) >= self.di_zero_size_threshold:
            return "di_blowout"

        return None