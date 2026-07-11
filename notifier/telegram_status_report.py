#!/usr/bin/env python3

import os
import json
import socket
import urllib.request
import urllib.parse
import subprocess

from pathlib import Path
from datetime import datetime, timezone


# =========================================================
# CONFIG
# =========================================================

MARKET = os.getenv(
    "BITVAVO_MARKET",
    "SOL-USDC"
)

SERVICE_NAME = os.getenv(
    "BITVAVO_SERVICE",
    "bitvavo-live"
)

from state.state_manager import StateManager

state = StateManager().get_state()

MAX_LIVE_NOTIONAL_USDC = (
    state.get("runtime", {})
    .get("max_live_notional_usdc", "UNKNOWN")
)

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

STATE_PATH = (
    PROJECT_ROOT
    / "state"
    / "state.json"
)

RECONCILIATION_REPORT_PATH = (
    PROJECT_ROOT
    / "state"
    / "reconciliation_report.json"
)

ACTIVITY_LOG_PATH = (
    PROJECT_ROOT
    / "live"
    / "logs"
    / "activity"
    / "activity.log"
)

EVENTS_LOG_PATH = (
    PROJECT_ROOT
    / "live"
    / "logs"
    / "journal"
    / "events.jsonl"
)

SECRETS_DIR = (
    PROJECT_ROOT
    / "secrets"
)

TELEGRAM_BOT_TOKEN_PATH = (
    SECRETS_DIR
    / "telegram_bot_token.txt"
)

TELEGRAM_CHAT_ID_PATH = (
    SECRETS_DIR
    / "telegram_chat_id.txt"
)


# =========================================================
# TIME
# =========================================================

def utc_now():

    return datetime.now(
        timezone.utc
    )


def utc_now_text():

    return utc_now().strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


# =========================================================
# FILE HELPERS
# =========================================================

def read_json(path):

    if not path.exists():
        return {}

    try:

        with path.open(
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return {}


def read_secret(path):

    if not path.exists():

        raise FileNotFoundError(
            f"Missing secret: {path}"
        )

    return path.read_text(
        encoding="utf-8"
    ).strip()


# =========================================================
# COMMANDS
# =========================================================

def run_cmd(cmd, timeout=8):

    try:

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        stdout = (
            result.stdout
            .strip()
        )

        stderr = (
            result.stderr
            .strip()
        )

        return (
            stdout
            or stderr
            or ""
        )

    except Exception as exc:

        return f"ERROR: {exc}"


# =========================================================
# SYSTEM
# =========================================================

def get_service_info():

    active = run_cmd([
        "systemctl",
        "is-active",
        SERVICE_NAME
    ])

    pid = run_cmd([
        "systemctl",
        "show",
        SERVICE_NAME,
        "--property=MainPID",
        "--value"
    ])

    restarts = run_cmd([
        "systemctl",
        "show",
        SERVICE_NAME,
        "--property=NRestarts",
        "--value"
    ])

    memory = run_cmd([
        "systemctl",
        "show",
        SERVICE_NAME,
        "--property=MemoryCurrent",
        "--value"
    ])

    uptime = run_cmd([
        "bash",
        "-lc",
        "uptime -p"
    ])

    try:

        memory_mb = (
            f"{int(memory) / 1024 / 1024:.1f} MB"
        )

    except Exception:

        memory_mb = "n/a"

    return {

        "active": (
            active or "n/a"
        ),

        "pid": (
            pid or "n/a"
        ),

        "restarts": (
            restarts or "n/a"
        ),

        "memory_mb": memory_mb,

        "uptime": (
            uptime or "n/a"
        ),
    }


def get_system_info():

    hostname = socket.gethostname()

    loadavg = run_cmd([
        "bash",
        "-lc",
        "cat /proc/loadavg | awk '{print $1, $2, $3}'"
    ])

    free_ram = run_cmd([
        "bash",
        "-lc",
        "free -m | awk '/Mem:/ {print $4 \" MB\"}'"
    ])

    return {

        "hostname": hostname,

        "loadavg": (
            loadavg or "n/a"
        ),

        "free_ram": (
            free_ram or "n/a"
        ),
    }


# =========================================================
# MARKET
# =========================================================

def get_market_price():

    url = (
        "https://api.bitvavo.com/v2/ticker/price"
        f"?market={urllib.parse.quote(MARKET)}"
    )

    try:

        with urllib.request.urlopen(
            url,
            timeout=10
        ) as response:

            data = json.loads(
                response.read()
                .decode("utf-8")
            )

        if isinstance(data, dict):

            return data.get(
                "price",
                "n/a"
            )

        if (
            isinstance(data, list)
            and data
        ):

            return data[0].get(
                "price",
                "n/a"
            )

        return "n/a"

    except Exception as exc:

        return f"ERROR: {exc}"


# =========================================================
# STRATEGY SNAPSHOT
# =========================================================

def get_last_strategy_snapshot():

    if not ACTIVITY_LOG_PATH.exists():

        return {

            "price": "n/a",
            "indicators": (
                "No activity.log"
            ),
        }

    try:

        lines = (
            ACTIVITY_LOG_PATH
            .read_text(
                encoding="utf-8",
                errors="ignore"
            )
            .splitlines()
        )

        closed_price = None
        indicators = None

        for i in range(
            len(lines) - 1,
            -1,
            -1
        ):

            line = lines[i].strip()

            if (
                "💰 CLOSED PRICE"
                in line
            ):

                closed_price = line

                for j in range(
                    i + 1,
                    min(i + 4, len(lines))
                ):

                    if (
                        "📊 EMA9="
                        in lines[j]
                    ):

                        indicators = (
                            lines[j]
                            .strip()
                        )

                        break

                break

        return {

            "price": (
                closed_price
                or "No closed candle"
            ),

            "indicators": (
                indicators
                or "No indicators"
            ),
        }

    except Exception as exc:

        return {

            "price": (
                f"ERROR: {exc}"
            ),

            "indicators": "n/a",
        }


# =========================================================
# WS / EVENTS
# =========================================================

def read_jsonl_events():

    if not EVENTS_LOG_PATH.exists():
        return []

    events = []

    try:

        with EVENTS_LOG_PATH.open(
            "r",
            encoding="utf-8",
            errors="ignore"
        ) as f:

            for line in f:

                line = line.strip()

                if not line:
                    continue

                try:

                    events.append(
                        json.loads(line)
                    )

                except Exception:

                    continue

    except Exception:

        return []

    return events


def get_ws_status():

    events = read_jsonl_events()

    last_error = None
    stale = None

    for ev in events:

        event_type = ev.get(
            "event_type"
        )

        ts = ev.get(
            "logged_at_utc",
            "n/a"
        )

        payload = ev.get(
            "payload",
            {}
        )

        if event_type in {

            "LIVE_ERROR",
            "PAPER_ERROR"

        }:

            last_error = (

                f"{ts} | "

                f"{payload.get('error', 'n/a')}"

            )

        elif event_type in {

            "LIVE_STALE_CANDLE_STREAM",
            "STALE_CANDLE_STREAM",
            "STALE_CANDLE",
            "WS_STALE",
            "WATCHDOG_STALE"

        }:

            stale = ts

    return {

        "last_error": (
            last_error or "None"
        ),

        "last_stale": (
            stale or "None"
        ),
    }


# =========================================================
# POSITION
# =========================================================

def get_position_section(
    state,
    reconciliation
):

    position = state.get(
        "position",
        {}
    )

    exchange = reconciliation.get(
        "exchange",
        {}
    )

    local = reconciliation.get(
        "local",
        {}
    )

    balance = exchange.get(
        "usdc_available",
        "n/a"
    )

    is_open = position.get(
        "is_open",
        False
    )

    if not is_open:

        return {

            "balance": balance,

            "text": (
                "NONE"
            ),

            "runtime_state": (
                local.get(
                    "runtime_position_state",
                    "n/a"
                )
            ),

            "protection": (
                local.get(
                    "protection_level",
                    "n/a"
                )
            ),

            "pending_action": (
                local.get(
                    "pending_action",
                    "n/a"
                )
            ),
        }

    return {

        "balance": balance,

        "text": (
            f"{position.get('symbol')} "
            f"{position.get('side')}"
        ),

        "runtime_state": (
            position.get(
                "runtime_position_state",
                "n/a"
            )
        ),

        "protection": (
            position.get(
                "protection_level",
                "n/a"
            )
        ),

        "pending_action": (
            position.get(
                "pending_action",
                "n/a"
            )
        ),
    }


# =========================================================
# RECONCILIATION
# =========================================================

def get_reconciliation_text(
    reconciliation
):

    status = reconciliation.get(
        "status",
        "n/a"
    )

    issues = reconciliation.get(
        "issues",
        []
    )

    warnings = reconciliation.get(
        "warnings",
        []
    )

    return {

        "status": status,

        "issues": len(issues),

        "warnings": len(warnings),
    }


# =========================================================
# TELEGRAM
# =========================================================

def send_telegram_message(text):

    token = read_secret(
        TELEGRAM_BOT_TOKEN_PATH
    )

    chat_id = read_secret(
        TELEGRAM_CHAT_ID_PATH
    )

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    payload = urllib.parse.urlencode({

        "chat_id": chat_id,

        "text": text,

    }).encode("utf-8")

    with urllib.request.urlopen(
        url,
        data=payload,
        timeout=10
    ) as response:

        return (
            response.read()
            .decode("utf-8")
        )


# =========================================================
# BUILD REPORT
# =========================================================

def build_report():

    state = read_json(
        STATE_PATH
    )

    reconciliation = read_json(
        RECONCILIATION_REPORT_PATH
    )

    service = get_service_info()

    system = get_system_info()

    ws = get_ws_status()

    strategy = (
        get_last_strategy_snapshot()
    )

    position = (
        get_position_section(
            state,
            reconciliation
        )
    )

    recon = (
        get_reconciliation_text(
            reconciliation
        )
    )

    market_price = (
        get_market_price()
    )

    service_icon = (

        "🟢"

        if service["active"] == "active"

        else "🔴"

    )

    return (

        f"{service_icon} "
        f"BITVAVO BOT HEALTH REPORT\n\n"

        f"Time: "
        f"{utc_now_text()}\n\n"

        f"RUNTIME\n"
        f"--------\n"
        f"Service: "
        f"{service['active']}\n"

        f"PID: "
        f"{service['pid']}\n"

        f"Restarts: "
        f"{service['restarts']}\n"

        f"Memory: "
        f"{service['memory_mb']}\n"

        f"Uptime: "
        f"{service['uptime']}\n"

        f"Host: "
        f"{system['hostname']}\n"

        f"Free RAM: "
        f"{system['free_ram']}\n"

        f"CPU Load: "
        f"{system['loadavg']}\n\n"

        f"MARKET\n"
        f"------\n"
        f"Pair: "
        f"{MARKET}\n"

        f"Price: "
        f"{market_price}\n\n"

        f"CLOSED CANDLE\n"
        f"-------------\n"
        f"{strategy['price']}\n"
        f"{strategy['indicators']}\n\n"

        f"POSITION\n"
        f"--------\n"
        f"Exchange USDC: "
        f"{position['balance']}\n"

        f"Runtime Max Notional: "
        f"{MAX_LIVE_NOTIONAL_USDC} USDC\n"

        f"Position: "
        f"{position['text']}\n"

        f"Runtime State: "
        f"{position['runtime_state']}\n"

        f"Protection: "
        f"{position['protection']}\n"

        f"Pending Action: "
        f"{position['pending_action']}\n\n"

        f"RECONCILIATION\n"
        f"--------------\n"
        f"Status: "
        f"{recon['status']}\n"

        f"Issues: "
        f"{recon['issues']}\n"

        f"Warnings: "
        f"{recon['warnings']}\n\n"

        f"WS / WATCHDOG\n"
        f"-------------\n"
        f"Last WS Error: "
        f"{ws['last_error']}\n"

        f"Last Stale: "
        f"{ws['last_stale']}"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    report = build_report()

    send_telegram_message(
        report
    )

    print(
        "Telegram health report sent."
    )


if __name__ == "__main__":

    main()
