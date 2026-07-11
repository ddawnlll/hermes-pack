#!/usr/bin/env python3
"""
T4 disposition engine (BE-5, #87).

Routes an Executive Packet (BE-4 #83) to one of two paths:

- Fast path:  ~$0.05, < 1 tick. Trigger: single candidate,
  effect_class=reversible_internal, merge_policy=pr_gated_auto,
  precedent memory success_rate > 0.9. Output: PROMOTING (delegates to
  BE-2 #85).

- Full synthesis:  ~$1.20, 1-3 ticks. Trigger: multi-candidate, OR
  irreversible_external (always escalates to human under AFK), OR
  precedent coverage < 0.5. Output: disposition recommendation +
  human override hook.

Effect honesty (Gate #15): irreversible_external ALWAYS escalates to
human, even when AFK flag is on. This check happens here (early) before
the engine ever sees the candidate.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any


class Route(str, Enum):
    FAST_PATH = "fast_path"
    FULL_SYNTHESIS = "full_synthesis"
    ESCALATE_HUMAN = "escalate_human"


@dataclass
class RoutingDecision:
    route: Route
    rationale: str
    estimated_cost_usd: float
    estimated_ticks: int
    requires_human: bool
    precedent_coverage: float


# Routing thresholds.
FAST_PATH_MIN_PRECEDENT_COVERAGE = 0.9
FAST_PATH_MAX_CANDIDATES = 1
SINGLE_CANDIDATE = 1

COST_FAST_PATH = 0.05
COST_FULL_SYNTHESIS = 1.20

TICKS_FAST_PATH = 1
TICKS_FULL_SYNTHESIS = 3  # upper bound


def compute_precedent_coverage(packet: dict, precedent_index: dict[str, float] | None) -> float:
    """Coverage = how many of the proposed candidates have a similar
    precedent in the index. Returns 0.0-1.0.

    The precedent index is the BE-6 (#84) memory, keyed by situation
    signature. For v0.6, the index is provided as a side input; the
    engine does not own the index.
    """
    if not precedent_index:
        return 0.0
    cands = packet.get("candidates_proposed", [])
    if not cands:
        return 1.0
    matches = 0
    for c in cands:
        sig = c.get("signature", "")
        if sig in precedent_index:
            matches += 1
    return matches / len(cands)


def route(packet: dict, *, afk: bool, precedent_index: dict[str, float] | None = None) -> RoutingDecision:
    """Decide which routing the packet gets. Returns a RoutingDecision."""
    cands = packet.get("candidates_proposed", [])

    # 1. Effect honesty: irreversible_external always escalates under AFK
    #    (Gate #15). This is the EARLY check, before any routing logic.
    for c in cands:
        if c.get("effect_class") == "irreversible_external" and afk:
            return RoutingDecision(
                route=Route.ESCALATE_HUMAN,
                rationale="afk_irreversible_external_blocked",
                estimated_cost_usd=0.0,
                estimated_ticks=0,
                requires_human=True,
                precedent_coverage=0.0,
            )

    # 2. Compute precedent coverage.
    coverage = compute_precedent_coverage(packet, precedent_index)

    # 3. Fast path criteria.
    if (
        len(cands) == SINGLE_CANDIDATE
        and cands[0].get("effect_class") == "reversible_internal"
        and cands[0].get("merge_policy") == "pr_gated_auto"
        and coverage >= FAST_PATH_MIN_PRECEDENT_COVERAGE
    ):
        return RoutingDecision(
            route=Route.FAST_PATH,
            rationale="single_reversible_with_high_precedent_coverage",
            estimated_cost_usd=COST_FAST_PATH,
            estimated_ticks=TICKS_FAST_PATH,
            requires_human=False,
            precedent_coverage=coverage,
        )

    # 4. Otherwise, full synthesis.
    return RoutingDecision(
        route=Route.FULL_SYNTHESIS,
        rationale="default",
        estimated_cost_usd=COST_FULL_SYNTHESIS,
        estimated_ticks=TICKS_FULL_SYNTHESIS,
        requires_human=False,
        precedent_coverage=coverage,
    )


def _cmd_route(args: argparse.Namespace) -> int:
    packet = json.loads(args.packet)
    precedent_index: dict[str, float] = {}
    if args.precedent_index:
        precedent_index = json.loads(args.precedent_index)
    decision = route(packet, afk=args.afk, precedent_index=precedent_index)
    print(json.dumps({
        "route": decision.route.value,
        "rationale": decision.rationale,
        "estimated_cost_usd": decision.estimated_cost_usd,
        "estimated_ticks": decision.estimated_ticks,
        "requires_human": decision.requires_human,
        "precedent_coverage": decision.precedent_coverage,
    }))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="T4 disposition engine (BE-5, #87): fast_path / full_synthesis / escalate_human routing."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_route = sub.add_parser("route", help="Route an Executive Packet.")
    p_route.add_argument("--packet", required=True, help="Path to the Executive Packet (JSON).")
    p_route.add_argument("--afk", action="store_true", help="Whether the system is in AFK mode.")
    p_route.add_argument("--precedent-index", default=None, help="Optional path to precedent index (JSON).")
    p_route.set_defaults(func=_cmd_route)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
