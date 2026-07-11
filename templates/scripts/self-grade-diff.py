#!/usr/bin/env python3
"""
self-grade-diff.py — $0 Deterministic Self-Grade Diff Gate (Issue #28)

Compares the orchestrator's proposed verdict against what the raw evidence
bundle supports. Blocks when the verdict is more optimistic than evidence
allows (e.g. FAIL softened to PARTIAL to keep the loop moving).

Fail-closed: on any error, outputs {"verdict": "FAIL", "error": "..."} and
exits with code 1.

Usage (stdin JSON):
  {
    "praxis_exit_code": 0,          # 2 = Praxis FAIL
    "evidence_bundle_status": "PASS", # or "FAIL"
    "acceptance_met": 5,             # criteria satisfied
    "total_criteria": 5,             # total criteria
    "orchestrator_verdict": "PASS"   # or "FAIL" / "HOLD" / "PARTIAL"
  }

Output (stdout JSON):
  {
    "verdict": "FAIL" | "PASS",
    "mechanical_verdict": "FAIL" | "HOLD" | "PASS",
    "orchestrator_verdict": "...",
    "components": { ... },
    "error": "..."
  }

Exit codes:
  0 = gate passed (orchestrator not more optimistic than evidence)
  1 = gate blocked (verdict mismatch or error)
"""
import json
import sys

# Optimism ordering: FAIL=0, HOLD=1, PASS=2
OPTIMISM_RANK = {"FAIL": 0, "HOLD": 1, "PASS": 2}


def compute_mechanical_verdict(praxis_exit_code, evidence_bundle_status,
                               acceptance_met, total_criteria):
    """Deterministic mechanical verdict from raw evidence."""
    mechanical = "PASS"
    reasons = []

    # Rule 1: praxis_exit_code == 2 → FAIL
    if praxis_exit_code == 2:
        mechanical = "FAIL"
        reasons.append("praxis_exit_code=2 (Praxis FAIL)")

    # Rule 1b: empty/null exit code → FAIL
    if praxis_exit_code is None or praxis_exit_code == "":
        mechanical = "FAIL"
        reasons.append("praxis_exit_code is empty (missing Praxis result)")

    # Rule 2: evidence_bundle_status == FAIL → FAIL
    if evidence_bundle_status == "FAIL":
        mechanical = "FAIL"
        reasons.append("evidence_bundle_status=FAIL")

    # Rule 3: acceptance not fully met → HOLD (only if not already FAIL)
    if mechanical != "FAIL":
        try:
            if int(acceptance_met) < int(total_criteria):
                mechanical = "HOLD"
                reasons.append(
                    f"acceptance_criteria_met ({acceptance_met}/{total_criteria})"
                    f" < total_criteria ({total_criteria})"
                )
        except (ValueError, TypeError):
            pass

    if not reasons:
        reasons.append(
            f"all checks passed (praxis_exit_code={praxis_exit_code}, "
            f"evidence_bundle_status={evidence_bundle_status}, "
            f"acceptance_criteria_met={acceptance_met}/{total_criteria})"
        )

    return {
        "mechanical_verdict": mechanical,
        "components": {
            "praxis_exit_code": praxis_exit_code,
            "evidence_bundle_status": evidence_bundle_status,
            "acceptance_criteria_met": acceptance_met,
            "total_criteria": total_criteria,
            "reason": "; ".join(reasons),
        },
    }


def check_orchestrator_optimism(mechanical_verdict, orchestrator_verdict):
    """Compare orchestrator verdict against mechanical verdict."""
    for name, val in [("mechanical", mechanical_verdict),
                      ("orchestrator", orchestrator_verdict)]:
        if val not in OPTIMISM_RANK:
            return {
                "verdict": "FAIL",
                "orchestrator": orchestrator_verdict,
                "mechanical": mechanical_verdict,
                "error": f"Invalid {name}_verdict '{val}'. Must be FAIL, HOLD, or PASS.",
            }

    mechanical_rank = OPTIMISM_RANK[mechanical_verdict]
    orchestrator_rank = OPTIMISM_RANK[orchestrator_verdict]

    # Invariant: orchestrator_verdict <= mechanical_verdict
    if orchestrator_rank > mechanical_rank:
        return {
            "verdict": "FAIL",
            "orchestrator": orchestrator_verdict,
            "mechanical": mechanical_verdict,
            "optimism_rank": {
                "orchestrator": orchestrator_rank,
                "mechanical": mechanical_rank,
            },
            "error": (
                f"Orchestrator verdict '{orchestrator_verdict}' (rank {orchestrator_rank}) "
                f"is more optimistic than mechanical verdict '{mechanical_verdict}' "
                f"(rank {mechanical_rank}). "
                f"Orchestrator cannot be more optimistic than evidence."
            ),
        }

    return {
        "verdict": "PASS",
        "orchestrator": orchestrator_verdict,
        "mechanical": mechanical_verdict,
        "optimism_rank": {
            "orchestrator": orchestrator_rank,
            "mechanical": mechanical_rank,
        },
        "error": "",
    }


def main():
    """Read JSON from stdin, compute gate verdict, print result."""
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            result = {
                "verdict": "FAIL",
                "error": "No input received on stdin",
            }
            print(json.dumps(result))
            sys.exit(1)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            result = {
                "verdict": "FAIL",
                "error": f"Invalid JSON input: {e}",
            }
            print(json.dumps(result))
            sys.exit(1)

        # Extract inputs with defaults
        praxis_exit_code = data.get("praxis_exit_code", None)
        evidence_bundle_status = data.get("evidence_bundle_status", "PASS")
        acceptance_met = data.get("acceptance_met", 0)
        total_criteria = data.get("total_criteria", 0)
        orchestrator_verdict = data.get("orchestrator_verdict", None)

        if orchestrator_verdict is None:
            result = {
                "verdict": "FAIL",
                "error": "Missing required field: orchestrator_verdict",
            }
            print(json.dumps(result))
            sys.exit(1)

        # Normalize PARTIAL → HOLD (PARTIAL is orchestrator-specific label)
        if orchestrator_verdict.upper() == "PARTIAL":
            orchestrator_verdict = "HOLD"

        mechanical = compute_mechanical_verdict(
            praxis_exit_code, evidence_bundle_status,
            str(acceptance_met), str(total_criteria)
        )

        check = check_orchestrator_optimism(
            mechanical["mechanical_verdict"], orchestrator_verdict.upper()
        )

        output = {
            "verdict": check["verdict"],
            "mechanical_verdict": mechanical["mechanical_verdict"],
            "orchestrator_verdict": orchestrator_verdict.upper(),
            "components": mechanical["components"],
        }
        if check.get("error"):
            output["error"] = check["error"]

        print(json.dumps(output, indent=2))
        sys.exit(0 if check["verdict"] == "PASS" else 1)

    except Exception as e:
        result = {
            "verdict": "FAIL",
            "error": f"Unexpected error: {e}",
        }
        print(json.dumps(result))
        sys.exit(1)


if __name__ == "__main__":
    main()
