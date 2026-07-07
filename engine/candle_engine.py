from models.position import Position
from models.signal import Signal
from execution.paper_execution import PaperExecution


class CandleEngine:

    def __init__(
        self,
        strategy,
        execution=None,
        initial_balance=1000.0,
        risk_per_trade=0.005
    ):

        self.strategy = strategy

        # execution layer
        self.execution = execution if execution is not None else PaperExecution()

        # current active position
        self.position = None

        # account state
        self.balance = float(initial_balance)

        # risk management
        self.risk_per_trade = float(risk_per_trade)

        # trade history
        self.trades = []

        # latest candle
        self.last_candle = None

        # bootstrap / historical warmup mode
        # When True, strategy memory and indicators are updated,
        # but entries, exits and execution are disabled.
        self.is_warming_up = False

    # =========================
    # MAIN EVENT HANDLER
    # =========================
    def on_candle(self, candle):

        self.last_candle = candle

        # =========================
        # STRATEGY SIGNAL
        # =========================
        signal = self.strategy.on_candle(candle, self)

        # =========================
        # WARMUP GUARD
        # =========================
        if self.is_warming_up:
            return

        # =========================
        # ENTRY
        # =========================
        if (
            isinstance(signal, Signal)
            and self.position is None
        ):
            self.open_position(signal)

        # =========================
        # EXIT CHECK
        # =========================
        if self.position is not None:
            self.check_exit(candle)

    # =========================
    # OPEN POSITION
    # =========================
    def open_position(self, signal):

        market_price = float(signal.entry_price)

        # realistic execution price
        entry_price = self.execution.get_entry_price(
            market_price=market_price,
            side=signal.side
        )

        # fallback TP/SL if strategy does not provide them
        stop_loss = (
            float(signal.stop_loss)
            if signal.stop_loss is not None
            else entry_price * 0.995
        )

        take_profit = (
            float(signal.take_profit)
            if signal.take_profit is not None
            else entry_price * 1.01
        )

        # =========================
        # RISK-BASED POSITION SIZING
        # =========================
        risk_amount = self.balance * self.risk_per_trade
        stop_distance = abs(entry_price - stop_loss)

        if stop_distance <= 0:
            print("\n⚠️ INVALID STOP DISTANCE")
            print("Position not opened.")
            return

        size = risk_amount / stop_distance

        # safety cap: no accidental leverage
        max_size = self.balance / entry_price
        size = min(size, max_size)

        size = float(size)

        # entry fee
        entry_fee = self.execution.calculate_fee(
            price=entry_price,
            size=size
        )

        # create position object

        self.position = Position(
            side=signal.side,
            symbol=signal.symbol,
            entry_price=entry_price,
            size=size,

            stop_loss=round(
                float(stop_loss),
                2
            ),

            take_profit=round(
                float(take_profit),
                2
            )
        )

        # attach signal telemetry metadata
        self.position.signal_metadata = signal.metadata or {}

        # attach execution metadata
        self.position.entry_fee = float(entry_fee)
        self.position.risk_per_trade = float(self.risk_per_trade)
        self.position.risk_amount = float(risk_amount)
        self.position.stop_distance = float(stop_distance)

        # attach timing metadata
        self.position.entry_timestamp = getattr(
            self.last_candle,
            "timestamp",
            None
        )

        print("\n🟢 OPEN POSITION")
        print(self.position)
        print(f"Risk Per Trade: {self.risk_per_trade:.4%}")
        print(f"Risk Amount: {risk_amount:.4f}")
        print(f"Stop Distance: {stop_distance:.4f}")
        print(f"Size: {size:.6f}")
        print(f"Entry Fee: {entry_fee:.4f}")
        print(f"Entry Timestamp: {self.position.entry_timestamp}")

    # =========================
    # CHECK EXIT CONDITIONS
    # =========================
    def check_exit(self, candle):

        if self.position is None:
            return

        market_price = float(candle.close)
        pos = self.position

        # update unrealized pnl using market price
        pos.update_pnl(market_price)

        # =============================================
        # TAKE PROFIT
        # RUNTIME REALTIME-MANAGED
        # =============================================
        #
        # Take profit execution is handled
        # by realtime update-candle supervision
        # inside realtime_engine_live.py
        #
        # if (
        #     pos.take_profit is not None
        #     and market_price >= pos.take_profit
        # ):
        #     self.close_position(
        #         market_price,
        #         "TAKE PROFIT"
        #     )

        # =============================================
        # STOP LOSS
        # EXCHANGE-MANAGED
        # =============================================
        #
        # Runtime no longer executes stop loss exits.
        # Exchange stopLossLimit is authoritative.
        #
        # elif (
        #     pos.stop_loss is not None
        #     and market_price <= pos.stop_loss
        # ):
        #     self.close_position(
        #         market_price,
        #         "STOP LOSS"
        #     )

    # =========================
    # CLOSE POSITION
    # =========================
    def close_position(self, market_price, reason):

        pos = self.position

        if pos is None:
            return

        market_price = float(market_price)

        # realistic execution exit price
        exit_price = self.execution.get_exit_price(
            market_price=market_price,
            side=pos.side
        )

        # gross pnl before fees
        gross_pnl = (
            (exit_price - pos.entry_price)
            * pos.size
        )

        if pos.side == "SELL":
            gross_pnl = -gross_pnl

        # fees
        entry_fee = getattr(pos, "entry_fee", 0.0)

        exit_fee = self.execution.calculate_fee(
            price=exit_price,
            size=pos.size
        )

        net_pnl = gross_pnl - entry_fee - exit_fee

        # close position state
        pos.close(exit_price)

        # update balance
        self.balance = float(self.balance + net_pnl)

        # timing metadata
        entry_timestamp = getattr(pos, "entry_timestamp", None)
        exit_timestamp = getattr(
            self.last_candle,
            "timestamp",
            None
        )

        duration_seconds = None
        duration_hours = None

        if (
            entry_timestamp is not None
            and exit_timestamp is not None
        ):
            duration_seconds = float(exit_timestamp) - float(entry_timestamp)
            duration_hours = duration_seconds / 3600

        # save trade
        trade = {
            "symbol": pos.symbol,
            "side": pos.side,
            "entry": float(pos.entry_price),
            "exit": float(exit_price),
            "size": float(pos.size),
            "risk_per_trade": float(getattr(pos, "risk_per_trade", self.risk_per_trade)),
            "risk_amount": float(getattr(pos, "risk_amount", 0.0)),
            "stop_distance": float(getattr(pos, "stop_distance", 0.0)),
            "gross_pnl": float(gross_pnl),
            "entry_fee": float(entry_fee),
            "exit_fee": float(exit_fee),
            "fees": float(entry_fee + exit_fee),
            "pnl": float(net_pnl),
            "reason": str(reason),
            "entry_timestamp": entry_timestamp,
            "exit_timestamp": exit_timestamp,
            "duration_seconds": duration_seconds,
            "duration_hours": duration_hours,
            "signal_metadata": getattr(pos, "signal_metadata", {})
        }

        self.trades.append(trade)

        print("\n🔴 CLOSE POSITION")
        print(trade)

        # clear active position
        self.position = None
