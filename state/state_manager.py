# state/state_manager.py

import json
import os
from datetime import datetime, timezone


class StateManager:

    # =====================================================
    # INIT
    # =====================================================
    def __init__(
        self,
        state_path="state/state.json"
    ):

        self.state_path = state_path

        self.state = self.default_state()

        self.load()

    # =====================================================
    # TIME
    # =====================================================
    def utc_now(self):

        return datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    # =====================================================
    # DEFAULT STATE
    # =====================================================
    def default_state(self):

        return {

            "version": "2.5",

            "last_updated_utc": None,

            # =================================================
            # BOT STATE
            # =================================================
            "bot": {

                "mode": "PAPER",

                "api_write": False,

                "is_running": False
            },

            # =================================================
            # MARKET STATE
            # =================================================
            "market": {

                "symbol": None,

                "interval": None,

                "last_candle_timestamp": None
            },

            # =================================================
            # POSITION STATE
            # =================================================
            "position": {

                # =============================================
                # CORE POSITION
                # =============================================
                "is_open": False,

                "symbol": None,

                "side": None,

                "entry_price": None,

                "size": None,

                "stop_loss": None,

                "take_profit": None,

                "entry_timestamp": None,

                # =============================================
                # EXECUTION OPERATION
                # =============================================
                "operation_id": None,

                # =============================================
                # ENTRY LIFECYCLE
                # =============================================
                "entry_order_id": None,

                "entry_client_order_id": None,

                "entry_exchange_status": None,

                "filled_size": None,

                "avg_fill_price": None,

                "entry_filled_utc": None,

                # =============================================
                # STOP LOSS
                # =============================================
                "stop_loss_order_id": None,

                "stop_loss_client_order_id": None,

                "stop_loss_exchange_status": None,

                "stop_loss_trigger_reference": None,

                "sl_created_utc": None,

                # =============================================
                # TAKE PROFIT
                # =============================================
                "take_profit_order_id": None,

                "take_profit_client_order_id": None,

                "take_profit_exchange_status": None,

                "take_profit_trigger_reference": None,

                "tp_created_utc": None,

                # =============================================
                # PROTECTION HEALTH
                # =============================================
                "is_protected": False,

                "protection_level": "NONE",

                "stop_loss_verified": False,

                "take_profit_verified": False,

                "protection_last_verified_utc": None,

                "fully_protected_utc": None,

                # =============================================
                # SYNTHETIC OCO
                # =============================================
                "synthetic_oco_enabled": False,

                # =============================================
                # RECONCILIATION
                # =============================================
                "exchange_sync_required": False,

                "last_exchange_sync_utc": None,

                "exchange_sync_status": None,

                # =============================================
                # RECOVERY / RUNTIME
                # =============================================
                "recovered_after_restart": False,

                "runtime_position_state": (
                    "POSITION_CLOSED"
                ),

                "pending_action": "NONE",

                # =============================================
                # EXCHANGE TRUTH SNAPSHOT
                # =============================================
                "last_confirmed_exchange_position_qty": None,

                "last_confirmed_exchange_open_orders": [],

                "last_confirmed_exchange_sync_utc": None,

                # =============================================
                # EXISTING TELEMETRY
                # =============================================
                "signal_metadata": {},

                "entry_fee": 0.0,

                "risk_per_trade": None,

                "risk_amount": None,

                "stop_distance": None
            },

            # =================================================
            # DAILY STATE
            # =================================================
            "daily": {

                "date": None,

                "start_balance": None,

                "realized_pnl": 0.0,

                "max_daily_loss_reached": False
            },

            # =================================================
            # SAFETY STATE
            # =================================================
            "safety": {

                "emergency_stop": False,

                "locked": False,

                "lock_reason": None
            },

            # =================================================
            # RUNTIME STATE
            # =================================================
            "runtime": {

                "last_signal_id": None,

                "last_trade_id": None,

                "last_error": None
            }
        }

    # =====================================================
    # LOAD
    # =====================================================
    def load(self):

        if not os.path.exists(
            self.state_path
        ):

            self.save()

            return self.state

        with open(
            self.state_path,
            "r",
            encoding="utf-8"
        ) as f:

            self.state = json.load(f)

        return self.state

    # =====================================================
    # SAVE ATOMIC
    # =====================================================
    def save(self):

        os.makedirs(
            os.path.dirname(
                self.state_path
            ),
            exist_ok=True
        )

        self.state[
            "last_updated_utc"
        ] = self.utc_now()

        tmp_path = (
            self.state_path + ".tmp"
        )

        with open(
            tmp_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                self.state,
                f,
                indent=2
            )

            f.write("\n")

        os.replace(
            tmp_path,
            self.state_path
        )

    # =====================================================
    # BOT STATE
    # =====================================================
    def set_bot_running(
        self,
        is_running
    ):

        self.state["bot"][
            "is_running"
        ] = bool(is_running)

        self.save()

    def set_bot_mode(
        self,
        mode,
        api_write
    ):

        self.state["bot"][
            "mode"
        ] = str(mode)

        self.state["bot"][
            "api_write"
        ] = bool(api_write)

        self.save()

    # =====================================================
    # MARKET STATE
    # =====================================================
    def update_market(
        self,
        symbol,
        interval,
        candle_timestamp
    ):

        self.state["market"][
            "symbol"
        ] = symbol

        self.state["market"][
            "interval"
        ] = interval

        self.state["market"][
            "last_candle_timestamp"
        ] = candle_timestamp

        self.save()

    # =====================================================
    # POSITION HELPERS
    # =====================================================
    def get_position_state(self):

        return self.state.get(
            "position",
            {}
        )

    def get_runtime_position_state(self):

        return self.state[
            "position"
        ].get(
            "runtime_position_state"
        )

    def get_protection_level(self):

        return self.state[
            "position"
        ].get(
            "protection_level"
        )

    def get_pending_action(self):

        return self.state[
            "position"
        ].get(
            "pending_action"
        )

    # =====================================================
    # POSITION TRANSITION
    # =====================================================
    def transition_position_state(
        self,
        runtime_state,
        protection_level=None,
        pending_action=None,
        exchange_sync_required=None
    ):

        position = self.state[
            "position"
        ]

        position[
            "runtime_position_state"
        ] = str(runtime_state)

        if protection_level is not None:

            position[
                "protection_level"
            ] = str(protection_level)

        if pending_action is not None:

            position[
                "pending_action"
            ] = str(pending_action)

        if exchange_sync_required is not None:

            position[
                "exchange_sync_required"
            ] = bool(
                exchange_sync_required
            )

        position[
            "last_exchange_sync_utc"
        ] = self.utc_now()

        self.save()

    # =====================================================
    # UPDATE EXCHANGE SNAPSHOT TRUTH
    # =====================================================
    def update_exchange_truth_snapshot(
        self,
        position_qty=None,
        open_orders=None
    ):

        position = self.state[
            "position"
        ]

        position[
            "last_confirmed_exchange_position_qty"
        ] = position_qty

        position[
            "last_confirmed_exchange_open_orders"
        ] = (
            open_orders
            if open_orders is not None
            else []
        )

        position[
            "last_confirmed_exchange_sync_utc"
        ] = self.utc_now()

        self.save()

    # =====================================================
    # SAVE OPEN POSITION
    # =====================================================
    def save_open_position(
        self,
        position
    ):

        self.state["position"] = {

            # =============================================
            # CORE POSITION
            # =============================================
            "is_open": True,

            "symbol": getattr(
                position,
                "symbol",
                None
            ),

            "side": getattr(
                position,
                "side",
                None
            ),

            "entry_price": getattr(
                position,
                "entry_price",
                None
            ),

            "size": getattr(
                position,
                "size",
                None
            ),

            "stop_loss": getattr(
                position,
                "stop_loss",
                None
            ),

            "take_profit": getattr(
                position,
                "take_profit",
                None
            ),

            "entry_timestamp": getattr(
                position,
                "entry_timestamp",
                None
            ),

            # =============================================
            # EXECUTION OPERATION
            # =============================================
            "operation_id": getattr(
                position,
                "operation_id",
                None
            ),

            # =============================================
            # ENTRY LIFECYCLE
            # =============================================
            "entry_order_id": getattr(
                position,
                "entry_order_id",
                None
            ),

            "entry_client_order_id": getattr(
                position,
                "entry_client_order_id",
                None
            ),

            "entry_exchange_status": getattr(
                position,
                "entry_exchange_status",
                None
            ),

            "filled_size": getattr(
                position,
                "filled_size",
                None
            ),

            "avg_fill_price": getattr(
                position,
                "avg_fill_price",
                None
            ),

            "entry_filled_utc": getattr(
                position,
                "entry_filled_utc",
                None
            ),

            # =============================================
            # STOP LOSS
            # =============================================
            "stop_loss_order_id": getattr(
                position,
                "stop_loss_order_id",
                None
            ),

            "stop_loss_client_order_id": getattr(
                position,
                "stop_loss_client_order_id",
                None
            ),

            "stop_loss_exchange_status": getattr(
                position,
                "stop_loss_exchange_status",
                None
            ),

            "stop_loss_trigger_reference": getattr(
                position,
                "stop_loss_trigger_reference",
                None
            ),

            "sl_created_utc": getattr(
                position,
                "sl_created_utc",
                None
            ),

            # =============================================
            # TAKE PROFIT
            # =============================================
            "take_profit_order_id": getattr(
                position,
                "take_profit_order_id",
                None
            ),

            "take_profit_client_order_id": getattr(
                position,
                "take_profit_client_order_id",
                None
            ),

            "take_profit_exchange_status": getattr(
                position,
                "take_profit_exchange_status",
                None
            ),

            "take_profit_trigger_reference": getattr(
                position,
                "take_profit_trigger_reference",
                None
            ),

            "tp_created_utc": getattr(
                position,
                "tp_created_utc",
                None
            ),

            # =============================================
            # PROTECTION HEALTH
            # =============================================
            "is_protected": getattr(
                position,
                "is_protected",
                False
            ),

            "protection_level": getattr(
                position,
                "protection_level",
                "NONE"
            ),

            "stop_loss_verified": getattr(
                position,
                "stop_loss_verified",
                False
            ),

            "take_profit_verified": getattr(
                position,
                "take_profit_verified",
                False
            ),

            "protection_last_verified_utc": getattr(
                position,
                "protection_last_verified_utc",
                None
            ),

            "fully_protected_utc": getattr(
                position,
                "fully_protected_utc",
                None
            ),

            # =============================================
            # SYNTHETIC OCO
            # =============================================
            "synthetic_oco_enabled": getattr(
                position,
                "synthetic_oco_enabled",
                False
            ),

            # =============================================
            # RECONCILIATION
            # =============================================
            "exchange_sync_required": getattr(
                position,
                "exchange_sync_required",
                False
            ),

            "last_exchange_sync_utc": getattr(
                position,
                "last_exchange_sync_utc",
                None
            ),

            "exchange_sync_status": getattr(
                position,
                "exchange_sync_status",
                None
            ),

            # =============================================
            # RECOVERY / RUNTIME
            # =============================================
            "recovered_after_restart": getattr(
                position,
                "recovered_after_restart",
                False
            ),

            "runtime_position_state": getattr(
                position,
                "runtime_position_state",
                "POSITION_OPEN"
            ),

            "pending_action": getattr(
                position,
                "pending_action",
                "NONE"
            ),

            # =============================================
            # EXCHANGE TRUTH SNAPSHOT
            # =============================================
            "last_confirmed_exchange_position_qty": getattr(
                position,
                "last_confirmed_exchange_position_qty",
                None
            ),

            "last_confirmed_exchange_open_orders": getattr(
                position,
                "last_confirmed_exchange_open_orders",
                []
            ),

            "last_confirmed_exchange_sync_utc": getattr(
                position,
                "last_confirmed_exchange_sync_utc",
                None
            ),

            # =============================================
            # EXISTING TELEMETRY
            # =============================================
            "signal_metadata": getattr(
                position,
                "signal_metadata",
                {}
            ),

            "entry_fee": getattr(
                position,
                "entry_fee",
                0.0
            ),

            "risk_per_trade": getattr(
                position,
                "risk_per_trade",
                None
            ),

            "risk_amount": getattr(
                position,
                "risk_amount",
                None
            ),

            "stop_distance": getattr(
                position,
                "stop_distance",
                None
            )
        }

        self.save()

    # =====================================================
    # CLEAR POSITION
    # =====================================================
    def clear_position(self):

        self.state[
            "position"
        ] = self.default_state()[
            "position"
        ]

        self.save()

    # =====================================================
    # DAILY STATE
    # =====================================================
    def update_daily_state(
        self,
        date,
        start_balance,
        realized_pnl
    ):

        self.state["daily"][
            "date"
        ] = date

        self.state["daily"][
            "start_balance"
        ] = float(start_balance)

        self.state["daily"][
            "realized_pnl"
        ] = float(realized_pnl)

        self.save()

    def mark_daily_loss_reached(
        self,
        reason
    ):

        self.state["daily"][
            "max_daily_loss_reached"
        ] = True

        self.lock(reason)

    # =====================================================
    # RUNTIME STATE
    # =====================================================
    def set_last_signal_id(
        self,
        signal_id
    ):

        self.state["runtime"][
            "last_signal_id"
        ] = signal_id

        self.save()

    def set_last_trade_id(
        self,
        trade_id
    ):

        self.state["runtime"][
            "last_trade_id"
        ] = trade_id

        self.save()

    def set_error(
        self,
        error
    ):

        self.state["runtime"][
            "last_error"
        ] = str(error)

        self.save()

    # =====================================================
    # SAFETY STATE
    # =====================================================
    def emergency_stop(
        self,
        reason="manual emergency stop"
    ):

        self.state["safety"][
            "emergency_stop"
        ] = True

        self.lock(reason)

    def clear_emergency_stop(self):

        self.state["safety"][
            "emergency_stop"
        ] = False

        self.unlock()

    def lock(
        self,
        reason
    ):

        self.state["safety"][
            "locked"
        ] = True

        self.state["safety"][
            "lock_reason"
        ] = str(reason)

        self.save()

    def unlock(self):

        self.state["safety"][
            "locked"
        ] = False

        self.state["safety"][
            "lock_reason"
        ] = None

        self.save()

    # =====================================================
    # GET STATE
    # =====================================================
    def get_state(self):

        return self.state
