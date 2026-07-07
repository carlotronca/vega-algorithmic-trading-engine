from models.position import Position


class RecoveryManager:
    def __init__(self, state_manager, journal=None):
        self.state_manager = state_manager
        self.journal = journal

    def has_open_position(self):
        state = self.state_manager.get_state()
        position_state = state.get("position", {})
        return position_state.get("is_open") is True

    def restore_position(self, engine):
        state = self.state_manager.get_state()
        position_state = state.get("position", {})

        if position_state.get("is_open") is not True:
            self._log_event(
                "RECOVERY_NO_OPEN_POSITION",
                {
                    "message": "No open position in state.json"
                }
            )
            return False

        required_fields = [
            "symbol",
            "side",
            "entry_price",
            "size",
            "stop_loss",
            "take_profit",
            "entry_timestamp"
        ]

        missing = [
            field for field in required_fields
            if position_state.get(field) is None
        ]

        if missing:
            reason = f"Missing position fields: {missing}"
            self.state_manager.lock(reason)

            self._log_event(
                "RECOVERY_FAILED",
                {
                    "reason": reason,
                    "position_state": position_state
                }
            )

            return False

        restored_position = Position(
            side=position_state["side"],
            symbol=position_state["symbol"],
            entry_price=float(position_state["entry_price"]),
            size=float(position_state["size"]),
            stop_loss=float(position_state["stop_loss"]),
            take_profit=float(position_state["take_profit"])
        )

        restored_position.entry_timestamp = float(
            position_state["entry_timestamp"]
        )

        restored_position.signal_metadata = position_state.get(
            "signal_metadata",
            {}
        )

        restored_position.entry_fee = float(
            position_state.get("entry_fee", 0.0)
        )

        restored_position.risk_per_trade = float(
            position_state.get("risk_per_trade", getattr(engine, "risk_per_trade", 0.0))
        )

        restored_position.risk_amount = float(
            position_state.get("risk_amount", 0.0)
        )

        restored_position.stop_distance = float(
            position_state.get("stop_distance", 0.0)
        )

        engine.position = restored_position

        self._log_event(
            "RECOVERY_POSITION_RESTORED",
            {
                "symbol": restored_position.symbol,
                "side": restored_position.side,
                "entry_price": restored_position.entry_price,
                "size": restored_position.size,
                "stop_loss": restored_position.stop_loss,
                "take_profit": restored_position.take_profit,
                "entry_timestamp": restored_position.entry_timestamp
            }
        )

        return True

    def check_recovered_position_price(self, engine, market_price):
        """
        Dopo recovery controlla se il prezzo corrente è già fuori da TP/SL.

        In paper:
        - chiude simulato con close_position()

        In live futuro:
        - prima servirà exchange reconciliation.
        """

        if engine.position is None:
            return True, "NO_POSITION"

        pos = engine.position
        price = float(market_price)

        self._log_event(
            "RECOVERY_POSITION_STILL_VALID",
            {
                "symbol": pos.symbol,
                "price": price,
                "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit
            }
        )

        return True, "POSITION_STILL_VALID"

    def _log_event(self, event_type, payload):
        if self.journal is not None:
            self.journal.log_event(
                event_type=event_type,
                payload=payload
            )
