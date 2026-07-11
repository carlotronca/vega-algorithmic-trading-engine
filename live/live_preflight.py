import os
import sys
import json
import time
from datetime import datetime, timezone


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from exchange.bitvavo_read_client import BitvavoReadClient, save_snapshot
from reconciliation.exchange_reconciliation import (
    LOCAL_STATE_PATH,
    EXCHANGE_SNAPSHOT_PATH,
    RECONCILIATION_REPORT_PATH,
    reconcile,
    load_json,
    save_json_atomic,
)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def recover_position_from_exchange(local_state, exchange_snapshot):

    print("Running exchange-driven recovery...")

    balances = exchange_snapshot.get("balances", [])

    open_orders = exchange_snapshot.get(
        "open_orders",
        [],
    )

    sol_balance = 0.0

    sol_data = balances.get("SOL")

    if sol_data:

        available = float(sol_data.get("available", 0))
        in_order = float(sol_data.get("in_order", 0))
        sol_balance = available + in_order

    MIN_RECOVERABLE_SOL = 0.0001

    if sol_balance <= MIN_RECOVERABLE_SOL:

        print("[RECOVERY] No real exchange position found.")

        local_state["position"]["is_open"] = False
        local_state["position"]["size"] = None
        local_state["position"]["stop_loss"] = None
        local_state["position"]["sl_order_id"] = None

        return local_state

    print(
        f"[RECOVERY] Real exchange position detected: "
        f"{sol_balance} SOL"
    )

    sl_order_id = None
    stop_loss = None
    protection = "UNPROTECTED"

    for order in open_orders:

        if order.get("side") != "sell":
            continue

        sl_order_id = order.get("orderId")

        stop_loss = (
            order.get("triggerPrice")
            or order.get("price")
        )

        protection = "EXCHANGE_SL"

        break

    local_state["position"]["is_open"] = True
    local_state["position"]["size"] = sol_balance

    local_state["position"][
        "symbol"
    ] = "SOL-USDC"

    local_state["position"]["entry_price"] = None
    local_state["position"]["stop_loss"] = stop_loss
    local_state["position"]["take_profit"] = None
    local_state["position"]["entry_timestamp"] = time.time()

    local_state["position"][
        "runtime_position_state"
    ] = "POSITION_OPEN"

    local_state["position"]["recovered_from_exchange"] = True

    local_state["position"]["protection_level"] = protection

    local_state["position"]["stop_loss_order_id"] = (
        sl_order_id
    )

    if sl_order_id is not None:

        local_state["position"][
            "stop_loss_verified"
        ] = True

        local_state["position"][
            "is_protected"
        ] = True

    return local_state

def main():
    print("=" * 80)
    print(f"[{utc_now()}] LIVE PREFLIGHT STARTED")
    print("=" * 80)

    client = BitvavoReadClient()

    print("Updating exchange snapshot...")
    snapshot = client.get_wallet_snapshot("SOL-USDC")
    save_snapshot(snapshot, EXCHANGE_SNAPSHOT_PATH)

    print(f"Exchange snapshot saved: {EXCHANGE_SNAPSHOT_PATH}")

    print("Running reconciliation...")

    exchange_snapshot = load_json(EXCHANGE_SNAPSHOT_PATH)

    print("Loading local state...")
    local_state = load_json(LOCAL_STATE_PATH)

    local_state = recover_position_from_exchange(
        local_state,
        exchange_snapshot,
    )

    save_json_atomic(local_state, LOCAL_STATE_PATH)

    print("Local state updated from exchange recovery.")

    report = reconcile(local_state, exchange_snapshot)
    save_json_atomic(report, RECONCILIATION_REPORT_PATH)

    print(f"Reconciliation report saved: {RECONCILIATION_REPORT_PATH}")
    print("")

    print(json.dumps(report, indent=2))
    print("")

    if report.get("status") == "RECONCILIATION_OK":
        print("=" * 80)
        print("LIVE_PREFLIGHT_OK")
        print("Exchange, wallet and local state are aligned.")
        print("API_WRITE remains controlled separately.")
        print("=" * 80)
        sys.exit(0)

    print("=" * 80)
    print("LIVE_PREFLIGHT_BLOCKED")
    print("Do not start live runtime.")
    print("=" * 80)
    sys.exit(1)


if __name__ == "__main__":
    main()
