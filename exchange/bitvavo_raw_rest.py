import time
import json
import hmac
import hashlib
from decimal import Decimal

import requests

import config


class BitvavoRawREST:

    BASE_URL = "https://api.bitvavo.com/v2"

    # =====================================================
    # INIT
    # =====================================================

    def __init__(self):

        self.api_key = config.API_KEY
        self.api_secret = config.API_SECRET

    # =====================================================
    # TIMESTAMP
    # =====================================================

    def _timestamp_ms(self):

        return str(
            int(time.time() * 1000)
        )

    # =====================================================
    # JSON SERIALIZATION
    # =====================================================

    def _json_dumps(
        self,
        payload
    ):

        def decimal_default(obj):

            if isinstance(obj, Decimal):

                return str(obj)

            raise TypeError(
                f"Object of type {type(obj)} "
                f"is not JSON serializable"
            )

        return json.dumps(

            payload,

            default=decimal_default,

            separators=(",", ":"),

            sort_keys=False
        )

    # =====================================================
    # SIGNATURE
    # =====================================================

    def _sign(
        self,
        timestamp,
        method,
        endpoint,
        body=""
    ):

        message = (
            timestamp
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

    def _headers(
        self,
        method,
        endpoint,
        body=""
    ):

        timestamp = self._timestamp_ms()

        signature = self._sign(

            timestamp=timestamp,

            method=method,

            endpoint=endpoint,

            body=body
        )

        # =================================================
        # AUTH DEBUG LOG
        # =================================================

        print("")
        print("=" * 80)
        print("RAW REST AUTH")
        print(f"TIMESTAMP => {timestamp}")
        print(f"METHOD    => {method}")
        print(f"ENDPOINT  => {endpoint}")
        print(f"BODY      => {body}")
        print(f"SIGNATURE => {signature}")
        print("=" * 80)

        return {

            "Bitvavo-Access-Key": self.api_key,

            "Bitvavo-Access-Signature": signature,

            "Bitvavo-Access-Timestamp": timestamp,

            "Bitvavo-Access-Window": "10000",

            "Content-Type": "application/json"
        }

    # =====================================================
    # RAW REQUEST
    # =====================================================

    def _request(
        self,
        method,
        endpoint,
        payload=None
    ):

        method = method.upper()

        url = self.BASE_URL + endpoint

        body = ""

        if payload is not None:

            body = self._json_dumps(payload)

        headers = self._headers(

            method=method,

            endpoint=endpoint,

            body=body
        )

        # =================================================
        # REQUEST DEBUG LOG
        # =================================================

        print("")
        print("=" * 80)
        print("RAW REST REQUEST")
        print(f"URL      => {url}")
        print(f"METHOD   => {method}")
        print(f"ENDPOINT => {endpoint}")
        print(f"PAYLOAD  => {body}")
        print(f"HEADERS  => {headers}")
        print("=" * 80)

        try:

            response = requests.request(

                method=method,

                url=url,

                headers=headers,

                data=body if body else None,

                timeout=30
            )

        except Exception as e:

            print("")
            print("=" * 80)
            print("RAW REST NETWORK ERROR")
            print(str(e))
            print("=" * 80)

            raise

        # =================================================
        # RESPONSE DEBUG LOG
        # =================================================

        print("")
        print("=" * 80)
        print("RAW REST RESPONSE")
        print(f"HTTP STATUS => {response.status_code}")
        print(response.text)
        print("=" * 80)

        return response

    # =====================================================
    # BALANCE
    # =====================================================

    def get_balance(self):

        return self._request(

            method="GET",

            endpoint="/balance"
        )

    # =====================================================
    # MARKETS
    # =====================================================

    def get_markets(
        self,
        market=None
    ):

        endpoint = "/markets"

        if market is not None:

            endpoint += f"?market={market}"

        return self._request(

            method="GET",

            endpoint=endpoint
        )

    # =====================================================
    # PLACE MARKET BUY
    # =====================================================

    def place_market_buy(
        self,
        market,
        amount_quote,
        operator_id=1
    ):

        payload = {

            "market": market,

            "side": "buy",

            "orderType": "market",

            "amountQuote": str(amount_quote),

            "operatorId": operator_id
        }

        return self._request(

            method="POST",

            endpoint="/order",

            payload=payload
        )

    # =====================================================
    # PLACE MARKET SELL
    # =====================================================

    def place_market_sell(
        self,
        market,
        amount,
        operator_id=1
    ):

        payload = {

            "market": market,

            "side": "sell",

            "orderType": "market",

            "amount": str(amount),

            "operatorId": operator_id
        }

        return self._request(

            method="POST",

            endpoint="/order",

            payload=payload
        )

    # =====================================================
    # OPEN ORDERS
    # =====================================================

    def get_open_orders(
        self,
        market=None
    ):

        endpoint = "/ordersOpen"

        if market is not None:

            endpoint += f"?market={market}"

        return self._request(

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

        return self._request(

            method="DELETE",

            endpoint=endpoint
        )
