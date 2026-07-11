#!/usr/bin/env python3
"""
AFK budget limits (GA-2, #102).

Two budgets:
  - max_promotions_per_afk_session: int, default 10
  - max_spend_usd_per_afk_session:   float, default 5.0

When either budget is exhausted, the AFK autonomy is auto-disabled
(GA-1 #99 auto_when_afk is set to False), the user is notified
through the attention queue (CP-2 #90 critical), and AFK is paused
for `cooldown_after_budget_exceeded` (default 30 minutes) before
human acknowledgment is required to resume.

State is persisted in templates/control.yaml (canonical) and
db.control_state (mirror, A-4 #79 OR'ling).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass


DEFAULT_MAX_PROMOTIONS = 10
DEFAULT_MAX_SPEND_USD = 5.0
DEFAULT_COOLDOWN_MIN = 30


@dataclass
class BudgetState:
    promotions_used: int = 0
    spend_usd: float = 0.0
    exhausted: bool = False
    cooldown_until: str = ""  # ISO-8601

    def to_dict(self) -> dict:
        return {
            "promotions_used": self.promotions_used,
            "spend_usd": self.spend_usd,
            "exhausted": self.exhausted,
            "cooldown_until": self.cooldown_until,
        }


def check_budget(
    state: BudgetState,
    *,
    cost_usd: float,
    promotions: int = 1,
    max_promotions: int = DEFAULT_MAX_PROMOTIONS,
    max_spend_usd: float = DEFAULT_MAX_SPEND_USD,
) -> dict:
    """Returns a verdict: ALLOWED + new state, or REJECTED + new state.

    The caller (BE-2 #85 + GA-1 #99) is responsible for the actual
    write back to state.
    """
    if state.exhausted:
        return {
            "verdict": "REJECTED",
            "reason": "budget_exhausted",
            "state": state.to_dict(),
        }
    if state.promotions_used + promotions > max_promotions:
        state.exhausted = True
        return {
            "verdict": "REJECTED",
            "reason": "max_promotions_exceeded",
            "state": state.to_dict(),
        }
    if state.spend_usd + cost_usd > max_spend_usd:
        state.exhausted = True
        return {
            "verdict": "REJECTED",
            "reason": "max_spend_usd_exceeded",
            "state": state.to_dict(),
        }
    state.promotions_used += promotions
    state.spend_usd += cost_usd
    return {
        "verdict": "ALLOWED",
        "reason": "ok",
        "state": state.to_dict(),
    }


def reset(_: BudgetState) -> BudgetState:
    """Reset the budget (called at the start of a new AFK session)."""
    return BudgetState()


def _cmd_check(args: argparse.Namespace) -> int:
    state = BudgetState(**json.loads(args.state))
    result = check_budget(
        state,
        cost_usd=args.cost,
        promotions=args.promotions,
        max_promotions=args.max_promotions,
        max_spend_usd=args.max_spend_usd,
    )
    print(json.dumps(result))
    return 0 if result["verdict"] == "ALLOWED" else 1


def _cmd_reset(_: argparse.Namespace) -> int:
    state = reset(BudgetState())
    print(json.dumps(state.to_dict()))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AFK budget (GA-2, #102).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_chk = sub.add_parser("check", help="Check whether the budget allows a promotion.")
    p_chk.add_argument("--state", required=True, help="JSON BudgetState.")
    p_chk.add_argument("--cost", type=float, required=True)
    p_chk.add_argument("--promotions", type=int, default=1)
    p_chk.add_argument("--max-promotions", type=int, default=DEFAULT_MAX_PROMOTIONS)
    p_chk.add_argument("--max-spend-usd", type=float, default=DEFAULT_MAX_SPEND_USD)
    p_chk.set_defaults(func=_cmd_check)

    p_rst = sub.add_parser("reset", help="Reset the budget (new AFK session).")
    p_rst.set_defaults(func=_cmd_reset)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
