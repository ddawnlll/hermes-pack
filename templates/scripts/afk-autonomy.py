#!/usr/bin/env python3
"""
AFK autonomy feature flags (GA-1, #99).

Four flags (consumed by feature-flags.py, 8.6K, merged):
  - auto_when_afk:            bool, default False
  - allowed_effect_classes:   list, default ["reversible_internal"]
  - max_concurrent_promotions: int, default 1
  - kill_override_priority:   bool, default True

Gate #15 enforcement: irreversible_external is rejected under AFK, even
when auto_when_afk is on. This check is layered:
  1. T4 disposition (BE-5 #87) -> escalate_human early.
  2. Promotion Engine (BE-2 #85) -> precondition fails.
  3. Containment Engine (#61)   -> kill overrides AFK.

The kill_override_priority flag is True by default: a kill signal ALWAYS
wins over AFK autonomy. This is not a "weaker" form of #17 (Kill
supremacy); it is the same invariant.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field, asdict


@dataclass
class AFKFlags:
    auto_when_afk: bool = False
    allowed_effect_classes: list = field(default_factory=lambda: ["reversible_internal"])
    max_concurrent_promotions: int = 1
    kill_override_priority: bool = True

    def is_allowed(self, effect_class: str) -> bool:
        if not self.auto_when_afk:
            return False
        return effect_class in self.allowed_effect_classes

    def to_dict(self) -> dict:
        return asdict(self)


def load(path: str) -> AFKFlags:
    with open(path) as f:
        raw = json.load(f)
    return AFKFlags(**raw)


def save(flags: AFKFlags, path: str) -> None:
    with open(path, "w") as f:
        json.dump(flags.to_dict(), f, indent=2)


def check(flags: AFKFlags, effect_class: str, *, kill_active: bool = False) -> dict:
    """Returns a verdict for a candidate with the given effect_class."""
    if kill_active and flags.kill_override_priority:
        return {"verdict": "KILLED", "reason": "kill_override_priority"}
    if effect_class == "irreversible_external":
        return {"verdict": "REJECTED", "reason": "irreversible_external_under_afk"}
    if not flags.auto_when_afk:
        return {"verdict": "REJECTED", "reason": "auto_when_afk_disabled"}
    if not flags.is_allowed(effect_class):
        return {"verdict": "REJECTED", "reason": f"effect_class_{effect_class}_not_allowed"}
    return {"verdict": "ALLOWED", "reason": "ok"}


def _cmd_check(args: argparse.Namespace) -> int:
    flags = AFKFlags(**json.loads(args.flags))
    verdict = check(flags, args.effect_class, kill_active=args.kill_active)
    print(json.dumps(verdict))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AFK autonomy flags (GA-1, #99).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_chk = sub.add_parser("check", help="Check whether a candidate's effect_class is allowed under AFK.")
    p_chk.add_argument("--flags", required=True, help="JSON object with the four flag values.")
    p_chk.add_argument("--effect-class", required=True)
    p_chk.add_argument("--kill-active", action="store_true")
    p_chk.set_defaults(func=_cmd_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
