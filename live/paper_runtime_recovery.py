import json
import os
import sys
import time
import websocket
from dataclasses import dataclass
from datetime import datetime, timezone


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from market.candle import Candle
from strategy import EMAVolumeStrategy
from engine.candle_engine import CandleEngine
from models.signal import Signal
from live.rest_bootstrap import RestBootstrap
from journal.trade_journal import TradeJournal
from state.state_manager import StateManager
from safety.safety_layer import SafetyLayer
from recovery.recovery_manager import RecoveryManager


WS_URL = "wss://ws.bitvavo.com/v2/"

MARKETS = [
    "SOL-USDC",
]

INTERVAL = "1h"
BOOTSTRAP_LIMIT = 400

INITIAL_BALANCE = 1000.0
RISK_PER_TRADE = 0.005

MAX_DAILY_LOSS_PCT = 2.0
STALE_CANDLE_SECONDS = 5400

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
STATE_PATH = os.path.join(PROJECT_ROOT, "state", "state.json")


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
            updates=1
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


class PaperRealtimeEngine(CandleEngine):
    """
    Realtime paper engine.

    Usa CandleEngine reale:
    - strategy reale
    - PaperExecution
    - position simulata
    - SL/TP simulati
    - trades[] simulati

    NON usa API write.
    """

    def __init__(
        self,
        strategy,
        market,
        journal,
        state_manager,
        safety_layer
    ):
        super().__init__(
            strategy=strategy,
            execution=None,
            initial_balance=INITIAL_BALANCE,
            risk_per_trade=RISK_PER_TRADE
        )

        self.market = market
        self.journal = journal
        self.state_manager = state_manager
        self.safety_layer = safety_layer

    def open_position(self, signal):
        candle = self.last_candle

        ok, reason = self.safety_layer.can_open_trade(
            candle=candle,
            engine=self,
            signal=signal
        )

        if not ok:
            self.journal.log_event(
                event_type="SAFETY_TRADE_BLOCKED",
                payload={
                    "market": self.market,
                    "timestamp": getattr(candle, "timestamp", None),
                    "reason": reason,
                    "signal_metadata": getattr(signal, "metadata", {})
                }
            )

            print("")
            print("=" * 80)
            print(f"[{utc_now()}] SAFETY BLOCKED TRADE")
            print(f"Market: {self.market}")
            print(f"Reason: {reason}")
            print("=" * 80)

            return

        position_before = self.position

        super().open_position(signal)

        if position_before is None and self.position is not None:
            pos = self.position

            self.safety_layer.register_open_position(pos)

            self.journal.log_signal(
                market=self.market,
                timestamp=getattr(pos, "entry_timestamp", None),
                signal=signal
            )

            self.journal.log_entry(
                market=self.market,
                timestamp=getattr(pos, "entry_timestamp", None),
                side=pos.side,
                price=pos.entry_price,
                size=pos.size,
                stop_loss=pos.stop_loss,
                take_profit=pos.take_profit,
                reason="PAPER_ENTRY",
                strategy=getattr(signal, "strategy", ""),
                metadata={
                    "signal_metadata": getattr(pos, "signal_metadata", {}),
                    "risk_per_trade": getattr(pos, "risk_per_trade", None),
                    "risk_amount": getattr(pos, "risk_amount", None),
                    "stop_distance": getattr(pos, "stop_distance", None),
                    "entry_fee": getattr(pos, "entry_fee", None),
                    "balance_before": self.balance
                }
            )

            self.journal.log_event(
                event_type="PAPER_ENTRY",
                payload={
                    "market": self.market,
                    "timestamp": getattr(pos, "entry_timestamp", None),
                    "side": pos.side,
                    "entry_price": pos.entry_price,
                    "size": pos.size,
                    "stop_loss": pos.stop_loss,
                    "take_profit": pos.take_profit
                }
            )

    def close_position(self, market_price, reason):
        trade_count_before = len(self.trades)

        super().close_position(market_price, reason)

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
                reason=f"PAPER_EXIT_{reason}",
                strategy="EMAVolumeStrategy",
                metadata={
                    "trade": trade,
                    "balance_after": self.balance
                }
            )

            self.journal.log_event(
                event_type="PAPER_EXIT",
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
                    "balance_after": self.balance
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

safety_layer = SafetyLayer(
    state_manager=state_manager,
    max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
    stale_candle_seconds=STALE_CANDLE_SECONDS
)

recovery_manager = RecoveryManager(
    state_manager=state_manager,
    journal=journal
)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def utc_today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def ensure_logs():
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(os.path.join(LOG_DIR, "journal"), exist_ok=True)


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
        f"[{utc_now()}] START HISTORICAL WARMUP "
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

    print(f"[{utc_now()}] WARMUP COMPLETE {market}")
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


def recover_engine_position(engine, market):
    restored = recovery_manager.restore_position(engine)

    if restored:
        print("")
        print("=" * 80)
        print(f"[{utc_now()}] RECOVERY POSITION RESTORED FOR {market}")
        print(f"Position: {engine.position}")
        print("=" * 80)

        if engine.last_candle is not None:
            ok, reason = recovery_manager.check_recovered_position_price(
                engine=engine,
                market_price=engine.last_candle.close
            )

            print("")
            print("=" * 80)
            print(f"[{utc_now()}] RECOVERY PRICE CHECK")
            print(f"Market: {market}")
            print(f"Result: {reason}")
            print("=" * 80)

    return restored


def get_engine(market):
    if market not in engines:
        strategy = EMAVolumeStrategy()

        engine = PaperRealtimeEngine(
            strategy=strategy,
            market=market,
            journal=journal,
            state_manager=state_manager,
            safety_layer=safety_layer
        )

        print("")
        print("=" * 80)
        print(f"[{utc_now()}] PAPER ENGINE CREATED FOR {market}")
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
    print(f"[{utc_now()}] INITIALIZING PAPER ENGINES BEFORE WEBSOCKET")
    print("=" * 80)

    for market in MARKETS:
        get_engine(market)

    print("")
    print("=" * 80)
    print(f"[{utc_now()}] ALL PAPER ENGINES WARMED UP")
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

    engine.on_candle(candle)

    after_count = len(engine.strategy.candles)
    after_trades = len(engine.trades)
    after_position = engine.position

    print("")
    print("=" * 80)
    print(f"[{utc_now()}] CLOSED CANDLE SENT TO PAPER ENGINE")
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
    print(f"[{utc_now()}] CONNECTED")

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

    print(f"[{utc_now()}] SUBSCRIBE")
    print(json.dumps(payload, indent=2))

    ws.send(json.dumps(payload))


def on_message(ws, message):
    try:
        data = json.loads(message)
    except Exception:
        print(f"[{utc_now()}] RAW MESSAGE")
        print(message)
        return

    if not isinstance(data, dict):
        print(f"[{utc_now()}] NON-DICT MESSAGE")
        print(data)
        return

    if data.get("event") != "candle":
        print(f"[{utc_now()}] CONTROL MESSAGE")
        print(json.dumps(data, indent=2))
        return

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
                f"[{utc_now()}] OPENED "
                f"{current.market} {current.interval} "
                f"ts={current.timestamp_ms} "
                f"C={current.close} V={current.volume} "
                f"updates={current.updates}"
            )

        elif event_type == "UPDATED":
            print(
                f"[{utc_now()}] UPDATED "
                f"{current.market} {current.interval} "
                f"ts={current.timestamp_ms} "
                f"C={current.close} V={current.volume} "
                f"updates={current.updates}"
            )

        elif event_type == "ROLLED":
            print(
                f"[{utc_now()}] ROLLED "
                f"{closed.market} old_ts={closed.timestamp_ms} "
                f"new_ts={current.timestamp_ms}"
            )

            process_closed_candle(closed)

            print(
                f"[{utc_now()}] OPENED "
                f"{current.market} {current.interval} "
                f"ts={current.timestamp_ms} "
                f"C={current.close} V={current.volume} "
                f"updates={current.updates}"
            )


def on_error(ws, error):
    print("")
    print("=" * 80)
    print(f"[{utc_now()}] ERROR")
    print(error)
    print("=" * 80)

    safety_layer.register_error(error)

    journal.log_event(
        event_type="PAPER_ERROR",
        payload={
            "error": str(error)
        }
    )


def on_close(ws, code, msg):
    print("")
    print("=" * 80)
    print(f"[{utc_now()}] CLOSED CONNECTION")
    print(code, msg)
    print("=" * 80)

    journal.log_event(
        event_type="PAPER_CONNECTION_CLOSED",
        payload={
            "code": code,
            "message": msg
        }
    )


def main():
    ensure_logs()
    state_manager.set_bot_running(True)

    initialize_engines()

    journal.log_event(
        event_type="PAPER_STARTED",
        payload={
            "markets": MARKETS,
            "interval": INTERVAL,
            "bootstrap_limit": BOOTSTRAP_LIMIT,
            "initial_balance": INITIAL_BALANCE,
            "risk_per_trade": RISK_PER_TRADE,
            "api_write": False,
            "state_path": STATE_PATH,
            "max_daily_loss_pct": MAX_DAILY_LOSS_PCT,
            "stale_candle_seconds": STALE_CANDLE_SECONDS,
            "recovery_enabled": True
        }
    )

    try:
        while True:
            print("")
            print("=" * 80)
            print(f"[{utc_now()}] STARTING REALTIME PAPER ENGINE")
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

            print(f"[{utc_now()}] RECONNECT IN 5s")
            time.sleep(5)

    except KeyboardInterrupt:
        state_manager.set_bot_running(False)

        journal.log_event(
            event_type="PAPER_STOPPED",
            payload={}
        )

        print("")
        print(f"[{utc_now()}] SHUTDOWN REQUESTED")
        print("Realtime paper engine stopped cleanly.")


if __name__ == "__main__":
    main()
