# reconciliation/exchange_reconciliation.py

import os
import json
from datetime import datetime, timezone

from exchange.bitvavo_api import BitvavoAPI

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

LOCAL_STATE_PATH = os.path.join(
    PROJECT_ROOT,
    "state",
    "state.json"
)

EXCHANGE_SNAPSHOT_PATH = os.path.join(
    PROJECT_ROOT,
    "state",
    "exchange_snapshot.json"
)

RECONCILIATION_REPORT_PATH = os.path.join(
    PROJECT_ROOT,
    "state",
    "reconciliation_report.json"
)


# =====================================================
# TIME
# =====================================================
def utc_now():

    return datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


# =====================================================
# JSON HELPERS
# =====================================================
def load_json(path):

    if not os.path.exists(path):
        return None

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def save_json_atomic(
    data,
    path
):

    os.makedirs(
        os.path.dirname(path),
        exist_ok=True
    )

    tmp_path = path + ".tmp"

    with open(
        tmp_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2
        )

        f.write("\n")

    os.replace(
        tmp_path,
        path
    )


# =====================================================
# FLOAT PARSER
# =====================================================
def parse_float(
    value,
    default=0.0
):

    try:

        if value is None:
            return default

        return float(value)

    except (
        TypeError,
        ValueError
    ):

        return default


# =====================================================
# RECONCILIATION
# =====================================================
def reconcile(
    local_state,
    exchange_snapshot
):

    issues = []

    warnings = []

    lifecycle_events = []

    # =================================================
    # BASIC VALIDATION
    # =================================================

    if local_state is None:

        issues.append(
            "LOCAL_STATE_MISSING"
        )

    if exchange_snapshot is None:

        issues.append(
            "EXCHANGE_SNAPSHOT_MISSING"
        )

    if issues:

        return {

            "timestamp_utc": utc_now(),

            "status": (
                "RECONCILIATION_LOCK_REQUIRED"
            ),

            "can_trade": False,

            "issues": issues,

            "warnings": warnings,

            "lifecycle_events": (
                lifecycle_events
            )
        }

    # =================================================
    # LOCAL POSITION
    # =================================================

    local_position = local_state.get(
        "position",
        {}
    )

    local_is_open = bool(
        local_position.get(
            "is_open",
            False
        )
    )

    runtime_position_state = (
        local_position.get(
            "runtime_position_state"
        )
    )

    protection_level = (
        local_position.get(
            "protection_level",
            "NONE"
        )
    )

    pending_action = (
        local_position.get(
            "pending_action",
            "NONE"
        )
    )

    operation_id = (
        local_position.get(
            "operation_id"
        )
    )

    stop_loss_order_id = (
        local_position.get(
            "stop_loss_order_id"
        )
    )

    stop_loss_exchange_status = (
        local_position.get(
            "stop_loss_exchange_status"
        )
    )


    # =================================================
    # AUTHORITATIVE POSITION SIZE
    # =================================================

    filled_size = parse_float(
        local_position.get(
            "filled_size"
        ),
        None
    )

    estimated_size = parse_float(
        local_position.get(
            "size"
        ),
        0.0
    )

    local_position_size = (

        filled_size

        if filled_size is not None

        else estimated_size
    )

    # =================================================
    # EXCHANGE BALANCES
    # =================================================

    balances = exchange_snapshot.get(
        "balances",
        {}
    )

    sol_balance = balances.get(
        "SOL",
        {}
    )

    sol_available = parse_float(
        sol_balance.get(
            "available",
            0
        )
    )

    sol_in_order = parse_float(
        sol_balance.get(
            "in_order",
            0
        )
    )

    sol_total = (
        sol_available
        + sol_in_order
    )

    usdc_available = parse_float(
        balances.get(
            "USDC",
            {}
        ).get(
            "available",
            0
        )
    )

    has_exchange_stop_loss = (
        stop_loss_order_id is not None
    )


    exchange_stop_loss_order = None

    exchange_stop_loss_verified = False

    if has_exchange_stop_loss:

        try:

            api = BitvavoAPI()

            exchange_stop_loss_order = (
                api.get_order(

                    market=local_position.get(
                        "symbol"
                    ),

                    order_id=stop_loss_order_id
                )
            )


            if exchange_stop_loss_order:

                stop_loss_exchange_status = (
                    exchange_stop_loss_order.get(
                        "status"
                    )
                )

                if stop_loss_exchange_status in [
                    "new",
                    "awaitingTrigger",
                    "partiallyFilled"
                ]:

                    exchange_stop_loss_verified = (
                        True
                    )


        except Exception as exc:

            warnings.append(
                f"STOP_LOSS_ORDER_QUERY_FAILED: {exc}"
            )


    stop_loss_likely_filled = (

        local_is_open

        and sol_total <= 0

        and not exchange_stop_loss_verified
    )


    # =================================================
    # POSITION CONSISTENCY
    # =================================================

    if stop_loss_likely_filled:

        lifecycle_events.append(
            "EXCHANGE_STOP_LOSS_FILLED"
        )

    if (

        local_is_open

        and sol_total <= 0

        and not exchange_stop_loss_verified

        and not stop_loss_likely_filled
    ):

        issues.append(
            "LOCAL_POSITION_OPEN_BUT_NO_SOL_ON_EXCHANGE"
        )


    if (
        local_is_open
        and not exchange_stop_loss_verified
        and stop_loss_order is None
    ):

        issues.append(
            "OPEN_POSITION_WITHOUT_VERIFIED_STOP_LOSS"
        )

    if (
        not local_is_open
        and sol_total > 0
    ):

        issues.append(
            "SOL_ON_EXCHANGE_BUT_LOCAL_POSITION_CLOSED"
        )

    # =================================================
    # SIZE CONSISTENCY
    # =================================================

    if local_is_open:

        size_diff = abs(
            sol_total
            - local_position_size
        )

        if size_diff > 0.01:

            warnings.append(
                "POSITION_SIZE_MISMATCH"
            )

            lifecycle_events.append(
                "EXCHANGE_SIZE_NORMALIZATION_REQUIRED"
            )

    # =================================================
    # SYNTHETIC PROTECTION MODE
    # =================================================


    protection_status = {

        "position_is_protected": (
            local_is_open
        ),

        "protection_level": (

            "EXCHANGE_STOPLOSS"

            if has_exchange_stop_loss

            else (

                "SYNTHETIC_RUNTIME"

                if local_is_open

                else "NONE"
            )
        ),

        "stop_loss_found": (
            has_exchange_stop_loss
        ),

        "take_profit_found": False,

        "stop_loss_status": (
            stop_loss_exchange_status
        ),

        "take_profit_status": None,

        "stop_loss_order": (
            stop_loss_order_id
        ),

        "take_profit_order": None
    }


    if local_is_open:

        lifecycle_events.append(
            "SYNTHETIC_RUNTIME_PROTECTION_ENABLED"
        )

    # =================================================
    # EXCHANGE SNAPSHOT VALIDATION
    # =================================================

    if (
        exchange_snapshot.get(
            "api_write"
        ) is not False
    ):

        issues.append(
            "EXCHANGE_SNAPSHOT_API_WRITE_NOT_FALSE"
        )

    if (
        exchange_snapshot.get(
            "mode"
        )
        != "LIVE_READ"
    ):

        warnings.append(
            "EXCHANGE_SNAPSHOT_MODE_NOT_LIVE_READ"
        )

    # =================================================
    # FINAL STATUS
    # =================================================

    status = (

        "RECONCILIATION_OK"

        if not issues

        else "RECONCILIATION_LOCK_REQUIRED"
    )

    # =================================================
    # FINAL REPORT
    # =================================================

    return {

        "timestamp_utc": utc_now(),

        "status": status,

        "can_trade": (
            status
            == "RECONCILIATION_OK"
        ),

        # =============================================
        # OPERATION CONTEXT
        # =============================================
        "operation_id": operation_id,

        # =============================================
        # LOCAL STATE
        # =============================================
        "local": {

            "position_is_open": (
                local_is_open
            ),

            "position_symbol": (
                local_position.get(
                    "symbol"
                )
            ),

            "position_size": (
                local_position_size
            ),

            "runtime_position_state": (
                runtime_position_state
            ),

            "protection_level": (
                protection_status[
                    "protection_level"
                ]
            ),

            "pending_action": (
                pending_action
            )
        },

        # =============================================
        # EXCHANGE STATE
        # =============================================
        "exchange": {

            "market": exchange_snapshot.get(
                "market"
            ),

            "sol_available": (
                sol_available
            ),

            "sol_in_order": (
                sol_in_order
            ),

            "sol_total": (
                sol_total
            ),

            "usdc_available": (
                usdc_available
            )
        },

        # =============================================
        # PROTECTION
        # =============================================
        "protection": protection_status,

        # =============================================
        # LIFECYCLE EVENTS
        # =============================================
        "lifecycle_events": (
            lifecycle_events
        ),

        # =============================================
        # DIAGNOSTICS
        # =============================================
        "issues": issues,

        "warnings": warnings
    }


# =====================================================
# MAIN
# =====================================================
def main():

    local_state = load_json(
        LOCAL_STATE_PATH
    )

    exchange_snapshot = load_json(
        EXCHANGE_SNAPSHOT_PATH
    )

    report = reconcile(
        local_state,
        exchange_snapshot
    )

    save_json_atomic(
        report,
        RECONCILIATION_REPORT_PATH
    )

    print(
        json.dumps(
            report,
            indent=2
        )
    )

    print("")

    print(
        f"Reconciliation report saved to: "
        f"{RECONCILIATION_REPORT_PATH}"
    )


if __name__ == "__main__":
    main()
