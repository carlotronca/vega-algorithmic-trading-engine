import csv
import json
from datetime import datetime, timezone
from pathlib import Path


class TradeJournal:
    """
    Activity Observer / Trade Journal minimale.

    Registra SOLO eventi operativi rilevanti:
    - start probe/bot
    - bootstrap completed
    - segnali generati
    - entry simulate/reali
    - exit simulate/reali
    - errori/warning importanti

    NON registra:
    - storico candele
    - no-signal
    - bootstrap candles
    - market context continuo
    """

    def __init__(self, base_dir="live/logs/journal"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        self.events_file = self.base_dir / "events.jsonl"
        self.signals_file = self.base_dir / "signals.csv"
        self.trades_file = self.base_dir / "trades.csv"

        self._ensure_csv_headers()

    def _utc_now(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _ensure_csv_headers(self):
        if not self.signals_file.exists():
            with self.signals_file.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "logged_at_utc",
                    "market",
                    "timestamp",
                    "side",
                    "entry_price",
                    "stop_loss",
                    "take_profit",
                    "confidence",
                    "strategy",
                    "reason",
                    "metadata",
                ])

        if not self.trades_file.exists():
            with self.trades_file.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "logged_at_utc",
                    "event",
                    "market",
                    "timestamp",
                    "side",
                    "price",
                    "size",
                    "stop_loss",
                    "take_profit",
                    "pnl",
                    "reason",
                    "strategy",
                    "metadata",
                ])

    def log_event(self, event_type, payload=None):
        row = {
            "logged_at_utc": self._utc_now(),
            "event_type": event_type,
            "payload": payload or {},
        }

        with self.events_file.open("a") as f:
            f.write(json.dumps(row, default=str) + "\n")

    def log_signal(self, market, timestamp, signal):
        """
        Registra SOLO segnali reali.
        Se signal è None o False, non scrive nulla.
        """
        if not signal:
            return

        metadata = getattr(signal, "metadata", {}) or {}

        with self.signals_file.open("a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                self._utc_now(),
                market,
                timestamp,
                getattr(signal, "side", ""),
                getattr(signal, "entry_price", ""),
                getattr(signal, "stop_loss", ""),
                getattr(signal, "take_profit", ""),
                getattr(signal, "confidence", ""),
                getattr(signal, "strategy", ""),
                metadata.get("reason", ""),
                json.dumps(metadata, default=str),
            ])

    def log_entry(
        self,
        market,
        timestamp,
        side,
        price,
        size,
        stop_loss=None,
        take_profit=None,
        reason="ENTRY",
        strategy="",
        metadata=None,
    ):
        self._log_trade(
            event="ENTRY",
            market=market,
            timestamp=timestamp,
            side=side,
            price=price,
            size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            pnl=None,
            reason=reason,
            strategy=strategy,
            metadata=metadata,
        )

    def log_exit(
        self,
        market,
        timestamp,
        side,
        price,
        size,
        pnl=None,
        reason="EXIT",
        strategy="",
        metadata=None,
    ):
        self._log_trade(
            event="EXIT",
            market=market,
            timestamp=timestamp,
            side=side,
            price=price,
            size=size,
            stop_loss=None,
            take_profit=None,
            pnl=pnl,
            reason=reason,
            strategy=strategy,
            metadata=metadata,
        )

    def _log_trade(
        self,
        event,
        market,
        timestamp,
        side,
        price,
        size,
        stop_loss=None,
        take_profit=None,
        pnl=None,
        reason="",
        strategy="",
        metadata=None,
    ):
        with self.trades_file.open("a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                self._utc_now(),
                event,
                market,
                timestamp,
                side,
                price,
                size,
                stop_loss if stop_loss is not None else "",
                take_profit if take_profit is not None else "",
                pnl if pnl is not None else "",
                reason,
                strategy,
                json.dumps(metadata or {}, default=str),
            ])
