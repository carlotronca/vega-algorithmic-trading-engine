import time
from datetime import datetime, timezone


class SafetyLayer:
    def __init__(
        self,
        state_manager,
        max_daily_loss_pct=2.0,
        stale_candle_seconds=5400
    ):
        self.state_manager = state_manager
        self.max_daily_loss_pct = float(max_daily_loss_pct)
        self.stale_candle_seconds = int(stale_candle_seconds)

    def utc_today(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def check_emergency_stop(self):
        state = self.state_manager.get_state()
        safety = state.get("safety", {})

        if safety.get("emergency_stop") is True:
            return False, "EMERGENCY_STOP_ACTIVE"

        return True, "OK"

    def check_daily_loss(self, current_balance):
        state = self.state_manager.get_state()
        daily = state.get("daily", {})

        start_balance = daily.get("start_balance")

        if start_balance is None:
            return True, "OK"

        start_balance = float(start_balance)
        current_balance = float(current_balance)

        if start_balance <= 0:
            return False, "INVALID_DAILY_START_BALANCE"

        loss_pct = ((start_balance - current_balance) / start_balance) * 100

        if loss_pct >= self.max_daily_loss_pct:
            reason = (
                f"MAX_DAILY_LOSS_REACHED "
                f"{loss_pct:.2f}% >= {self.max_daily_loss_pct:.2f}%"
            )
            self.state_manager.mark_daily_loss_reached(reason)
            return False, reason

        return True, "OK"

    def check_stale_candle(self, candle):
        candle_timestamp = getattr(candle, "timestamp", None)

        if candle_timestamp is None:
            return False, "MISSING_CANDLE_TIMESTAMP"

        now_ts = time.time()
        age_seconds = now_ts - float(candle_timestamp)

        if age_seconds > self.stale_candle_seconds:
            return False, (
                f"STALE_CANDLE "
                f"age={age_seconds:.0f}s "
                f"limit={self.stale_candle_seconds}s"
            )

        return True, "OK"

    def can_process_candle(self, candle):
        ok, reason = self.check_emergency_stop()
        if not ok:
            return False, reason

        ok, reason = self.check_stale_candle(candle)
        if not ok:
            return False, reason

        return True, "OK"

    def can_open_trade(self, candle, engine, signal):
        ok, reason = self.check_emergency_stop()
        if not ok:
            return False, reason

        ok, reason = self.check_daily_loss(engine.balance)
        if not ok:
            return False, reason

        ok, reason = self.check_stale_candle(candle)
        if not ok:
            return False, reason

        return True, "OK"

    def register_candle(self, candle):
        self.state_manager.update_market(
            symbol=getattr(candle, "symbol", None),
            interval="1h",
            candle_timestamp=getattr(candle, "timestamp", None)
        )

    def register_open_position(self, position):
        self.state_manager.save_open_position(position)

    def register_closed_position(self, trade_id=None):
        self.state_manager.clear_position()

        if trade_id is not None:
            self.state_manager.set_last_trade_id(trade_id)

    def register_error(self, error):
        self.state_manager.set_error(error)
