import json
import os
import sys
import time
import threading
import subprocess
import websocket
from dataclasses import dataclass
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from models.position import Position
from market.candle import Candle
from strategy import EMAVolumeStrategy
from engine.candle_engine import CandleEngine
from models.signal import Signal
from live.rest_bootstrap import RestBootstrap
from journal.trade_journal import TradeJournal
from state.state_manager import StateManager
from safety.safety_layer import SafetyLayer
from state.recovery_manager import RecoveryManager
from execution.live_execution import LiveExecution
from exchange.bitvavo_api import BitvavoAPI

WS_URL = "wss://ws.bitvavo.com/v2/"

MARKETS = [
    "SOL-USDC",
]

INTERVAL = "1h"
BOOTSTRAP_LIMIT = 800

LIVE_INITIAL_BALANCE = 50.0
RISK_PER_TRADE = 0.01
MAX_LIVE_NOTIONAL_USDC = 50.0
API_WRITE = True

MAX_DAILY_LOSS_PCT = 2.0
STALE_CANDLE_SECONDS = 5400

WS_CANDLE_STALE_SECONDS = 45 * 60
WS_WATCHDOG_CHECK_SECONDS = 60

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
ACTIVITY_LOG_DIR = os.path.join(LOG_DIR, "activity")
ACTIVITY_LOG_PATH = os.path.join(ACTIVITY_LOG_DIR, "activity.log")

STATE_PATH = os.path.join(PROJECT_ROOT, "state", "state.json")
PREFLIGHT_PATH = os.path.join(PROJECT_ROOT, "live", "live_preflight.py")
RECONCILIATION_REPORT_PATH = os.path.join(
    PROJECT_ROOT,
    "state",
    "reconciliation_report.json"
)


class Tee:
    def __init__(self, stream, log_path):
        self.stream = stream
        self.log_file = open(log_path, "a", encoding="utf-8", buffering=1)

    def write(self, data):
        self.stream.write(data)
        self.log_file.write(data)

    def flush(self):
        self.stream.flush()
        self.log_file.flush()


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def utc_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def setup_activity_log(reset=True):
    os.makedirs(ACTIVITY_LOG_DIR, exist_ok=True)

    if reset and os.path.exists(ACTIVITY_LOG_PATH):
        os.remove(ACTIVITY_LOG_PATH)

    sys.stdout = Tee(sys.__stdout__, ACTIVITY_LOG_PATH)
    sys.stderr = Tee(sys.__stderr__, ACTIVITY_LOG_PATH)

    print("")
    print("=" * 80)
    print(f"[{utc_now()}] LIVE ACTIVITY LOG STARTED")
    print(f"Path: {ACTIVITY_LOG_PATH}")
    print("=" * 80)


def run_live_preflight_or_raise():
    print("")
    print("=" * 80)
    print(f"[{utc_now()}] RUNNING MANDATORY LIVE PREFLIGHT")
    print("=" * 80)

    result = subprocess.run(
        [sys.executable, PREFLIGHT_PATH],
        cwd=PROJECT_ROOT
    )


    if not os.path.exists(
        RECONCILIATION_REPORT_PATH
    ):

        raise RuntimeError(
            "LIVE_PREFLIGHT_FAILED_NO_REPORT"
        )

    with open(RECONCILIATION_REPORT_PATH, "r", encoding="utf-8") as f:
        report = json.load(f)

    if report.get("status") != "RECONCILIATION_OK":

        recovery_policy = (
            recovery_manager.determine_recovery_policy(
                report
            )
        )

        recovery_result = (
            recovery_manager.apply_recovery_policy(
                recovery_policy,
                report
            )
        )

        runtime_action = (
            recovery_policy.get(
                "runtime_action"
            )
        )

        if runtime_action != "CLEAR_LOCAL_POSITION":

            raise RuntimeError(
                f"RECONCILIATION_NOT_OK: {report}"
            )

        print(
            f"[{utc_now()}] "
            f"RECOVERY POLICY APPLIED => {runtime_action}"
        )

    print("")
    print("=" * 80)
    print(f"[{utc_now()}] LIVE PREFLIGHT PASSED")
    print("=" * 80)

    return report


@dataclass
class BuiltCandle:
    market: str
    interval: str
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    updates: int


class CandleBuilder:
    def __init__(self):
        self.current = {}

    def process(self, market, interval, row):
        timestamp_ms = int(row[0])

        incoming = BuiltCandle(
            market=market,
            interval=interval,
            timestamp_ms=timestamp_ms,
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            updates=0
        )

        key = (market, interval)

        if key not in self.current:
            self.current[key] = incoming
            return "OPENED", incoming, None

        current = self.current[key]

        if incoming.timestamp_ms == current.timestamp_ms:
            incoming.updates = current.updates + 1
            self.current[key] = incoming
            return "UPDATED", incoming, None

        closed = current
        self.current[key] = incoming

        return "ROLLED", incoming, closed


class LiveRealtimeEngine(CandleEngine):
    def __init__(
        self,
        strategy,
        market,
        journal,
        state_manager,
        safety_layer
    ):
        live_execution = LiveExecution(
            market=market,
            api_write=API_WRITE,
            max_notional_usdc=MAX_LIVE_NOTIONAL_USDC
        )

        super().__init__(
            strategy=strategy,
            execution=live_execution,
            initial_balance=LIVE_INITIAL_BALANCE,
            risk_per_trade=RISK_PER_TRADE
        )

        self.market = market
        self.journal = journal
        self.state_manager = state_manager
        self.safety_layer = safety_layer
        self.live_execution = live_execution

        self.exchange = BitvavoAPI()

    def assert_live_order_allowed(self):
        report = run_live_preflight_or_raise()

        if not report.get("can_trade", False):
            raise RuntimeError(f"RECONCILIATION_CAN_TRADE_FALSE: {report}")

        if self.market != "SOL-USDC":
            raise RuntimeError("LIVE_BLOCKED_MARKET_NOT_ALLOWED")

        return report

    # =========================================================
    # EXCHANGE BALANCE RECONCILIATION
    # =========================================================

    def reconcile_exchange_balance(self):
        try:
            api = BitvavoAPI()

            balances = api.get_balances()

            usdc_available = None

            if "USDC" not in balances:
                raise RuntimeError(
                    "USDC balance not found"
                )

            usdc_available = float(
                balances["USDC"]["available"]
            )


            if usdc_available is None:
                raise RuntimeError(
                    "USDC balance not found"
                )

            old_balance = float(self.balance)

            self.balance = float(usdc_available)

            print("")
            print("=" * 80)
            print(f"[{utc_now()}] EXCHANGE BALANCE RECONCILED")
            print(f"Old local balance: {old_balance}")
            print(f"Exchange balance: {self.balance}")
            print("=" * 80)

            self.journal.log_event(
                event_type="EXCHANGE_BALANCE_RECONCILED",
                payload={
                    "market": self.market,
                    "old_local_balance": old_balance,
                    "exchange_balance": self.balance
                }
            )

            return self.balance

        except Exception as exc:

            pos.pending_action = (
                "NONE"
            )

            print("")
            print("=" * 80)
            print(f"[{utc_now()}] EXCHANGE BALANCE RECONCILIATION FAILED")
            print(exc)
            print("=" * 80)

            self.journal.log_event(
                event_type="EXCHANGE_BALANCE_RECONCILIATION_FAILED",
                payload={
                    "market": self.market,
                    "error": str(exc)
                }
            )

            return self.balance



    def open_position(self, signal):
        candle = self.last_candle

        ok, reason = self.safety_layer.can_open_trade(
            candle=candle,
            engine=self,
            signal=signal
        )

        if not ok:
            self.journal.log_event(
                event_type="LIVE_SAFETY_TRADE_BLOCKED",
                payload={
                    "market": self.market,
                    "timestamp": getattr(candle, "timestamp", None),
                    "reason": reason,
                    "signal_metadata": getattr(signal, "metadata", {})
                }
            )

            print("")
            print("=" * 80)
            print(f"[{utc_now()}] LIVE SAFETY BLOCKED TRADE")
            print(f"Market: {self.market}")
            print(f"Reason: {reason}")
            print("=" * 80)

            return

        try:
            self.assert_live_order_allowed()
        except Exception as exc:
            self.journal.log_event(
                event_type="LIVE_RECONCILIATION_BLOCKED_ENTRY",
                payload={
                    "market": self.market,
                    "error": str(exc),
                    "signal_metadata": getattr(signal, "metadata", {})
                }
            )

            print("")
            print("=" * 80)
            print(f"[{utc_now()}] LIVE ENTRY BLOCKED BY PREFLIGHT/RECONCILIATION")
            print(exc)
            print("=" * 80)

            return

        if self.position is not None:

            print("")
            print("=" * 80)
            print(f"[{utc_now()}] LIVE ENTRY BLOCKED")
            print("Runtime already has an open position.")
            print("=" * 80)

            return

        # =========================================================
        # CREATE SYNTHETIC POSITION LOCALLY
        # BEFORE EXCHANGE EXECUTION
        # =========================================================

        super().open_position(signal)

        if self.position is None:

            print("")
            print("=" * 80)
            print(f"[{utc_now()}] LIVE ENTRY FAILED")
            print("super().open_position(signal) returned no position.")
            print("=" * 80)

            return

        pos = self.position

        notional = float(pos.entry_price) * float(pos.size)

        if notional > MAX_LIVE_NOTIONAL_USDC:
            print("")
            print("=" * 80)
            print(f"[{utc_now()}] LIVE ENTRY SIZE CAPPED")
            print(f"Original notional: {notional}")
            print(f"Cap: {MAX_LIVE_NOTIONAL_USDC}")
            print("=" * 80)

            pos.size = (
                float(MAX_LIVE_NOTIONAL_USDC)
                / float(pos.entry_price)
            )

            notional = (
                float(pos.entry_price)
                * float(pos.size)
            )

        notional = round(
            notional,
            2
        )

        try:
            order_response = (
                self.live_execution.place_market_buy_quote(
                    amount_quote_usdc=notional
                )
            )

            try:
                order_response_data = order_response.json()

            except Exception:
                order_response_data = {
                    "raw_response": str(order_response)
                }

            fills = order_response_data.get(
                "fills",
                []
            )

            if len(fills) <= 0:
                raise RuntimeError("NO_EXCHANGE_FILLS")

            first_fill = fills[0]

            filled_size = float(
                order_response_data.get(
                    "filledAmount",
                    0.0
                )
            )

            if filled_size <= 0:
                raise RuntimeError("INVALID_FILLED_SIZE")

            pos.size = filled_size
            pos.filled_size = filled_size

            pos.entry_order_id = (
                order_response_data.get(
                    "orderId"
                )
            )

            pos.entry_exchange_status = (
                order_response_data.get(
                    "status"
                )
            )

            pos.avg_fill_price = float(
                first_fill.get(
                    "price",
                    pos.entry_price
                )
            )

            pos.entry_price = pos.avg_fill_price

            state_manager.save_open_position(
                pos
            )

            pos.entry_filled_utc = utc_now()

            print("")
            print("=" * 80)
            print(
                f"[{utc_now()}] "
                f"LIVE POSITION SYNCHRONIZED WITH EXCHANGE"
            )
            print(f"Exchange filled size: {filled_size}")
            print(f"Runtime position size updated: {pos.size}")
            print("=" * 80)

            self.reconcile_exchange_balance()

            # =====================================================
            # PLACE EXCHANGE STOP LOSS LIMIT
            # =====================================================


            sl_trigger = round(
                float(pos.stop_loss),
                2
            )

            sl_limit = round(
                sl_trigger * 0.999,
                2
            )

            stop_loss_response = (
                self.exchange.place_stop_loss_limit(

                    market=self.market,

                    side="sell",

                    amount=pos.size,

                    trigger_price=sl_trigger,

                    limit_price=sl_limit
                )
            )

            pos.stop_loss_order_id = (
                stop_loss_response.get(
                    "orderId"
                )
            )

            pos.stop_loss_exchange_status = (
                stop_loss_response.get(
                    "status"
                )
            )

            pos.stop_loss_trigger_reference = (
                "lastTrade"
            )

            pos.is_protected = True

            pos.protection_level = (
                "EXCHANGE_STOPLOSS"
            )

            pos.stop_loss_verified = True

            pos.protection_last_verified_utc = (
                utc_now()
            )

            pos.last_exchange_sync_utc = (
                utc_now()
            )

            pos.exchange_sync_status = (
                "SYNCED"
            )

            pos.last_confirmed_exchange_position_qty = (
                pos.size
            )

            pos.last_confirmed_exchange_sync_utc = (
                utc_now()
            )

            print("")
            print("=" * 80)
            print(
                f"[{utc_now()}] "
                f"EXCHANGE STOP LOSS PLACED"
            )
            print(
                f"Trigger: {pos.stop_loss}"
            )
            print(
                f"Order ID: "
                f"{pos.stop_loss_order_id}"
            )
            print("=" * 80)


        except Exception as exc:

            self.journal.log_event(
                event_type="LIVE_ENTRY_ORDER_FAILED",
                payload={
                    "market": self.market,
                    "error": str(exc),
                    "notional": notional,
                    "position": {
                        "side": pos.side,
                        "symbol": pos.symbol,
                        "entry_price": pos.entry_price,
                        "size": pos.size,
                        "stop_loss": pos.stop_loss,
                        "take_profit": pos.take_profit
                    }
                }
            )

            print("")
            print("=" * 80)
            print(f"[{utc_now()}] LIVE ENTRY ORDER FAILED")
            print(exc)
            print(
                "Local position cleared because "
                "exchange order failed."
            )
            print("=" * 80)

            self.position = None
            return

        self.safety_layer.register_open_position(pos)

        self.journal.log_signal(
            market=self.market,
            timestamp=getattr(
                pos,
                "entry_timestamp",
                None
            ),
            signal=signal
        )

        self.journal.log_entry(
            market=self.market,
            timestamp=getattr(
                pos,
                "entry_timestamp",
                None
            ),
            side=pos.side,
            price=pos.entry_price,
            size=pos.size,
            stop_loss=pos.stop_loss,
            take_profit=pos.take_profit,
            reason="LIVE_ENTRY",
            strategy=getattr(signal, "strategy", ""),
            metadata={
                "signal_metadata": getattr(
                    pos,
                    "signal_metadata",
                    {}
                ),
                "risk_per_trade": getattr(
                    pos,
                    "risk_per_trade",
                    None
                ),
                "risk_amount": getattr(
                    pos,
                    "risk_amount",
                    None
                ),
                "stop_distance": getattr(
                    pos,
                    "stop_distance",
                    None
                ),
                "entry_fee": getattr(
                    pos,
                    "entry_fee",
                    None
                ),
                "balance_before": self.balance,
                "max_live_notional_usdc":
                    MAX_LIVE_NOTIONAL_USDC,
                "order_response":
                    order_response_data
            }
        )

        self.journal.log_event(
            event_type="LIVE_ENTRY",
            payload={
                "market": self.market,
                "timestamp": getattr(
                    pos,
                    "entry_timestamp",
                    None
                ),
                "side": pos.side,
                "entry_price": pos.entry_price,
                "size": pos.size,
                "notional_usdc": notional,
                "stop_loss": pos.stop_loss,
                "take_profit": pos.take_profit,
                "order_response":
                    order_response_data
            }
        )

    def close_position(self, market_price, reason):
        pos = self.position

        if pos is None:
            return

        try:
            self.assert_live_order_allowed()
        except Exception as exc:
            self.journal.log_event(
                event_type="LIVE_RECONCILIATION_BLOCKED_EXIT",
                payload={
                    "market": self.market,
                    "reason": reason,
                    "error": str(exc)
                }
            )

            print("")
            print("=" * 80)
            print(f"[{utc_now()}] LIVE EXIT BLOCKED BY PREFLIGHT/RECONCILIATION")
            print(exc)
            print("=" * 80)

            return

        try:

            # =========================================
            # CANCEL EXCHANGE STOP LOSS
            # BEFORE TP / MANUAL EXIT
            # =========================================

            if pos.stop_loss_order_id is not None:

                print("")
                print("=" * 80)
                print(
                    f"[{utc_now()}] "
                    f"CANCELING EXCHANGE STOP LOSS"
                )
                print(
                    f"Order ID: "
                    f"{pos.stop_loss_order_id}"
                )
                print("=" * 80)

                cancel_response = (
                    self.exchange.cancel_order(

                        market=self.market,

                        order_id=(
                            pos.stop_loss_order_id
                        )
                    )
                )

                if (
                    cancel_response is None
                    or cancel_response.get(
                        "error"
                    ) is not None
                ):

                    raise RuntimeError(
                        f"FAILED_TO_CANCEL_STOP_LOSS: "
                        f"{cancel_response}"
                    )

                print("")
                print("=" * 80)
                print(
                    f"[{utc_now()}] "
                    f"EXCHANGE STOP LOSS CANCELED"
                )
                print(cancel_response)
                print("=" * 80)

                pos.stop_loss_order_id = None

                pos.stop_loss_exchange_status = (
                    "canceled"
                )

                pos.stop_loss_verified = False

                pos.is_protected = False

                pos.protection_level = (
                    "NONE"
                )

                pos.protection_last_verified_utc = (
                    utc_now()
                )

            sell_size = (


                pos.filled_size
                if pos.filled_size is not None
                else pos.size
            )

            order_response = self.live_execution.place_market_sell_amount(
                amount_sol=sell_size
            )

            if (
                order_response.status_code < 200
                or order_response.status_code >= 300
            ):

                print("")
                print("=" * 80)
                print(f"[{utc_now()}] LIVE SELL FAILED")
                print(f"HTTP STATUS => {order_response.status_code}")
                print(order_response.text)
                print("POSITION WILL REMAIN OPEN")
                print("=" * 80)

                self.journal.log_event(
                    event_type="LIVE_EXIT_ORDER_REJECTED",
                    payload={
                        "market": self.market,
                        "reason": reason,
                        "status_code": order_response.status_code,
                        "response": order_response.text,
                        "position_size": pos.size
                    }
                )

                pos.pending_action = (
                    "NONE"
                )

                return

        except Exception as exc:

            self.journal.log_event(
                event_type="LIVE_EXIT_ORDER_FAILED",
                payload={
                    "market": self.market,
                    "reason": reason,
                    "error": str(exc),
                    "position": {
                        "side": pos.side,
                        "symbol": pos.symbol,
                        "entry_price": pos.entry_price,
                        "size": pos.size,
                        "stop_loss": pos.stop_loss,
                        "take_profit": pos.take_profit
                    }
                }
            )

            print("")
            print("=" * 80)
            print(f"[{utc_now()}] LIVE EXIT ORDER FAILED")
            print(exc)
            print("Local position kept open because exchange sell failed.")
            print("=" * 80)

            return

        trade_count_before = len(self.trades)

        super().close_position(market_price, reason)

        pos.pending_action = "NONE"

        state_manager.transition_position_state(
            runtime_state="POSITION_OPEN",
            pending_action="NONE"
        )

        self.reconcile_exchange_balance()

        if len(self.trades) > trade_count_before:
            trade = self.trades[-1]

            trade_id = (
                f"{trade.get('symbol')}_"
                f"{trade.get('entry_timestamp')}_"
                f"{trade.get('exit_timestamp')}"
            )

            self.safety_layer.register_closed_position(
                trade_id=trade_id
            )

            update_daily_state_from_engine(self)

            self.journal.log_exit(
                market=self.market,
                timestamp=trade.get("exit_timestamp"),
                side=trade.get("side"),
                price=trade.get("exit"),
                size=trade.get("size"),
                pnl=trade.get("pnl"),
                reason=f"LIVE_EXIT_{reason}",
                strategy="EMAVolumeStrategy",
                metadata={
                    "trade": trade,
                    "balance_after": self.balance,
                    "order_response": order_response
                }
            )

            self.journal.log_event(
                event_type="LIVE_EXIT",
                payload={
                    "market": self.market,
                    "reason": reason,
                    "entry_timestamp": trade.get("entry_timestamp"),
                    "exit_timestamp": trade.get("exit_timestamp"),
                    "entry": trade.get("entry"),
                    "exit": trade.get("exit"),
                    "size": trade.get("size"),
                    "gross_pnl": trade.get("gross_pnl"),
                    "fees": trade.get("fees"),
                    "net_pnl": trade.get("pnl"),
                    "balance_after": self.balance,
                    "order_response": order_response
                }
            )


builder = CandleBuilder()
engines = {}

journal = TradeJournal(
    base_dir=os.path.join(LOG_DIR, "journal")
)

state_manager = StateManager(
    state_path=STATE_PATH
)

state_manager.set_bot_mode("LIVE", True)

safety_layer = SafetyLayer(
    state_manager=state_manager,
    max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    stale_candle_seconds=STALE_CANDLE_SECONDS
)

recovery_manager = RecoveryManager(
    state_manager=state_manager
)

runtime_lock = threading.Lock()
current_ws = None
last_candle_event_at = None
last_candle_event_label = None
watchdog_started = False


def mark_candle_stream_alive(label):
    global last_candle_event_at
    global last_candle_event_label

    with runtime_lock:
        last_candle_event_at = time.time()
        last_candle_event_label = str(label)


def register_current_ws(ws):
    global current_ws

    with runtime_lock:
        current_ws = ws

    mark_candle_stream_alive("CONNECTED_GRACE")


def clear_current_ws(ws):
    global current_ws

    with runtime_lock:
        if current_ws is ws:
            current_ws = None


def websocket_candle_watchdog():
    while True:
        time.sleep(WS_WATCHDOG_CHECK_SECONDS)

        ws_to_close = None
        age_seconds = None
        label = None

        with runtime_lock:
            if current_ws is not None and last_candle_event_at is not None:
                age_seconds = time.time() - float(last_candle_event_at)
                label = last_candle_event_label

                if age_seconds >= WS_CANDLE_STALE_SECONDS:
                    ws_to_close = current_ws
                    globals()["last_candle_event_at"] = time.time()
                    globals()["last_candle_event_label"] = "STALE_CLOSE_REQUESTED"

        if ws_to_close is not None:
            print("")
            print("=" * 80)
            print(f"[{utc_now()}] LIVE STALE_CANDLE_STREAM")
            print(f"No candle payload received for {age_seconds:.0f} seconds")
            print(f"Last candle marker: {label}")
            print("Closing websocket to force clean reconnect...")
            print("=" * 80)

            journal.log_event(
                event_type="LIVE_STALE_CANDLE_STREAM",
                payload={
                    "age_seconds": float(age_seconds),
                    "threshold_seconds": WS_CANDLE_STALE_SECONDS,
                    "last_marker": label,
                    "action": "ws.close"
                }
            )

            try:
                ws_to_close.close()
            except Exception as exc:

                print("")
                print("=" * 80)
                print(f"[{utc_now()}] LIVE_STALE_CANDLE_STREAM_CLOSE_ERROR")
                print(exc)
                print("=" * 80)

                journal.log_event(
                    event_type="LIVE_STALE_CANDLE_STREAM_CLOSE_ERROR",
                    payload={
                        "error": str(exc)
                    }
                )


def start_websocket_watchdog():
    global watchdog_started

    if watchdog_started:
        return

    watchdog_started = True

    thread = threading.Thread(
        target=websocket_candle_watchdog,
        name="websocket_candle_watchdog",
        daemon=True
    )
    thread.start()

    print("")
    print("=" * 80)
    print(f"[{utc_now()}] LIVE WEBSOCKET CANDLE WATCHDOG STARTED")
    print(f"Threshold seconds: {WS_CANDLE_STALE_SECONDS}")
    print(f"Check interval seconds: {WS_WATCHDOG_CHECK_SECONDS}")
    print("=" * 80)


def ensure_logs():
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(os.path.join(LOG_DIR, "journal"), exist_ok=True)
    os.makedirs(ACTIVITY_LOG_DIR, exist_ok=True)


def ensure_daily_state(engine):
    state = state_manager.get_state()
    daily = state.get("daily", {})
    today = utc_today()

    if daily.get("date") != today:
        state_manager.update_daily_state(
            date=today,
            start_balance=engine.balance,
            realized_pnl=0.0
        )


def update_daily_state_from_engine(engine):
    state = state_manager.get_state()
    daily = state.get("daily", {})
    today = utc_today()

    start_balance = daily.get("start_balance")

    if daily.get("date") != today or start_balance is None:
        start_balance = engine.balance

    realized_pnl = float(engine.balance) - float(start_balance)

    state_manager.update_daily_state(
        date=today,
        start_balance=start_balance,
        realized_pnl=realized_pnl
    )


def bootstrap_engine(engine, market):
    print("")
    print("=" * 80)
    print(
        f"[{utc_now()}] START LIVE HISTORICAL WARMUP "
        f"{market} ({BOOTSTRAP_LIMIT} candles)"
    )

    bootstrap = RestBootstrap(
        market=market,
        interval=INTERVAL,
        limit=BOOTSTRAP_LIMIT
    )

    result = bootstrap.warmup_engine(
        engine=engine,
        warmup_mode=True
    )

    print(f"[{utc_now()}] LIVE WARMUP COMPLETE {market}")
    print(json.dumps(result, indent=2))
    print(f"Strategy candles: {len(engine.strategy.candles)}")
    print(f"Strategy prices: {len(engine.strategy.prices)}")
    print(f"Engine position: {engine.position}")
    print(f"Engine trades: {len(engine.trades)}")
    print(f"Engine balance: {engine.balance}")
    print(f"Engine is_warming_up: {getattr(engine, 'is_warming_up', None)}")
    print("=" * 80)

    if result.get("loaded_candles") != BOOTSTRAP_LIMIT:
        raise RuntimeError(f"Bootstrap failed for {market}")

    if len(engine.strategy.candles) != BOOTSTRAP_LIMIT:
        raise RuntimeError(f"Strategy candle count mismatch for {market}")

    if len(engine.strategy.prices) != BOOTSTRAP_LIMIT:
        raise RuntimeError(f"Strategy price count mismatch for {market}")

    if engine.position is not None:
        raise RuntimeError(f"Unexpected open position after warmup for {market}")

    if len(engine.trades) != 0:
        raise RuntimeError(f"Unexpected historical trades after warmup for {market}")


def recover_engine_position(
    engine,
    market
):

    engine.reconcile_exchange_balance()

    try:

        raw_balances = (
            engine.execution
            .client
            .get_balance()
        )


        balances = raw_balances.json()

        sol_balance = 0.0

        usdc_balance = None

        for asset in balances:

            if asset.get("symbol") == "USDC":

                usdc_balance = float(
                    asset.get(
                        "available",
                        0.0
                    )
                )

            if asset.get("symbol") == "SOL":

                available = float(
                    asset.get(
                        "available",
                        0.0
                    )
                )

                in_order = float(
                    asset.get(
                        "inOrder",
                        0.0
                    )
                )

                sol_balance = (
                    available + in_order
                )

        if sol_balance <= 0.00001:

            print("")
            print("=" * 80)
            print(
                f"[{utc_now()}] "
                f"NO EXCHANGE POSITION FOUND"
            )
            print(
                "SOL balance is zero "
                "-> skipping recovery"
            )
            print("=" * 80)

            engine.position = None

            if usdc_balance is not None:
                engine.balance = usdc_balance

            state_manager.clear_position()
            return

    except Exception as e:

        print("")
        print("=" * 80)
        print(
            f"[{utc_now()}] "
            f"RECOVERY RECONCILIATION ERROR"
        )
        print(str(e))
        print("=" * 80)

    position_state = (
        state_manager.state.get(
            "position",
            {}
        )
    )

    if not position_state.get("is_open"):
        return

    if (
        position_state.get("symbol")
        != market
    ):
        return

    recovered_position = Position(

        side=position_state.get(
            "side",
            "BUY"
        ),

        symbol=market,

        entry_price=(
            position_state.get(
                "entry_price"
            )
            or 0.0
        ),

        size=(
            position_state.get(
                "size"
            )
            or position_state.get(
                "filled_size"
            )
            or 0.0
        ),

        stop_loss=position_state.get(
            "stop_loss"
        ),

        take_profit=position_state.get(
            "take_profit"
        )
    )

    recovered_position.stop_loss_order_id = (
        position_state.get(
            "stop_loss_order_id"
        )
    )

    recovered_position.pending_action = (
        position_state.get(
            "pending_action",
            "NONE"
        )
    )

    engine.position = recovered_position

    print("")
    print("=" * 80)
    print(
        f"[{utc_now()}] "
        f"ENGINE POSITION RECOVERED"
    )
    print(recovered_position)
    print("=" * 80)

def get_engine(market):
    if market not in engines:
        strategy = EMAVolumeStrategy()

        engine = LiveRealtimeEngine(
            strategy=strategy,
            market=market,
            journal=journal,
            state_manager=state_manager,
            safety_layer=safety_layer
        )

        print("")
        print("=" * 80)
        print(f"[{utc_now()}] LIVE ENGINE CREATED FOR {market}")
        print(f"API_WRITE: {API_WRITE}")
        print(f"MAX_LIVE_NOTIONAL_USDC: {MAX_LIVE_NOTIONAL_USDC}")
        print("=" * 80)

        bootstrap_engine(
            engine=engine,
            market=market
        )

        recover_engine_position(
            engine=engine,
            market=market
        )

        ensure_daily_state(engine)

        engines[market] = engine

    return engines[market]


def initialize_engines():
    print("")
    print("=" * 80)
    print(f"[{utc_now()}] INITIALIZING LIVE ENGINES BEFORE WEBSOCKET")
    print("=" * 80)

    for market in MARKETS:
        get_engine(market)

    print("")
    print("=" * 80)
    print(f"[{utc_now()}] ALL LIVE ENGINES WARMED UP")
    print("=" * 80)

    for market in MARKETS:
        engine = engines[market]
        print(
            f"{market} | "
            f"candles={len(engine.strategy.candles)} | "
            f"prices={len(engine.strategy.prices)} | "
            f"position={engine.position} | "
            f"trades={len(engine.trades)} | "
            f"balance={engine.balance}"
        )


def built_to_market_candle(built):
    return Candle(
        timestamp=float(built.timestamp_ms) / 1000.0,
        open=float(built.open),
        high=float(built.high),
        low=float(built.low),
        close=float(built.close),
        volume=float(built.volume),
        symbol=str(built.market)
    )


def process_closed_candle(closed):
    engine = get_engine(closed.market)
    candle = built_to_market_candle(closed)

    engine.safety_layer.register_candle(candle)
    ensure_daily_state(engine)

    before_count = len(engine.strategy.candles)
    before_trades = len(engine.trades)
    before_position = engine.position

    # =========================================================
    # EXCHANGE BALANCE REFRESH
    # =========================================================

    try:

        raw_balances = (
            engine.execution
            .client
            .get_balance()
        )

        balances = raw_balances.json()

        for asset in balances:

            if asset.get("symbol") == "USDC":

                available = float(
                    asset.get(
                        "available",
                        0.0
                    )
                )

                in_order = float(
                    asset.get(
                        "inOrder",
                        0.0
                    )
                )

                engine.balance = (
                    available + in_order
                )

                print(
                    f"[{utc_now()}] "
                    f"BALANCE REFRESH "
                    f"USDC={engine.balance}"
                )

                break

    except Exception as e:

        print(
            f"[{utc_now()}] "
            f"BALANCE REFRESH ERROR: {e}"
        )

    engine.on_candle(candle)

    after_count = len(engine.strategy.candles)
    after_trades = len(engine.trades)
    after_position = engine.position

    print("")
    print("=" * 80)
    print(f"[{utc_now()}] CLOSED CANDLE SENT TO LIVE ENGINE")
    print(
        f"{closed.market} {closed.interval} "
        f"ts={closed.timestamp_ms} "
        f"O={closed.open} H={closed.high} "
        f"L={closed.low} C={closed.close} "
        f"V={closed.volume} updates={closed.updates}"
    )
    print(f"Strategy candles: {before_count} -> {after_count}")
    print(f"Position before: {before_position}")
    print(f"Position after: {after_position}")
    print(f"Trades: {before_trades} -> {after_trades}")
    print(f"Balance: {engine.balance}")
    print("=" * 80)


def on_open(ws):
    register_current_ws(ws)

    print(f"[{utc_now()}] LIVE CONNECTED")

    payload = {
        "action": "subscribe",
        "channels": [
            {
                "name": "candles",
                "markets": MARKETS,
                "interval": [INTERVAL]
            }
        ]
    }

    print(f"[{utc_now()}] LIVE SUBSCRIBE")
    print(json.dumps(payload, indent=2))

    ws.send(json.dumps(payload))


def on_message(ws, message):
    try:
        data = json.loads(message)
    except Exception:
        print(f"[{utc_now()}] LIVE RAW MESSAGE")
        print(message)
        return

    if not isinstance(data, dict):
        print(f"[{utc_now()}] LIVE NON-DICT MESSAGE")
        print(data)
        return

    if data.get("event") != "candle":
        print(f"[{utc_now()}] LIVE CONTROL MESSAGE")
        print(json.dumps(data, indent=2))
        return

    mark_candle_stream_alive("CANDLE_PAYLOAD")

    market = data.get("market")
    interval = data.get("interval")
    candles = data.get("candle", [])

    for row in candles:
        event_type, current, closed = builder.process(
            market=market,
            interval=interval,
            row=row
        )

        if event_type == "OPENED":
            print(
                f"[{utc_now()}] LIVE OPENED "
                f"{current.market} {current.interval} "
                f"ts={current.timestamp_ms} "
                f"C={current.close} V={current.volume} "
                f"updates={current.updates}"
            )

        elif event_type == "UPDATED":
            print(
                f"[{utc_now()}] LIVE UPDATED "
                f"{current.market} {current.interval} "
                f"ts={current.timestamp_ms} "
                f"C={current.close} V={current.volume} "
                f"updates={current.updates}"
            )

            # =====================================
            # REALTIME TAKE PROFIT CHECK
            # =====================================

            engine = engines.get(market)

            # =====================================
            # REALTIME TAKE PROFIT CHECK
            # =====================================

            engine = engines.get(market)

            # =====================================
            # EXCHANGE POSITION RECONCILIATION
            # =====================================

            if (
                engine is not None
                and engine.position is not None
                and engine.position.is_open
            ):

                try:

                    raw_balances = (
                        engine.execution
                        .client
                        .get_balance()
                    )

                    balances = raw_balances.json()

                    sol_balance = 0.0

                    for asset in balances:

                        if asset.get("symbol") == "SOL":

                            available = float(
                                asset.get(
                                    "available",
                                    0.0
                                )
                            )

                            in_order = float(
                                asset.get(
                                    "inOrder",
                                    0.0
                                )
                            )

                            sol_balance = (
                                available + in_order
                            )

                            break

                    if sol_balance <= 0.00001:

                        print("")
                        print("=" * 80)
                        print(
                            f"[{utc_now()}] "
                            f"EXCHANGE POSITION CLOSED DETECTED"
                        )
                        print(
                            "SOL balance is zero "
                            "-> closing local runtime position"
                        )
                        print("=" * 80)

                        engine.position = None

                        state_manager.clear_position()

                except Exception as e:

                    print("")
                    print("=" * 80)
                    print(
                        f"[{utc_now()}] "
                        f"EXCHANGE RECONCILIATION ERROR"
                    )
                    print(str(e))
                    print("=" * 80)

            if (
                engine is not None
                and engine.position is not None
            ):

                pos = engine.position

                market_price = float(
                    current.close
                )


                if (
                    pos.take_profit is not None
                    and market_price >= pos.take_profit
                    and pos.pending_action != "EXITING"
                ):

                    pos.pending_action = (
                        "EXITING"
                    )

                    state_manager.transition_position_state(
                        runtime_state="POSITION_OPEN",
                        pending_action="EXITING"
                    )

                    print("")
                    print("=" * 80)
                    print(
                        f"[{utc_now()}] "
                        f"REALTIME TAKE PROFIT TRIGGERED"
                    )
                    print(
                        f"Market Price: "
                        f"{market_price}"
                    )
                    print(
                        f"Take Profit: "
                        f"{pos.take_profit}"
                    )

                    print("=" * 80)

                    sl_order_id = getattr(
                        pos,
                        "stop_loss_order_id",
                        None,
                    )

                    if sl_order_id is not None:

                        print(
                            f"[{utc_now()}] "
                            f"Cancelling SL order: "
                            f"{sl_order_id}"
                        )

                        try:

                            engine.execution.cancel_order(
                                sl_order_id
                            )

                            print(
                                f"[{utc_now()}] "
                                f"SL order cancelled."
                            )

                        except Exception as e:

                            print(
                                f"[{utc_now()}] "
                                f"SL cancel failed: {e}"
                            )

                    engine.close_position(
                        market_price,
                        "TAKE PROFIT"
                    )


        elif event_type == "ROLLED":
            print(
                f"[{utc_now()}] LIVE ROLLED "
                f"{closed.market} old_ts={closed.timestamp_ms} "
                f"new_ts={current.timestamp_ms}"
            )

            process_closed_candle(closed)

            print(
                f"[{utc_now()}] LIVE OPENED "
                f"{current.market} {current.interval} "
                f"ts={current.timestamp_ms} "
                f"C={current.close} V={current.volume} "
                f"updates={current.updates}"
            )


def on_error(ws, error):

    error_str = str(error)

    if "opcode=8" in error_str and "b'\\x03\\xe8'" in error_str:
        print("")
        print("=" * 80)
        print(f"[{utc_now()}] LIVE WS CLOSED NORMAL")
        print(error)
        print("=" * 80)
        return

    print("")
    print("=" * 80)
    print(f"[{utc_now()}] LIVE ERROR")
    print(error)
    print("=" * 80)

    safety_layer.register_error(error)

    journal.log_event(
        event_type="LIVE_ERROR",
        payload={
            "error": error_str
        }
    )

def on_close(ws, code, msg):
    clear_current_ws(ws)

    print("")
    print("=" * 80)
    print(f"[{utc_now()}] LIVE CLOSED CONNECTION")
    print(code, msg)
    print("=" * 80)

    journal.log_event(
        event_type="LIVE_CONNECTION_CLOSED",
        payload={
            "code": code,
            "message": msg
        }
    )


def main():
    ensure_logs()
    setup_activity_log(reset=True)
    start_websocket_watchdog()

    run_live_preflight_or_raise()

    state_manager.load()

    state_manager.set_bot_running(True)

    state_manager.state["runtime"][
        "max_live_notional_usdc"
    ] = MAX_LIVE_NOTIONAL_USDC

    state_manager.save()

    initialize_engines()

    journal.log_event(
        event_type="LIVE_STARTED",
        payload={
            "markets": MARKETS,
            "interval": INTERVAL,
            "bootstrap_limit": BOOTSTRAP_LIMIT,
            "live_initial_balance": LIVE_INITIAL_BALANCE,
            "risk_per_trade": RISK_PER_TRADE,
            "api_write": API_WRITE,
            "max_live_notional_usdc": MAX_LIVE_NOTIONAL_USDC,
            "state_path": STATE_PATH,
            "max_daily_loss_pct": MAX_DAILY_LOSS_PCT,
            "stale_candle_seconds": STALE_CANDLE_SECONDS,
            "ws_candle_stale_seconds": WS_CANDLE_STALE_SECONDS,
            "ws_watchdog_check_seconds": WS_WATCHDOG_CHECK_SECONDS,
            "activity_log_path": ACTIVITY_LOG_PATH,
            "recovery_enabled": True,
            "preflight_required": True,
            "reconciliation_required": True
        }
    )

    try:
        while True:
            print("")
            print("=" * 80)
            print(f"[{utc_now()}] STARTING REALTIME LIVE ENGINE")
            print("=" * 80)

            ws = websocket.WebSocketApp(
                WS_URL,
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )

            ws.run_forever(
                ping_interval=30,
                ping_timeout=10
            )

            print(f"[{utc_now()}] LIVE RECONNECT IN 5s")
            time.sleep(5)

    except KeyboardInterrupt:
        state_manager.set_bot_running(False)

        journal.log_event(
            event_type="LIVE_STOPPED",
            payload={}
        )

        print("")
        print(f"[{utc_now()}] LIVE SHUTDOWN REQUESTED")
        print("Realtime live engine stopped cleanly.")


if __name__ == "__main__":
    main()
