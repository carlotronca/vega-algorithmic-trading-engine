# state/recovery_manager.py

import os
import json
from datetime import datetime, timezone

from reconciliation.exchange_reconciliation import (
    reconcile
)

from state.state_manager import (
    StateManager
)


PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

EXCHANGE_SNAPSHOT_PATH = os.path.join(
    PROJECT_ROOT,
    "state",
    "exchange_snapshot.json"
)

RECOVERY_REPORT_PATH = os.path.join(
    PROJECT_ROOT,
    "state",
    "recovery_report.json"
)


class RecoveryManager:

    # =====================================================
    # INIT
    # =====================================================

    def __init__(
        self,
        state_manager=None
    ):

        self.state_manager = (
            state_manager
            if state_manager is not None
            else StateManager()
        )

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
    def log(self, message):

        print(
            f"[{self.utc_now()}] {message}"
        )

    # =====================================================
    # JSON HELPERS
    # =====================================================
    def load_json(self, path):

        if not os.path.exists(path):
            return None

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    def save_json_atomic(
        self,
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
    # RECOVERY POLICY
    # =====================================================
    def determine_recovery_policy(
        self,
        reconciliation_report
    ):

        issues = reconciliation_report.get(
            "issues",
            []
        )

        warnings = reconciliation_report.get(
            "warnings",
            []
        )

        lifecycle_events = (
            reconciliation_report.get(
                "lifecycle_events",
                []
            )
        )

        protection = reconciliation_report.get(
            "protection",
            {}
        )

        local = reconciliation_report.get(
            "local",
            {}
        )

        runtime_state = local.get(
            "runtime_position_state"
        )

        protection_level = protection.get(
            "protection_level"
        )

        pending_action = local.get(
            "pending_action"
        )

        # =================================================
        # SAFE RESUME
        # =================================================

        if (
            reconciliation_report.get(
                "status"
            )
            == "RECONCILIATION_OK"
        ):

            return {

                "policy": "SAFE_RESUME",

                "severity": "INFO",

                "runtime_action": (
                    "RESUME_RUNTIME"
                ),

                "requires_manual_intervention": (
                    False
                )
            }

        # =================================================
        # SL ONLY DEGRADATION
        # =================================================

        if (
            protection_level
            == "SL_ONLY"
        ):

            return {

                "policy": (
                    "DEGRADED_SL_ONLY"
                ),

                "severity": "WARNING",

                "runtime_action": (
                    "LOCK_NEW_ENTRIES"
                ),

                "requires_manual_intervention": (
                    False
                ),

                "recommended_next_action": (
                    "RECREATE_TAKE_PROFIT"
                )
            }

        # =================================================
        # TP ONLY => CRITICAL
        # =================================================

        if (
            protection_level
            == "TP_ONLY"
        ):

            return {

                "policy": (
                    "CRITICAL_TP_ONLY"
                ),

                "severity": "CRITICAL",

                "runtime_action": (
                    "EMERGENCY_LOCK_RUNTIME"
                ),

                "requires_manual_intervention": (
                    True
                ),

                "recommended_next_action": (
                    "RESTORE_STOP_LOSS"
                )
            }

        # =================================================
        # EXCHANGE STOP LOSS FILLED
        # =================================================

        if (
            "EXCHANGE_STOP_LOSS_FILLED"
            in lifecycle_events
        ):

            return {

                "policy": (
                    "EXCHANGE_STOP_LOSS_FILLED"
                ),

                "severity": "INFO",

                "runtime_action": (
                    "CLEAR_LOCAL_POSITION"
                ),

                "requires_manual_intervention": (
                    False
                )
            }



        # =================================================
        # UNPROTECTED POSITION
        # =================================================

        if (
            "POSITION_UNPROTECTED"
            in issues
        ):

            return {

                "policy": (
                    "CRITICAL_UNPROTECTED"
                ),

                "severity": "CRITICAL",

                "runtime_action": (
                    "LOCK_RUNTIME"
                ),

                "requires_manual_intervention": (
                    True
                ),

                "recommended_next_action": (
                    "MANUAL_POSITION_REVIEW"
                )
            }

        # =================================================
        # LOCAL/EXCHANGE MISMATCH
        # =================================================

        if (
            "LOCAL_POSITION_OPEN_BUT_NO_SOL_ON_EXCHANGE"
            in issues
        ):

            return {

                "policy": (
                    "ORPHAN_LOCAL_POSITION"
                ),

                "severity": "WARNING",

                "runtime_action": (
                    "CLEAR_LOCAL_POSITION"
                ),

                "requires_manual_intervention": (
                    False
                )
            }

        # =================================================
        # EXCHANGE POSITION WITHOUT LOCAL
        # =================================================

        if (
            "SOL_ON_EXCHANGE_BUT_LOCAL_POSITION_CLOSED"
            in issues
        ):

            return {

                "policy": (
                    "EXCHANGE_POSITION_UNKNOWN"
                ),

                "severity": "CRITICAL",

                "runtime_action": (
                    "LOCK_RUNTIME"
                ),

                "requires_manual_intervention": (
                    True
                ),

                "recommended_next_action": (
                    "MANUAL_EXCHANGE_REVIEW"
                )
            }

        # =================================================
        # STALE PENDING ACTION
        # =================================================

        if (
            "PENDING_ACTION_STALE_CREATE_TP"
            in warnings
        ):

            return {

                "policy": (
                    "STALE_PENDING_ACTION"
                ),

                "severity": "INFO",

                "runtime_action": (
                    "CLEAR_PENDING_ACTION"
                ),

                "requires_manual_intervention": (
                    False
                )
            }

        # =================================================
        # DEFAULT SAFE LOCK
        # =================================================

        return {

            "policy": (
                "UNKNOWN_RUNTIME_STATE"
            ),

            "severity": "CRITICAL",

            "runtime_action": (
                "LOCK_RUNTIME"
            ),

            "requires_manual_intervention": (
                True
            )
        }

    # =====================================================
    # APPLY RECOVERY POLICY
    # =====================================================
    def apply_recovery_policy(
        self,
        recovery_policy,
        reconciliation_report
    ):

        runtime_action = recovery_policy.get(
            "runtime_action"
        )

        self.log(
            f"APPLYING POLICY => "
            f"{runtime_action}"
        )

        # =================================================
        # SAFE RESUME
        # =================================================

        if runtime_action == "RESUME_RUNTIME":

            return {

                "recovery_status": (
                    "RUNTIME_RESUMED"
                ),

                "runtime_locked": False,

                "manual_intervention_required": (
                    False
                )
            }

        # =================================================
        # LOCK NEW ENTRIES
        # =================================================

        if runtime_action == "LOCK_NEW_ENTRIES":

            self.state_manager.lock(
                "DEGRADED_SL_ONLY_RUNTIME"
            )

            return {

                "recovery_status": (
                    "DEGRADED_RUNTIME_LOCKED"
                ),

                "runtime_locked": True,

                "manual_intervention_required": (
                    False
                )
            }

        # =================================================
        # CLEAR LOCAL POSITION
        # =================================================

        if runtime_action == "CLEAR_LOCAL_POSITION":

            self.state_manager.clear_position()

            return {

                "recovery_status": (
                    "ORPHAN_LOCAL_POSITION_CLEARED"
                ),

                "runtime_locked": False,

                "manual_intervention_required": (
                    False
                )
            }

        # =================================================
        # CLEAR PENDING ACTION
        # =================================================

        if runtime_action == "CLEAR_PENDING_ACTION":

            self.state_manager.transition_position_state(
                runtime_state=(
                    "POSITION_FULLY_PROTECTED"
                ),
                protection_level="FULL",
                pending_action="NONE"
            )

            return {

                "recovery_status": (
                    "PENDING_ACTION_CLEARED"
                ),

                "runtime_locked": False,

                "manual_intervention_required": (
                    False
                )
            }

        # =================================================
        # LOCK RUNTIME
        # =================================================

        self.state_manager.lock(
            runtime_action
        )

        return {

            "recovery_status": (
                "RUNTIME_LOCKED"
            ),

            "runtime_locked": True,

            "manual_intervention_required": (
                True
            )
        }

    # =====================================================
    # RECOVERY ENTRYPOINT
    # =====================================================
    def recover(self):

        self.log("=" * 80)

        self.log(
            "RECOVERY MANAGER START"
        )

        self.log("=" * 80)

        # =================================================
        # LOAD STATES
        # =================================================

        local_state = (
            self.state_manager.get_state()
        )

        exchange_snapshot = self.load_json(
            EXCHANGE_SNAPSHOT_PATH
        )

        # =================================================
        # RECONCILIATION
        # =================================================

        reconciliation_report = reconcile(
            local_state=local_state,
            exchange_snapshot=(
                exchange_snapshot
            )
        )

        # =================================================
        # DETERMINE POLICY
        # =================================================

        recovery_policy = (
            self.determine_recovery_policy(
                reconciliation_report
            )
        )

        # =================================================
        # APPLY POLICY
        # =================================================

        recovery_result = (
            self.apply_recovery_policy(
                recovery_policy,
                reconciliation_report
            )
        )

        # =================================================
        # FINAL REPORT
        # =================================================

        final_report = {

            "timestamp_utc": (
                self.utc_now()
            ),

            "reconciliation": (
                reconciliation_report
            ),

            "recovery_policy": (
                recovery_policy
            ),

            "recovery_result": (
                recovery_result
            )
        }

        # =================================================
        # SAVE REPORT
        # =================================================

        self.save_json_atomic(
            final_report,
            RECOVERY_REPORT_PATH
        )

        # =================================================
        # LOG RESULT
        # =================================================

        self.log(
            f"RECOVERY STATUS => "
            f"{recovery_result.get('recovery_status')}"
        )

        self.log(
            "=" * 80
        )

        return final_report


# =====================================================
# MAIN
# =====================================================
def main():

    manager = RecoveryManager()

    report = manager.recover()

    print(
        json.dumps(
            report,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
