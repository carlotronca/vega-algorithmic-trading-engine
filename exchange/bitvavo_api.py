# exchange/bitvavo_api.py

import json
import threading
import time
import websocket
from datetime import datetime, timezone

import config

from python_bitvavo_api.bitvavo import (
    Bitvavo
)


# =====================================================
# BITVAVO API WRAPPER V2.5
# =====================================================
#
# PURPOSE:
#
# Centralized exchange abstraction layer
#
# RESPONSIBILITIES:
#
# - REST API
# - websocket orchestration
# - order placement
# - order cancellation
# - balances
# - candles
# - open orders
# - exchange snapshot retrieval
#
# NON RESPONSIBLE FOR:
#
# - reconciliation
# - recovery
# - runtime state
# - persistence
# - lifecycle semantics
#
# =====================================================


class BitvavoAPI:

    # =================================================
    # INIT
    # =================================================
    def __init__(self):

        self.client = Bitvavo({

            "APIKEY": (
                config.API_KEY
            ),

            "APISECRET": (
                config.API_SECRET
            ),

            "RESTURL": (
                "https://api.bitvavo.com/v2"
            ),

            "ACCESSWINDOW": 10000
        })

        self.websocket_running = False

        self.websocket_thread = None

    # =================================================
    # TIME
    # =================================================
    def utc_now(self):

        return datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    # =================================================
    # LOG
    # =================================================
    def log(self, message):

        print(
            f"[{self.utc_now()}] "
            f"[BITVAVO_API] "
            f"{message}"
        )

    # =================================================
    # BALANCES
    # =================================================
    def get_balances(self):

        try:

            balances = (
                self.client.balance({})
            )

            result = {}

            for item in balances:

                symbol = item.get(
                    "symbol"
                )

                result[symbol] = {

                    "available": float(
                        item.get(
                            "available",
                            0
                        )
                    ),

                    "in_order": float(
                        item.get(
                            "inOrder",
                            0
                        )
                    )
                }

            return result

        except Exception as e:

            self.log(
                f"BALANCE ERROR => {e}"
            )

            raise

    # =================================================
    # CANDLES
    # =================================================
    def get_candles(

        self,

        market,

        interval="1h",

        limit=400
    ):

        try:

            candles = (
                self.client.candles(

                    market,

                    interval,

                    {
                        "limit": limit
                    }
                )
            )

            return candles

        except Exception as e:

            self.log(
                f"CANDLE ERROR => {e}"
            )

            raise

    # =================================================
    # OPEN ORDERS
    # =================================================
    def get_open_orders(
        self,
        market=None
    ):

        try:

            if market is not None:

                return (
                    self.client.ordersOpen({

                        "market": market
                    })
                )

            return (
                self.client.ordersOpen({})
            )

        except Exception as e:

            self.log(
                f"OPEN ORDERS ERROR => {e}"
            )

            raise

    # =================================================
    # GET ORDER
    # =================================================
    def get_order(

        self,

        market,

        order_id
    ):

        try:

            return self.client.getOrder(

                market,

                order_id
            )

        except Exception as e:

            self.log(
                f"GET ORDER ERROR => {e}"
            )

            raise

    # =================================================
    # CANCEL ORDER
    # =================================================
    def cancel_order(

        self,

        market,

        order_id
    ):

        try:

            return self.client.cancelOrder(

                market,

                order_id
            )

        except Exception as e:

            self.log(
                f"CANCEL ERROR => {e}"
            )

            raise

    # =================================================
    # MARKET ORDER
    # =================================================
    def place_market_order(

        self,

        market,

        side,

        amount
    ):

        try:

            result = self.client.placeOrder(

                market,

                side.lower(),

                "market",

                {
                    "amount": str(amount),

                    "operatorId": 1

                }
            )

            self.log(
                f"MARKET ORDER => "
                f"{side} "
                f"{market} "
                f"amount={amount}"
            )

            return result

        except Exception as e:

            self.log(
                f"MARKET ORDER ERROR => {e}"
            )

            raise

    # =================================================
    # LIMIT ORDER
    # =================================================
    def place_limit_order(

        self,

        market,

        side,

        amount,

        price
    ):

        try:

            result = self.client.placeOrder(

                market,

                side.lower(),

                "limit",

                {

                    "amount": str(amount),

                    "price": str(price),

                    "operatorId": 1

                }
            )

            self.log(
                f"LIMIT ORDER => "
                f"{side} "
                f"{market} "
                f"amount={amount} "
                f"price={price}"
            )

            return result

        except Exception as e:

            self.log(
                f"LIMIT ORDER ERROR => {e}"
            )

            raise

    # =================================================
    # STOP LOSS LIMIT
    # =================================================
    def place_stop_loss_limit(

        self,

        market,

        side,

        amount,

        trigger_price,

        limit_price
    ):

        try:

            result = self.client.placeOrder(

                market,

                side.lower(),

                "stopLossLimit",

                {

                    "amount": str(amount),

                    "triggerType": "price",

                    "triggerReference": "lastTrade",

                    "triggerAmount": str(
                        trigger_price
                    ),

                    "price": str(
                        limit_price
                    ),

                    "operatorId": 1

                }
            )

            self.log(
                f"STOP LOSS LIMIT => "
                f"{side} "
                f"{market} "
                f"trigger={trigger_price}"
            )

            self.log(
                f"STOP LOSS MARKET RESPONSE => {result}"
            )

            return result

        except Exception as e:

            self.log(
                f"STOP LOSS ERROR => {e}"
            )

            raise

    # =================================================
    # STOP LOSS MARKET
    # =================================================
    def place_stop_loss_market(

        self,

        market,

        side,

        amount,

        trigger_price
    ):

        try:

            result = self.client.placeOrder(

                market,

                side.lower(),

                "stopLoss",

                {

                    "amount": str(amount),

                    "triggerType": "price",

                    "triggerReference": "lastTrade",

                    "triggerAmount": str(
                        trigger_price
                    ),

                    "operatorId": 1

                }
            )

            self.log(
                f"STOP LOSS MARKET => "
                f"{side} "
                f"{market} "
                f"trigger={trigger_price}"
            )

            return result

        except Exception as e:

            self.log(
                f"STOP LOSS MARKET ERROR => {e}"
            )

            raise

    # =================================================
    # EXCHANGE SNAPSHOT
    # =================================================
    def get_exchange_snapshot(

        self,

        market="SOL-USDC"
    ):

        try:

            balances = (
                self.get_balances()
            )

            orders = (
                self.get_open_orders(
                    market
                )
            )

            return {

                "timestamp_utc": (
                    self.utc_now()
                ),

                "market": market,

                "balances": balances,

                "open_orders": orders
            }

        except Exception as e:

            self.log(
                f"SNAPSHOT ERROR => {e}"
            )

            raise

    # =================================================
    # SAVE SNAPSHOT
    # =================================================
    def save_exchange_snapshot(

        self,

        path,

        market="SOL-USDC"
    ):

        snapshot = (
            self.get_exchange_snapshot(
                market
            )
        )

        with open(
            path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                snapshot,
                f,
                indent=2
            )

            f.write("\n")

        return snapshot

    # =================================================
    # WEBSOCKET CANDLES
    # =================================================
    def start_candle_websocket(

        self,

        market,

        interval,

        callback
    ):

        if self.websocket_running:

            self.log(
                "WEBSOCKET ALREADY RUNNING"
            )

            return

        self.websocket_running = True

        self.log(
            f"START WEBSOCKET "
            f"{market} "
            f"{interval}"
        )

        def websocket_runner():

            while self.websocket_running:

                try:

                    def on_open(ws):

                        self.log(
                            "WEBSOCKET CONNECTED"
                        )

                        subscribe_payload = {

                            "action": "subscribe",

                            "channels": [

                                {
                                    "name": "candles",

                                    "markets": [
                                        market
                                    ],

                                    "interval": [
                                        interval
                                    ]
                                }
                            ]
                        }

                        ws.send(
                            json.dumps(
                                subscribe_payload
                            )
                        )

                        self.log(
                            f"SUBSCRIBED => "
                            f"{market} "
                            f"{interval}"
                        )

                    def on_message(

                        ws,

                        message
                    ):

                        try:

                            data = json.loads(
                                message
                            )

                            if (
                                "event" in data
                                and data["event"] == "candle"
                            ):

                                callback(
                                    data
                                )

                        except Exception as e:

                            self.log(
                                f"MESSAGE PARSE ERROR => {e}"
                            )

                    def on_error(

                        ws,

                        error
                    ):

                        self.log(
                            f"WEBSOCKET ERROR => {error}"
                        )

                    def on_close(

                        ws,

                        close_status_code,

                        close_msg
                    ):

                        self.log(
                            "WEBSOCKET CLOSED"
                        )

                    ws = websocket.WebSocketApp(

                        "wss://ws.bitvavo.com/v2/",

                        on_open=on_open,

                        on_message=on_message,

                        on_error=on_error,

                        on_close=on_close
                    )

                    ws.run_forever(

                        ping_interval=30,

                        ping_timeout=10
                    )

                except Exception as e:

                    self.log(
                        f"WEBSOCKET RUNNER ERROR => {e}"
                    )

                if self.websocket_running:

                    self.log(
                        "RECONNECT IN 5s"
                    )

                    time.sleep(5)

        self.websocket_thread = (
            threading.Thread(

                target=websocket_runner,

                daemon=True
            )
        )

        self.websocket_thread.start()
    # =================================================
    # STOP WEBSOCKET
    # =================================================
    def stop_websocket(self):

        self.websocket_running = False

        self.log(
            "WEBSOCKET STOPPED"
        )
