#!/usr/bin/env python3

import os
import json
import socket
import urllib.request
import urllib.parse
import subprocess
from pathlib import Path
from datetime import datetime, timezone


MARKET = os.getenv("BITVAVO_MARKET", "SOL-USDC")
SERVICE_NAME = os.getenv("BITVAVO_SERVICE", "bitvavo-live")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

STATE_PATH = PROJECT_ROOT / "state" / "state.json"
ACTIVITY_LOG_PATH = PROJECT_ROOT / "live" / "logs" / "activity" / "activity.log"
EVENTS_LOG_PATH = PROJECT_ROOT / "live" / "logs" / "journal" / "events.jsonl"

RECONCILIATION_REPORT_PATH = PROJECT_ROOT / "state" / "reconciliation_report.json"

SECRETS_DIR = PROJECT_ROOT / "secrets"
TELEGRAM_BOT_TOKEN_PATH = SECRETS_DIR / "telegram_bot_token.txt"
TELEGRAM_CHAT_ID_PATH = SECRETS_DIR / "telegram_chat_id.txt"


def utc_now():
    return datetime.now(timezone.utc)


def utc_now_text():
    return utc_now().strftime("%Y-%m-%d %H:%M:%S UTC")


def read_secret(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Secret file non trovato: {path}")
    return path.read_text(encoding="utf-8").strip()


def run_cmd(cmd, timeout=8):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        return stdout or stderr or ""
    except Exception as exc:
        return f"ERROR: {exc}"


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return None


def read_state():
    if not STATE_PATH.exists():
        return {}

    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def read_reconciliation_report():
    if not RECONCILIATION_REPORT_PATH.exists():
        return {}

    try:
        with RECONCILIATION_REPORT_PATH.open(
            "r",
            encoding="utf-8"
        ) as f:
            return json.load(f)

    except Exception:
        return {}

def get_mode_info(state):
    bot = state.get("bot", {})

    mode = bot.get("mode", "n/a")
    api_write = bot.get("api_write", "n/a")
    running = bot.get("is_running", "n/a")

    api_text = "API WRITE ON" if api_write is True else "API WRITE OFF" if api_write is False else "API WRITE n/a"

    if str(mode).lower() == "live" or api_write is True:
        mode_text = "LIVE REAL"
    elif str(mode).lower() == "paper":
        mode_text = "PAPER"
    else:
        mode_text = str(mode).upper()

    return mode_text, api_text, running


def get_service_info():
    active = run_cmd(["systemctl", "is-active", SERVICE_NAME])

    active_since = run_cmd([
        "systemctl", "show", SERVICE_NAME,
        "--property=ActiveEnterTimestamp", "--value",
    ])

    memory = run_cmd([
        "systemctl", "show", SERVICE_NAME,
        "--property=MemoryCurrent", "--value",
    ])

    main_pid = run_cmd([
        "systemctl", "show", SERVICE_NAME,
        "--property=MainPID", "--value",
    ])

    restart_count = run_cmd([
        "systemctl", "show", SERVICE_NAME,
        "--property=NRestarts", "--value",
    ])

    try:
        memory_mb = f"{int(memory) / 1024 / 1024:.1f} MB"
    except Exception:
        memory_mb = "n/a"

    return {
        "active": active or "n/a",
        "active_since": active_since or "n/a",
        "memory_mb": memory_mb,
        "main_pid": main_pid or "n/a",
        "restart_count": restart_count or "n/a",
    }


def get_system_resources():
    hostname = socket.gethostname()
    ram_free = run_cmd(["bash", "-lc", "free -m | awk '/Mem:/ {print $4 \" MB\"}'"])
    loadavg = run_cmd(["bash", "-lc", "cat /proc/loadavg | awk '{print $1, $2, $3}'"])
    uptime_short = run_cmd(["bash", "-lc", "uptime -p"])

    return {
        "hostname": hostname,
        "ram_free": ram_free or "n/a",
        "loadavg": loadavg or "n/a",
        "uptime": uptime_short or "n/a",
    }


def get_kernel_messages():
    output = run_cmd([
        "bash", "-lc",
        "journalctl -k -p warning..alert --since '3 hours ago' --no-pager -n 3"
    ], timeout=10)

    if not output:
        return "No important kernel messages"

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    return " | ".join(lines[-3:]) if lines else "No important kernel messages"


def get_bitvavo_price():
    url = f"https://api.bitvavo.com/v2/ticker/price?market={urllib.parse.quote(MARKET)}"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        if isinstance(data, dict):
            return data.get("price", "n/a")

        if isinstance(data, list) and data:
            return data[0].get("price", "n/a")

        return "n/a"

    except Exception as exc:
        return f"ERROR: {exc}"


def get_last_closed_candle():
    if not ACTIVITY_LOG_PATH.exists():
        return {
            "raw": "activity.log non trovato",
            "timestamp": "n/a",
            "open": "n/a",
            "high": "n/a",
            "low": "n/a",
            "close": "n/a",
            "volume": "n/a",
        }

    try:
        lines = ACTIVITY_LOG_PATH.read_text(
            encoding="utf-8",
            errors="ignore",
        ).splitlines()

        markers = [
            "CLOSED CANDLE SENT TO LIVE ENGINE",
            "CLOSED CANDLE SENT TO PAPER ENGINE",
        ]

        for i in range(len(lines) - 1, -1, -1):
            if any(marker in lines[i] for marker in markers):
                candle_line = None

                for j in range(i + 1, min(i + 6, len(lines))):
                    if MARKET in lines[j] and " O=" in lines[j] and " C=" in lines[j]:
                        candle_line = lines[j].strip()
                        break

                data = {
                    "raw": candle_line or lines[i].strip(),
                    "timestamp": "n/a",
                    "open": "n/a",
                    "high": "n/a",
                    "low": "n/a",
                    "close": "n/a",
                    "volume": "n/a",
                }

                if not candle_line:
                    return data

                for part in candle_line.split():
                    if part.startswith("ts="):
                        data["timestamp"] = part.replace("ts=", "")
                    elif part.startswith("O="):
                        data["open"] = part.replace("O=", "")
                    elif part.startswith("H="):
                        data["high"] = part.replace("H=", "")
                    elif part.startswith("L="):
                        data["low"] = part.replace("L=", "")
                    elif part.startswith("C="):
                        data["close"] = part.replace("C=", "")
                    elif part.startswith("V="):
                        data["volume"] = part.replace("V=", "")

                return data

        return {
            "raw": "nessuna candela chiusa trovata nel log corrente",
            "timestamp": "n/a",
            "open": "n/a",
            "high": "n/a",
            "low": "n/a",
            "close": "n/a",
            "volume": "n/a",
        }

    except Exception as exc:
        return {
            "raw": f"ERROR reading activity.log: {exc}",
            "timestamp": "n/a",
            "open": "n/a",
            "high": "n/a",
            "low": "n/a",
            "close": "n/a",
            "volume": "n/a",
        }


def get_position_info(state, reconciliation):
    position = state.get("position", {})
    daily = state.get("daily", {})
    account = state.get("account", {})

    exchange = reconciliation.get("exchange", {})

    local = reconciliation.get("local", {})

    current_balance = (
        exchange.get("usdc_available")
        or account.get("balance")
        or account.get("paper_balance")
        or daily.get("current_balance")
        or daily.get("balance")
        or daily.get("start_balance")
        or "n/a"
    )

    runtime_position_open = local.get("position_is_open")

    if runtime_position_open is False:
        return {
            "balance": current_balance,
            "position_text": "None",
        }


    symbol = position.get("symbol", MARKET)
    side = position.get("side", "n/a")
    entry = position.get("entry_price", "n/a")
    size = position.get("size", "n/a")
    sl = position.get("stop_loss", "n/a")
    tp = position.get("take_profit", "n/a")
    entry_ts = position.get("entry_timestamp", "n/a")

    return {
        "balance": current_balance,
        "position_text": (
            f"OPEN {symbol} {side}\n"
            f"Entry: {entry}\n"
            f"Size: {size}\n"
            f"TP: {tp}\n"
            f"SL: {sl}\n"
            f"Entry time: {entry_ts}"
        ),
    }


def read_jsonl_events():
    if not EVENTS_LOG_PATH.exists():
        return []

    events = []

    try:
        with EVENTS_LOG_PATH.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    events.append(json.loads(line))
                except Exception:
                    continue

    except Exception:
        return []

    return events


def get_ws_status_text():
    events = read_jsonl_events()

    last_error = None
    last_restart = None
    last_stale = None

    for ev in events:
        event_type = ev.get("event_type")
        ts = ev.get("logged_at_utc", "n/a")
        payload = ev.get("payload", {})

        if event_type in {"LIVE_ERROR", "PAPER_ERROR"}:
            last_error = {
                "time": ts,
                "reason": payload.get("error", "n/a"),
            }

        elif event_type in {"LIVE_STARTED", "PAPER_STARTED"}:
            last_restart = {
                "time": ts,
                "reason": event_type,
            }

        elif event_type in {
            "LIVE_STALE_CANDLE_STREAM",
            "STALE_CANDLE_STREAM",
            "STALE_CANDLE",
            "WS_STALE",
            "WATCHDOG_STALE",
        }:
            last_stale = {
                "time": ts,
                "reason": json.dumps(payload, ensure_ascii=False),
            }

    return {
        "last_ws_fail_time": last_error["time"] if last_error else "None",
        "last_ws_fail_reason": last_error["reason"] if last_error else "None",
        "last_restart_time": last_restart["time"] if last_restart else "n/a",
        "last_stale": (
            f"{last_stale['time']} | {last_stale['reason']}"
            if last_stale else "None recorded"
        ),
    }


def get_last_login():
    output = run_cmd(["bash", "-lc", "last -w -n 5 | grep -v 'wtmp begins' | head -n 1"])
    return output or "n/a"


def send_telegram_message(text):
    telegram_bot_token = read_secret(TELEGRAM_BOT_TOKEN_PATH)
    telegram_chat_id = read_secret(TELEGRAM_CHAT_ID_PATH)

    url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"

    payload = urllib.parse.urlencode({
        "chat_id": telegram_chat_id,
        "text": text,
    }).encode("utf-8")

    with urllib.request.urlopen(url, data=payload, timeout=10) as response:
        return response.read().decode("utf-8")


def build_report():
    state = read_state()

    reconciliation = read_reconciliation_report()

    mode_text, api_text, running = get_mode_info(state)

    service = get_service_info()
    system = get_system_resources()
    kernel = get_kernel_messages()

    price = get_bitvavo_price()
    candle = get_last_closed_candle()

    position = get_position_info(
        state,
        reconciliation
    )

    ws = get_ws_status_text()
    last_login = get_last_login()

    service_icon = "🟢" if service["active"] == "active" else "🔴"

    return (
        f"{service_icon} BITVAVO BOT HEALTH REPORT\n"
        f"Time: {utc_now_text()}\n"
        f"Mode: {mode_text} / {api_text}\n\n"

        f"1) SERVER\n"
        f"I am alive: YES\n"
        f"Host: {system['hostname']}\n"
        f"Service: {SERVICE_NAME} = {service['active']}\n"
        f"Bot running flag: {running}\n"
        f"PID: {service['main_pid']}\n"
        f"Restarts: {service['restart_count']}\n"
        f"Active since: {service['active_since']}\n"
        f"Process RAM: {service['memory_mb']}\n"
        f"Free RAM: {system['ram_free']}\n"
        f"CPU load: {system['loadavg']}\n"
        f"Uptime: {system['uptime']}\n"
        f"Kernel: {kernel}\n\n"

        f"2) MARKET\n"
        f"Pair: {MARKET}\n"
        f"Current price: {price}\n"
        f"Last closed candle:\n"
        f"C: {candle['close']} | H: {candle['high']} | L: {candle['low']} | V: {candle['volume']}\n"
        f"Timestamp: {candle['timestamp']}\n\n"

        f"3) POSITION\n"
        f"Balance: {position['balance']}\n"
        f"Position: {position['position_text']}\n\n"

        f"4) WEBSOCKET / STALE / RESTART\n"
        f"Last WS fail: {ws['last_ws_fail_time']}\n"
        f"Reason: {ws['last_ws_fail_reason']}\n"
        f"Last bot restart: {ws['last_restart_time']}\n"
        f"Last stale: {ws['last_stale']}\n\n"

        f"5) MACHINE ACCESS\n"
        f"Last login: {last_login}"
    )


def main():
    report = build_report()
    send_telegram_message(report)
    print("Telegram LIVE health report sent.")


if __name__ == "__main__":
    main()
