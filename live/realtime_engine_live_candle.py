import os
import sys
import runpy
import subprocess
from datetime import datetime, timezone


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

PREFLIGHT_PATH = os.path.join(PROJECT_ROOT, "live", "live_preflight.py")
FROZEN_RUNTIME_PATH = os.path.join(
    PROJECT_ROOT,
    "live",
    "realtime_engine_paper_state_and_safety.py"
)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def main():
    print("=" * 80)
    print(f"[{utc_now()}] LIVE CANDLE STARTED")
    print("Mode: LIVE_CANDLE")
    print("API_WRITE: OFF")
    print("Execution: DISABLED")
    print("=" * 80)

    print("Running mandatory live preflight...")
    result = subprocess.run(
        [sys.executable, PREFLIGHT_PATH],
        cwd=PROJECT_ROOT
    )

    if result.returncode != 0:
        print("=" * 80)
        print("LIVE CANDLE BLOCKED")
        print("Reason: live_preflight.py failed")
        print("=" * 80)
        sys.exit(1)

    print("=" * 80)
    print("LIVE PREFLIGHT PASSED")
    print("Starting frozen candle runtime...")
    print("=" * 80)

    os.environ["BOT_MODE"] = "LIVE_CANDLE"
    os.environ["API_WRITE"] = "false"

    runpy.run_path(FROZEN_RUNTIME_PATH, run_name="__main__")


if __name__ == "__main__":
    main()
