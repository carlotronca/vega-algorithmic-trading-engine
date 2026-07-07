from models.signal import Signal


class EMAVolumeStrategy:

    def __init__(self):

        self.prices = []
        self.candles = []

        self.ema_fast = None
        self.ema_slow = None
        self.ema_regime = None

        self.prev_ema_fast = None
        self.prev_ema_slow = None

        self.alpha_fast = 2 / (9 + 1)
        self.alpha_slow = 2 / (21 + 1)
        self.alpha_regime = 2 / (200 + 1)

        self.atr_period = 14
        self.sl_atr_multiplier = 2.0
        self.tp_atr_multiplier = 3.5

        # EMA EXIT disabled for V2.4.3 RC
        self.min_ema_exit_hours = 6
        self.ema_exit_enabled = False

        self.adx_period = 14
        self.adx_threshold = 25.0

        self.rsi_period = 14
        self.rsi_overbought = 70.0

        # Anti re-entry cooldown
        self.reentry_cooldown_hours = 12
        self.last_trade_exit_timestamp = None

        # EMA200 extension filter
        self.max_ema200_extension_pct = 3.5

    def calc_ema(self, prev, price, alpha):
        return price * alpha + prev * (1 - alpha)

    def calc_atr(self):

        if len(self.candles) < self.atr_period + 1:
            return None

        true_ranges = []
        recent_candles = self.candles[-self.atr_period:]

        for i in range(1, len(recent_candles)):

            current = recent_candles[i]
            previous = recent_candles[i - 1]

            high = float(current.high)
            low = float(current.low)
            prev_close = float(previous.close)

            true_range = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )

            true_ranges.append(true_range)

        if not true_ranges:
            return None

        return sum(true_ranges) / len(true_ranges)

    def calc_adx(self):

        required_candles = (self.adx_period * 2) + 1

        if len(self.candles) < required_candles:
            return None

        recent_candles = self.candles[-required_candles:]

        true_ranges = []
        plus_dm_values = []
        minus_dm_values = []

        for i in range(1, len(recent_candles)):

            current = recent_candles[i]
            previous = recent_candles[i - 1]

            current_high = float(current.high)
            current_low = float(current.low)
            previous_high = float(previous.high)
            previous_low = float(previous.low)
            previous_close = float(previous.close)

            high_diff = current_high - previous_high
            low_diff = previous_low - current_low

            plus_dm = 0.0
            minus_dm = 0.0

            if high_diff > low_diff and high_diff > 0:
                plus_dm = high_diff

            if low_diff > high_diff and low_diff > 0:
                minus_dm = low_diff

            true_range = max(
                current_high - current_low,
                abs(current_high - previous_close),
                abs(current_low - previous_close)
            )

            true_ranges.append(true_range)
            plus_dm_values.append(plus_dm)
            minus_dm_values.append(minus_dm)

        dx_values = []

        for i in range(self.adx_period, len(true_ranges) + 1):

            tr_slice = true_ranges[i - self.adx_period:i]
            plus_dm_slice = plus_dm_values[i - self.adx_period:i]
            minus_dm_slice = minus_dm_values[i - self.adx_period:i]

            tr_sum = sum(tr_slice)

            if tr_sum <= 0:
                continue

            plus_di = 100 * (sum(plus_dm_slice) / tr_sum)
            minus_di = 100 * (sum(minus_dm_slice) / tr_sum)

            di_sum = plus_di + minus_di

            if di_sum <= 0:
                continue

            dx = 100 * (abs(plus_di - minus_di) / di_sum)
            dx_values.append(dx)

        if len(dx_values) < self.adx_period:
            return None

        return float(sum(dx_values[-self.adx_period:]) / self.adx_period)

    def calc_rsi(self):

        if len(self.prices) < self.rsi_period + 1:
            return None

        recent_prices = self.prices[-(self.rsi_period + 1):]

        gains = []
        losses = []

        for i in range(1, len(recent_prices)):

            change = recent_prices[i] - recent_prices[i - 1]

            if change > 0:
                gains.append(change)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(change))

        avg_gain = sum(gains) / self.rsi_period
        avg_loss = sum(losses) / self.rsi_period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return float(rsi)

    def sync_last_trade_exit_timestamp(self, engine):

        if not hasattr(engine, "trades"):
            return

        if not engine.trades:
            return

        last_trade = engine.trades[-1]
        exit_timestamp = last_trade.get("exit_timestamp")

        if exit_timestamp is not None:
            self.last_trade_exit_timestamp = float(exit_timestamp)

    def reentry_allowed(self, candle):

        if self.last_trade_exit_timestamp is None:
            return True

        current_timestamp = getattr(candle, "timestamp", None)

        if current_timestamp is None:
            return True

        hours_since_exit = (
            float(current_timestamp) - float(self.last_trade_exit_timestamp)
        ) / 3600

        return hours_since_exit >= self.reentry_cooldown_hours

    def on_candle(self, candle, engine):

        self.sync_last_trade_exit_timestamp(engine)

        price = float(candle.close)

        self.prices.append(price)
        self.candles.append(candle)

        if len(self.prices) < 200:
            return None

        if self.ema_fast is None:
            self.ema_fast = price
            self.ema_slow = price
            self.ema_regime = price

        self.prev_ema_fast = self.ema_fast
        self.prev_ema_slow = self.ema_slow

        self.ema_fast = self.calc_ema(
            self.ema_fast,
            price,
            self.alpha_fast
        )

        self.ema_slow = self.calc_ema(
            self.ema_slow,
            price,
            self.alpha_slow
        )

        self.ema_regime = self.calc_ema(
            self.ema_regime,
            price,
            self.alpha_regime
        )

        atr = self.calc_atr()

        if atr is None or atr <= 0:
            return None

        adx = self.calc_adx()

        if adx is None:
            return None

        adx_confirmed = adx >= self.adx_threshold

        rsi = self.calc_rsi()

        if rsi is None:
            return None

        rsi_allowed = rsi < self.rsi_overbought

        bullish_regime = price > self.ema_regime

        ema_cross_up = (
            self.prev_ema_fast is not None
            and self.prev_ema_slow is not None
            and self.prev_ema_fast <= self.prev_ema_slow
            and self.ema_fast > self.ema_slow
        )

        cooldown_allowed = self.reentry_allowed(candle)

        ema200_extension_pct = (
            ((price - self.ema_regime) / self.ema_regime) * 100
            if self.ema_regime != 0
            else 0
        )

        ema_extension_allowed = (
            ema200_extension_pct <= self.max_ema200_extension_pct
        )

        print(
            f"💰 CLOSED PRICE {candle.symbol}={price:.3f}"
        )

        print(
            f"📊 "
            f"EMA9={self.ema_fast:.2f} | "
            f"EMA21={self.ema_slow:.2f} | "
            f"EMA200={self.ema_regime:.2f} | "
            f"ATR={atr:.4f} | "
            f"ADX={adx:.2f} | "
            f"RSI={rsi:.2f} | "
            f"REGIME={'BULL' if bullish_regime else 'NO TRADE'} | "
            f"EMA_CROSS_UP={'YES' if ema_cross_up else 'NO'} | "
            f"ADX_FILTER={'OK' if adx_confirmed else 'WEAK'} | "
            f"RSI_FILTER={'OK' if rsi_allowed else 'OVERBOUGHT'} | "
            f"COOLDOWN={'OK' if cooldown_allowed else 'WAIT'} | "
            f"EMA_EXT={ema200_extension_pct:.2f}% | "
            f"EMA_EXT_FILTER={'OK' if ema_extension_allowed else 'EXTENDED'} | "
            f"EMA_EXIT={'ON' if self.ema_exit_enabled else 'OFF'}"
        )

        if engine.position is None:

            if (
                bullish_regime
                and ema_cross_up
                and adx_confirmed
                and rsi_allowed
                and cooldown_allowed
                and ema_extension_allowed
            ):

                stop_loss = price - (self.sl_atr_multiplier * atr)
                take_profit = price + (self.tp_atr_multiplier * atr)

                return Signal(
                    side="BUY",
                    symbol=candle.symbol,
                    entry_price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    confidence=0.80,
                    metadata={
                        "strategy": "EMA_REGIME_ATR_ADX_RSI_CROSS_ENTRY_V2_4_3_EMA200_EXTENSION_FILTER",
                        "ema_fast": self.ema_fast,
                        "ema_slow": self.ema_slow,
                        "ema_regime": self.ema_regime,
                        "prev_ema_fast": self.prev_ema_fast,
                        "prev_ema_slow": self.prev_ema_slow,
                        "ema_cross_up": ema_cross_up,
                        "atr": atr,
                        "adx": adx,
                        "adx_threshold": self.adx_threshold,
                        "adx_confirmed": adx_confirmed,
                        "rsi": rsi,
                        "rsi_overbought": self.rsi_overbought,
                        "rsi_allowed": rsi_allowed,
                        "sl_atr_multiplier": self.sl_atr_multiplier,
                        "tp_atr_multiplier": self.tp_atr_multiplier,
                        "min_ema_exit_hours": self.min_ema_exit_hours,
                        "ema_exit_enabled": self.ema_exit_enabled,
                        "reentry_cooldown_hours": self.reentry_cooldown_hours,
                        "cooldown_allowed": cooldown_allowed,
                        "ema200_extension_pct": ema200_extension_pct,
                        "max_ema200_extension_pct": self.max_ema200_extension_pct,
                        "ema_extension_allowed": ema_extension_allowed,
                        "regime": "BULL"
                    }
                )

        else:

            if not self.ema_exit_enabled:
                return None

            entry_timestamp = getattr(
                engine.position,
                "entry_timestamp",
                None
            )

            current_timestamp = getattr(
                candle,
                "timestamp",
                None
            )

            position_age_hours = None

            if (
                entry_timestamp is not None
                and current_timestamp is not None
            ):
                position_age_hours = (
                    float(current_timestamp) - float(entry_timestamp)
                ) / 3600

            ema_exit_allowed = (
                position_age_hours is not None
                and position_age_hours >= self.min_ema_exit_hours
            )

            if (
                self.ema_fast < self.ema_slow
                and price < self.ema_regime
                and ema_exit_allowed
            ):

                engine.close_position(
                    market_price=price,
                    reason="EMA CROSS + REGIME EXIT"
                )

                self.last_trade_exit_timestamp = float(current_timestamp)

        return None
