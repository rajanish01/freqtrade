"""Bollinger + RSI/MFI band reversion — the portfolio control case.

Hypothesis: price that closes outside a Bollinger Band with momentum confirming
exhaustion reverts to the band mid; the BB-width filter suppresses entries
during squeezes, where touching the band means tight bands, not stretched
price. Short-horizon liquidity provision: the counterparty is a taker paying
the spread for immediate fills; the edge is small and dies in trends.
Plan: user_data/strategies/plan/BBRSIMeanReversion.md.
"""

import talib.abstract as ta
from math import isfinite

from pandas import DataFrame
from technical import qtpylib

from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy


class BBRSIMeanReversion(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "15m"
    can_short = True
    use_custom_stoploss = False
    position_adjustment_enable = False

    minimal_roi = {"0": 0.05, "60": 0.025, "180": 0.01, "360": 0}
    stoploss = -0.12
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    startup_candle_count: int = 200

    target_vol_pct: float = 0.5
    max_leverage_cap: float = 3.0

    opt_rsi_entry = IntParameter(20, 40, default=30, space="buy")
    opt_mfi_entry = IntParameter(15, 40, default=30, space="buy")
    opt_min_bb_width = DecimalParameter(0.005, 0.05, default=0.01, space="buy")
    opt_min_vol_ratio = DecimalParameter(0.3, 1.5, default=0.5, space="buy")
    opt_rsi_exit = IntParameter(60, 85, default=70, space="sell")

    @property
    def protections(self):
        return [
            {"method": "CooldownPeriod", "stop_duration_candles": 2},
            {
                "method": "StoplossGuard",
                "lookback_period_candles": 96,
                "trade_limit": 1,
                "stop_duration_candles": 96,
                "only_per_pair": False,
                "only_per_side": False,
            },
            {
                "method": "MaxDrawdown",
                "lookback_period_candles": 2000,
                "trade_limit": 5,
                "max_allowed_drawdown": 0.10,
                "calculation_mode": "equity",
                "stop_duration_candles": 288,
            },
        ]

    def leverage(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        df, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0:
            return 1.0
        natr = df["ind_natr_14"].iat[-1]
        if not isfinite(natr) or natr <= 0:
            return 1.0
        lev = self.target_vol_pct / natr
        return float(max(1.0, min(lev, self.max_leverage_cap, max_leverage)))

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        bb = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), 20, 2)
        dataframe["ind_bb_lower"] = bb["lower"]
        dataframe["ind_bb_mid"] = bb["mid"]
        dataframe["ind_bb_upper"] = bb["upper"]
        dataframe["ind_bb_width"] = (
            dataframe["ind_bb_upper"] - dataframe["ind_bb_lower"]
        ) / dataframe["ind_bb_mid"]
        dataframe["ind_bb_pct"] = (
            dataframe["close"] - dataframe["ind_bb_lower"]
        ) / (dataframe["ind_bb_upper"] - dataframe["ind_bb_lower"])
        dataframe["ind_rsi_14"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ind_mfi_14"] = ta.MFI(dataframe, timeperiod=14)
        dataframe["ind_vol_sma_20"] = dataframe["volume"].rolling(20).mean()
        dataframe["ind_natr_14"] = ta.NATR(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "enter_long"] = 0
        dataframe.loc[:, "enter_short"] = 0
        dataframe.loc[:, "enter_tag"] = ""

        vol_ok = (dataframe["volume"] > 0) & (
            dataframe["volume"]
            > dataframe["ind_vol_sma_20"] * self.opt_min_vol_ratio.value
        )
        width_ok = dataframe["ind_bb_width"] > self.opt_min_bb_width.value

        long_cond = (
            (dataframe["close"] < dataframe["ind_bb_lower"])
            & (dataframe["ind_rsi_14"] < self.opt_rsi_entry.value)
            & (dataframe["ind_mfi_14"] < self.opt_mfi_entry.value)
            & width_ok
            & vol_ok
        )
        dataframe.loc[long_cond, "enter_long"] = 1
        dataframe.loc[long_cond, "enter_tag"] = "bb_lower_reversion"

        short_cond = (
            (dataframe["close"] > dataframe["ind_bb_upper"])
            & (dataframe["ind_rsi_14"] > (100 - self.opt_rsi_entry.value))
            & (dataframe["ind_mfi_14"] > (100 - self.opt_mfi_entry.value))
            & width_ok
            & vol_ok
        )
        dataframe.loc[short_cond, "enter_short"] = 1
        dataframe.loc[short_cond, "enter_tag"] = "bb_upper_reversion"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "exit_long"] = 0
        dataframe.loc[:, "exit_short"] = 0
        dataframe.loc[:, "exit_tag"] = ""

        long_exit = dataframe["ind_rsi_14"] > self.opt_rsi_exit.value
        dataframe.loc[long_exit, "exit_long"] = 1
        dataframe.loc[long_exit, "exit_tag"] = "rsi_exit"

        short_exit = dataframe["ind_rsi_14"] < (100 - self.opt_rsi_exit.value)
        dataframe.loc[short_exit, "exit_short"] = 1
        dataframe.loc[short_exit, "exit_tag"] = "rsi_exit"
        return dataframe
