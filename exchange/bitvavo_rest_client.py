# exchange/bitvavo_rest_client.py

import os
import sys
import time
import hmac
import hashlib
import requests
from datetime import datetime, timezone


PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

if PROJECT_ROOT not in sys.path:

    sys.path.insert(
        0,
        PROJECT_ROOT
    )

import config


class BitvavoRESTClient:

    # =====================================================
    # INIT
    # =====================================================
    def __init__(self):

        self.api_key = config.API_KEY

        self.api_secret = config.API_SECRET

        self.base_url = config.BASE_URL

        self.session = requests.Session()

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
    # LOG
    # =====================================================
    def log(
        self,
        message
    ):

        print(
            f"[{self.utc_now()}] "
            f"[BITVAVO_REST] "
            f"{message}"
        )

    # =====================================================
    # SIGNATURE
    # =====================================================
    def build_signature(

        self,

        timestamp_ms,

        method,

        endpoint,

        body=""
    ):

        message = (
            str(timestamp_ms)
            + method.upper()
            + "/v2"
            + endpoint
            + body
        )

        signature = hmac.new(

            self.api_secret.encode(),

            message.encode(),

            hashlib.sha256
        ).hexdigest()

        return signature

    # =====================================================
    # HEADERS
    # =====================================================
    def build_headers(

        self,

        method,

        endpoint,

        body=""
    ):

        timestamp_ms = int(
            time.time() * 1000
        )

        signature = self.build_signature(

            timestamp_ms=timestamp_ms,

            method=method,

            endpoint=endpoint,

            body=body
        )

        return {

            "Bitvavo-Access-Key": (
                self.api_key
            ),

            "Bitvavo-Access-Signature": (
                signature
            ),

            "Bitvavo-Access-Timestamp": (
                str(timestamp_ms)
            ),

            "Bitvavo-Access-Window": "10000",

            "Content-Type": "application/json"
        }

    # =====================================================
    # REQUEST
    # =====================================================
    def request(

        self,

        method,

        endpoint,

        payload=None
    ):

        url = (
            self.base_url
            + endpoint
        )

        body = ""

        if payload is not None:

            import json

            body = json.dumps(
                payload,
                separators=(",", ":")
            )

        headers = self.build_headers(

            method=method,

            endpoint=endpoint,

            body=body
        )

        self.log(
            f"{method.upper()} {endpoint}"
        )

        if payload is not None:

            self.log(
                f"PAYLOAD => {payload}"
            )

        response = self.session.request(

            method=method,

            url=url,

            headers=headers,

            data=body if body else None,

            timeout=30
        )

        response_json = response.json()

        self.log(
            f"RESPONSE => {response_json}"
        )

        return response_json

    # =====================================================
    # BALANCE
    # =====================================================
    def get_balance(self):

        return self.request(

            method="GET",

            endpoint="/balance"
        )

    # =====================================================
    # TICKER
    # =====================================================
    def get_ticker_price(

        self,

        market="SOL-USDC"
    ):

        endpoint = (
            f"/ticker/price"
            f"?market={market}"
        )

        return self.request(

            method="GET",

            endpoint=endpoint
        )

    # =====================================================
    # OPEN ORDERS
    # =====================================================
    def get_open_orders(

        self,

        market="SOL-USDC"
    ):

        endpoint = (
            f"/ordersOpen"
            f"?market={market}"
        )

        return self.request(

            method="GET",

            endpoint=endpoint
        )

    # =====================================================
    # GET ORDER
    # =====================================================
    def get_order(

        self,

        market,

        order_id
    ):

        endpoint = (
            f"/order"
            f"?market={market}"
            f"&orderId={order_id}"
        )

        return self.request(

            method="GET",

            endpoint=endpoint
        )

    # =====================================================
    # CANCEL ORDER
    # =====================================================
    def cancel_order(

        self,

        market,

        order_id
    ):

        endpoint = (
            f"/order"
            f"?market={market}"
            f"&orderId={order_id}"
        )

        return self.request(

            method="DELETE",

            endpoint=endpoint
        )

    # =====================================================
    # MARKET BUY
    # =====================================================
    def place_market_buy(

        self,

        market,

        amount_quote_usdc
    ):

        payload = {

            "market": market,

            "side": "buy",

            "orderType": "market",

            "amountQuote": str(
                amount_quote_usdc
            ),

            "operatorId": 1
        }

        return self.request(

            method="POST",

            endpoint="/order",

            payload=payload
        )

    # =====================================================
    # STOP LOSS
    # =====================================================
    def place_stop_loss(

        self,

        market,

        amount,

        trigger_price
    ):

        payload = {

            "market": market,

            "side": "sell",

            "orderType": "stopLoss",

            "amount": str(amount),

            "triggerType": "price",

            "triggerReference": "lastTrade",

            "triggerAmount": str(
                trigger_price
            ),

            "operatorId": 1
        }

        return self.request(

            method="POST",

            endpoint="/order",

            payload=payload
        )

    # =====================================================
    # TAKE PROFIT LIMIT
    # =====================================================
    def place_take_profit_limit(

        self,

        market,

        amount,

        trigger_price,

        limit_price
    ):

        payload = {

            "market": market,

            "side": "sell",

            "orderType": "takeProfitLimit",

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

        return self.request(

            method="POST",

            endpoint="/order",

            payload=payload
        )
