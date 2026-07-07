# =============================
# PAPER EXECUTION MODEL
# =============================

class PaperExecution:

    def __init__(
        self,
        fee_rate=0.0005,
        slippage_rate=0.0005
    ):

        # Example:
        # fee_rate 0.0025 = 0.25%
        # slippage_rate 0.0005 = 0.05%

        self.fee_rate = float(fee_rate)
        self.slippage_rate = float(slippage_rate)

    # =============================
    # ENTRY EXECUTION PRICE
    # =============================
    def get_entry_price(self, market_price, side):

        market_price = float(market_price)

        if side == "BUY":
            return market_price * (1 + self.slippage_rate)

        if side == "SELL":
            return market_price * (1 - self.slippage_rate)

        raise ValueError(f"Unsupported side: {side}")

    # =============================
    # EXIT EXECUTION PRICE
    # =============================
    def get_exit_price(self, market_price, side):

        market_price = float(market_price)

        if side == "BUY":
            # closing a long means selling, worse price
            return market_price * (1 - self.slippage_rate)

        if side == "SELL":
            # closing a short means buying back, worse price
            return market_price * (1 + self.slippage_rate)

        raise ValueError(f"Unsupported side: {side}")

    # =============================
    # FEE CALCULATION
    # =============================
    def calculate_fee(self, price, size):

        price = float(price)
        size = float(size)

        return price * size * self.fee_rate
