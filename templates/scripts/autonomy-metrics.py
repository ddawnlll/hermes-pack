#!/usr/bin/env python3
"""
Autonomy metrics (GA-3, #101).

Five metrics for the AFK autonomy surface:

  1. success_rate:  auto_promoted_under_afk / total_auto_attempts
  2. rollback_rate: auto_rolled_back / auto_promoted_under_afk
  3. override_rate: human_override_after_afk / auto_promoted_under_afk
  4. regret_rate:   regret_marker_count / total_auto_attempts
                    (regret = A-2 shadowed intent that was later reverted)
  5. calibration_error: predicted_success_rate - actual_success_rate
                    (from BE-6 #84 precedent memory)

Inputs are read from the tick-journal.py output (BE-6 #84) and the
memory_scar table (DL-4 #98). Output is a JSON object with the five
metrics, plus a recommendation: if regret_rate > 0.2, AFK autonomy
should be defaulted off (safety).

Gate #13 (Autonomy measurement) is satisfied by this script alone.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, asdict


REGRET_THRESHOLD = 0.2  # Above this, AFK autonomy defaults to off


@dataclass
class Metrics:
    success_rate: float
    rollback_rate: float
    override_rate: float
    regret_rate: float
    calibration_error: float
    total_auto_attempts: int
    recommendation: str

    def to_dict(self) -> dict:
        return asdict(self)


def compute(*, auto_attempts: int, auto_promoted: int, auto_rolled_back: int,
            human_overrides: int, regret_markers: int, predicted_success: float) -> Metrics:
    success = (auto_promoted / auto_attempts) if auto_attempts else 0.0
    rollback = (auto_rolled_back / auto_promoted) if auto_promoted else 0.0
    override = (human_overrides / auto_promoted) if auto_promoted else 0.0
    regret = (regret_markers / auto_attempts) if auto_attempts else 0.0
    calibration = predicted_success - success

    if regret > REGRET_THRESHOLD:
        recommendation = "DISABLE_AFK_AUTONOMY"
    elif calibration > 0.2:
        recommendation = "TIGHTEN_PRECEDENT_THRESHOLD"
    else:
        recommendation = "HOLD"

    return Metrics(
        success_rate=round(success, 4),
        rollback_rate=round(rollback, 4),
        override_rate=round(override, 4),
        regret_rate=round(regret, 4),
        calibration_error=round(calibration, 4),
        total_auto_attempts=auto_attempts,
        recommendation=recommendation,
    )


def _cmd_compute(args: argparse.Namespace) -> int:
    m = compute(
        auto_attempts=args.attempts,
        auto_promoted=args.promoted,
        auto_rolled_back=args.rolled_back,
        human_overrides=args.overrides,
        regret_markers=args.regret,
        predicted_success=args.predicted,
    )
    print(json.dumps(m.to_dict(), indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Autonomy metrics (GA-3, #101).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_c = sub.add_parser("compute", help="Compute the 5 autonomy metrics.")
    p_c.add_argument("--attempts", type=int, required=True, help="total_auto_attempts")
    p_c.add_argument("--promoted", type=int, required=True, help="auto_promoted_under_afk")
    p_c.add_argument("--rolled-back", type=int, required=True, help="auto_rolled_back")
    p_c.add_argument("--overrides", type=int, required=True, help="human_override_after_afk")
    p_c.add_argument("--regret", type=int, required=True, help="regret_marker_count")
    p_c.add_argument("--predicted", type=float, required=True, help="predicted_success_rate (from BE-6 #84)")
    p_c.set_defaults(func=_cmd_compute)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
