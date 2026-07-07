import time


# =============================
# POSITION OBJECT
# =============================
class Position:

    def __init__(
        self,
        side,
        symbol,
        entry_price,
        size,
        stop_loss=None,
        take_profit=None,

        # ==========================================
        # EXCHANGE ENTRY LIFECYCLE
        # ==========================================
        entry_order_id=None,
        entry_client_order_id=None,
        entry_exchange_status=None,

        filled_size=None,
        avg_fill_price=None,

        # ==========================================
        # STOP LOSS PROTECTION
        # ==========================================
        stop_loss_order_id=None,
        stop_loss_client_order_id=None,
        stop_loss_exchange_status=None,
        stop_loss_trigger_reference=None,

        # ==========================================
        # TAKE PROFIT PROTECTION
        # ==========================================
        take_profit_order_id=None,
        take_profit_client_order_id=None,
        take_profit_exchange_status=None,
        take_profit_trigger_reference=None,

        # ==========================================
        # PROTECTION HEALTH
        # ==========================================
        is_protected=False,
        stop_loss_verified=False,
        take_profit_verified=False,
        protection_last_verified_utc=None,

        # ==========================================
        # SYNTHETIC OCO
        # ==========================================
        synthetic_oco_enabled=False,

        # ==========================================
        # RECONCILIATION
        # ==========================================
        exchange_sync_required=False,
        last_exchange_sync_utc=None,
        exchange_sync_status=None,

        # ==========================================
        # RECOVERY / RUNTIME
        # ==========================================
        recovered_after_restart=False,
        runtime_position_state="POSITION_OPEN"
    ):

        # ==========================================
        # CORE POSITION DATA
        # ==========================================
        self.side = str(side)
        self.symbol = str(symbol)

        self.entry_price = float(entry_price)
        self.size = float(size)

        self.stop_loss = (
            float(stop_loss)
            if stop_loss is not None
            else None
        )

        self.take_profit = (
            float(take_profit)
            if take_profit is not None
            else None
        )

        self.open_time = float(time.time())

        # ==========================================
        # POSITION STATE
        # ==========================================
        self.is_open = True

        # ==========================================
        # PNL TRACKING
        # ==========================================
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0

        # ==========================================
        # EXCHANGE ENTRY LIFECYCLE
        # ==========================================
        self.entry_order_id = entry_order_id
        self.entry_client_order_id = entry_client_order_id
        self.entry_exchange_status = entry_exchange_status

        self.filled_size = (
            float(filled_size)
            if filled_size is not None
            else None
        )

        self.avg_fill_price = (
            float(avg_fill_price)
            if avg_fill_price is not None
            else None
        )

        # ==========================================
        # STOP LOSS PROTECTION
        # ==========================================
        self.stop_loss_order_id = stop_loss_order_id
        self.stop_loss_client_order_id = stop_loss_client_order_id
        self.stop_loss_exchange_status = stop_loss_exchange_status
        self.stop_loss_trigger_reference = stop_loss_trigger_reference

        # ==========================================
        # TAKE PROFIT PROTECTION
        # ==========================================
        self.take_profit_order_id = take_profit_order_id
        self.take_profit_client_order_id = take_profit_client_order_id
        self.take_profit_exchange_status = take_profit_exchange_status
        self.take_profit_trigger_reference = take_profit_trigger_reference

        # ==========================================
        # PROTECTION HEALTH
        # ==========================================
        self.is_protected = bool(is_protected)
        self.stop_loss_verified = bool(stop_loss_verified)
        self.take_profit_verified = bool(take_profit_verified)

        self.protection_last_verified_utc = (
            str(protection_last_verified_utc)
            if protection_last_verified_utc is not None
            else None
        )

        # ==========================================
        # SYNTHETIC OCO
        # ==========================================
        self.synthetic_oco_enabled = bool(synthetic_oco_enabled)

        # ==========================================
        # RECONCILIATION
        # ==========================================
        self.exchange_sync_required = bool(exchange_sync_required)

        self.last_exchange_sync_utc = (
            str(last_exchange_sync_utc)
            if last_exchange_sync_utc is not None
            else None
        )

        self.exchange_sync_status = (
            str(exchange_sync_status)
            if exchange_sync_status is not None
            else None
        )

        # ==========================================
        # RECOVERY / RUNTIME
        # ==========================================
        self.recovered_after_restart = bool(recovered_after_restart)

        self.runtime_position_state = str(runtime_position_state)

    # =============================
    # UPDATE UNREALIZED PNL
    # =============================
    def update_pnl(self, current_price):

        current_price = float(current_price)

        pnl = (
            (current_price - self.entry_price)
            * self.size
        )

        if self.side == "SELL":
            pnl = -pnl

        self.unrealized_pnl = float(pnl)

        return self.unrealized_pnl

    # =============================
    # CLOSE POSITION
    # =============================
    def close(self, exit_price):

        exit_price = float(exit_price)

        pnl = (
            (exit_price - self.entry_price)
            * self.size
        )

        if self.side == "SELL":
            pnl = -pnl

        self.realized_pnl = float(pnl)

        self.is_open = False

        self.runtime_position_state = "POSITION_CLOSED"

        return self.realized_pnl

    # =============================
    # PROTECTION STATUS
    # =============================
    def mark_protected(self):

        self.is_protected = True

        self.runtime_position_state = "POSITION_PROTECTED"

    def mark_unprotected(self):

        self.is_protected = False

        self.runtime_position_state = "POSITION_UNPROTECTED"

    def require_exchange_sync(self):

        self.exchange_sync_required = True

        self.runtime_position_state = "POSITION_SYNC_REQUIRED"

    # =============================
    # STRING DEBUG
    # =============================
    def __repr__(self):

        return (
            f"Position("
            f"side={self.side}, "
            f"symbol={self.symbol}, "
            f"entry={self.entry_price}, "
            f"size={self.size}, "
            f"sl={self.stop_loss}, "
            f"tp={self.take_profit}, "
            f"open={self.is_open}, "
            f"protected={self.is_protected}, "
            f"runtime_state={self.runtime_position_state}"
            f")"
        )
