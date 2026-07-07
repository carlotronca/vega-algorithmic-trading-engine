from dataclasses import dataclass


@dataclass
class Candle:
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    symbol: str = "SOL-USDC"
