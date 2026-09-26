"""Bollinger + RSI/MFI band reversion — the portfolio control case.

Hypothesis: price that closes outside a Bollinger Band with momentum confirming
exhaustion reverts to the band mid; the BB-width filter suppresses entries
during squeezes, where touching the band means tight bands, not stretched
price. Short-horizon liquidity provision: the counterparty is a taker paying
the spread for immediate fills; the edge is small and dies in trends.
Plan: user_data/strategies/plan/BBRSIMeanReversion.md.
"""

from math import isfinite

from pandas import DataFrame

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
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "enter_long"] = 0
        dataframe.loc[:, "enter_short"] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[:, "exit_long"] = 0
        dataframe.loc[:, "exit_short"] = 0
        return dataframe
