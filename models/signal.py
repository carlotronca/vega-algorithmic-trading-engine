# =============================
# SIGNAL OBJECT
# =============================

class Signal:

    def __init__(
        self,
        side,
        symbol,
        entry_price,
        stop_loss=None,
        take_profit=None,
        confidence=1.0,
        metadata=None
    ):

        self.side = str(side)
        self.symbol = str(symbol)

        self.entry_price = float(entry_price)

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

        self.confidence = float(confidence)

        self.metadata = metadata or {}

    # =============================
    # STRING DEBUG
    # =============================
    def __repr__(self):

        return (
            f"Signal("
            f"side={self.side}, "
            f"symbol={self.symbol}, "
            f"entry={self.entry_price}, "
            f"sl={self.stop_loss}, "
            f"tp={self.take_profit}, "
            f"confidence={self.confidence}"
            f")"
        )
