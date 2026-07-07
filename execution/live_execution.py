import os
import sys
import uuid
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from exchange.bitvavo_raw_rest import BitvavoRawREST
from config import API_KEY, API_SECRET


class LiveExecution:
    def __init__(
        self,
        market="SOL-USDC",
        api_write=True,
        max_notional_usdc=500.0,
        fee_rate=0.0005
    ):
        self.market = str(market)
        self.api_write = bool(api_write)
        self.max_notional_usdc = Decimal(str(max_notional_usdc))
        self.fee_rate = float(fee_rate)

        if self.market != "SOL-USDC":
            raise RuntimeError("LIVE execution allowed only for SOL-USDC")

        self.client = BitvavoRawREST()

    def utc_now(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def _format_decimal(self, value, decimals=8):
        q = Decimal("1." + ("0" * decimals))
        return str(Decimal(str(value)).quantize(q, rounding=ROUND_DOWN))

    def get_entry_price(self, market_price, side):
        return float(market_price)

    def get_exit_price(self, market_price, side):
        return float(market_price)

    def cancel_order(self, order_id):

        return self.client.cancel_order(
            self.market,
            order_id,
        )

    def calculate_fee(self, price, size):
        return float(price) * float(size) * float(self.fee_rate)

    def place_market_buy_quote(self, amount_quote_usdc):
        amount_quote = Decimal(str(amount_quote_usdc))

        if not self.api_write:
            raise RuntimeError("API_WRITE_OFF: live buy blocked")

        if amount_quote <= 0:
            raise RuntimeError("Invalid buy amountQuote")

        if amount_quote > self.max_notional_usdc:
            raise RuntimeError(
                f"Buy blocked: amountQuote {amount_quote} exceeds cap {self.max_notional_usdc}"
            )

        payload = {
            "market": self.market,
            "side": "buy",
            "orderType": "market",
            "amountQuote": self._format_decimal(amount_quote, decimals=2),
            "clientOrderId": str(uuid.uuid4())
        }

        print("")
        print("=" * 80)
        print(f"[{self.utc_now()}] LIVE MARKET BUY")
        print(payload)
        print("=" * 80)

        response = self.client.place_market_buy(


            market=self.market,

            amount_quote=self._format_decimal(
                amount_quote,
                decimals=2
            ),

            operator_id=1
        )
        print("")
        print("=" * 80)
        print(f"[{self.utc_now()}] LIVE MARKET BUY RESPONSE")
        print(response)
        print("=" * 80)

        return response

    def place_market_sell_amount(self, amount_sol):

        print("SELL amount_sol RAW =", repr(amount_sol), type(amount_sol))

        amount = Decimal(str(amount_sol))

        if not self.api_write:
            raise RuntimeError("API_WRITE_OFF: live sell blocked")

        if amount <= 0:
            raise RuntimeError("Invalid sell amount")

        payload = {
            "market": self.market,
            "side": "sell",
            "orderType": "market",
            "amount": self._format_decimal(amount, decimals=8),
            "clientOrderId": str(uuid.uuid4())
        }

        print("")
        print("=" * 80)
        print(f"[{self.utc_now()}] LIVE MARKET SELL")
        print(payload)
        print("=" * 80)

        return self.client.place_market_sell(

            market=self.market,

            amount=self._format_decimal(
                amount,
                decimals=8
            ),

            operator_id=1
        )
