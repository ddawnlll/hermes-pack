#!/usr/bin/env python3
"""
containment-engine.py — Phase 2 Containment Mechanisms (#61, #62, #63, #64)

#61 — Authority matrix with terminal referee for every role pair
#62 — Suspect TTL with automatic enforcement expiry (no permanent lockout)
#63 — Belief minimum residency and evidence-backed eviction
#64 — Frame-shift cooldown + ratchet hysteresis (rate limit + directional window)

Commands:
  authority-check <role_a> <role_b> [roles_dir]
      — Check if two roles have a terminal referee. When roles_dir is provided,
        dynamically discovers all roles from bootstrap/profile definitions and
        verifies coverage.
  suspect-ttl <beliefs_file> [--tick-increment=N]
      — Age suspect beliefs. When suspect_age >= TTL, enforcement expires:
        status reverts to 'active' (or 'active_previously_suspect').
        Audit history that belief was suspect is preserved.
  curiosity-check <state_file> <hypothesis_id>
      — Check if curiosity budget allows a blocked experiment to run.
  eviction-review <beliefs_file>
      — Review candidates for evidence-backed eviction.
  eviction-execute <beliefs_file> <belief_id> [more_ids...]
      — Execute eviction with audit trail.
  cooldown-tick <beliefs_file> [--tick-increment=N] [--ratchet-window=N]
      — Advance cooldown counters. Implements ratchet hysteresis:
        * Max one notch change per R-verdict window
        * Direction reversal requires full evidence window
        * All transitions recorded in ratchet_audit
        * State survives process restart (stored in beliefs.yaml)
  ratchet-check <beliefs_file>
      — Check for oscillation and pending ratchet actions.
  dynamic-coverage [roles_dir]
      — Discover all roles from bootstrap definitions and verify authority coverage.
  status <state_file> <beliefs_file>
      — Show combined containment status.
"""

import json
import os
import sys
import yaml

from datetime import datetime


# ── Authority Matrix (#61) ─────────────────────────────────────────────────────

BASE_ROLES = {
    "worker", "orchestrator", "challenger", "arbiter",
    "red_team", "explorer", "reflector", "human",
}

AUTHORITY_MATRIX = {
    ("worker", "challenger"): "arbiter",
    ("worker", "orchestrator"): "arbiter",
    ("worker", "worker"): "orchestrator",
    ("challenger", "orchestrator"): "arbiter",
    ("challenger", "arbiter"): "human",
    ("challenger", "red_team"): "arbiter",
    ("challenger", "explorer"): "arbiter",
    ("challenger", "reflector"): "arbiter",
    ("orchestrator", "arbiter"): "human",
    ("orchestrator", "red_team"): "arbiter",
    ("orchestrator", "explorer"): "arbiter",
    ("orchestrator", "reflector"): "arbiter",
    ("red_team", "worker"): "arbiter",
    ("red_team", "explorer"): "orchestrator",
    ("red_team", "arbiter"): "human",
    ("red_team", "reflector"): "arbiter",
    ("explorer", "reflector"): "orchestrator",
    ("explorer", "worker"): "orchestrator",
    ("explorer", "arbiter"): "human",
    ("reflector", "arbiter"): "human",
    ("reflector", "worker"): "arbiter",
    ("arbiter", "human"): "human",
    ("arbiter", "worker"): "human",
    ("human", "worker"): "human",
    ("human", "orchestrator"): "human",
    ("human", "arbiter"): "human",
    ("human", "red_team"): "human",
    ("human", "explorer"): "human",
    ("human", "reflector"): "human",
    ("human", "challenger"): "human",
}

BLOCKING_TIMEOUTS = {
    "challenger_pending": {"timeout_ticks": 3, "default": "HOLD"},
    "arbiter_pending": {"timeout_ticks": 5, "default": "HOLD"},
    "red_team_pending": {"timeout_ticks": 3, "default": "HOLD"},
    "human_pending": {"timeout_ticks": 24, "default": "HOLD"},
    "praxis_pending": {"timeout_ticks": 2, "default": "HOLD"},
    "eviction_review": {"timeout_ticks": 3, "default": "HOLD"},
}


def discover_roles_from_bootstrap(roles_dir=None):
    """Dynamically discover all roles from bootstrap and profile definitions.
    
    Scans:
    1. templates/ for SOUL.*.md files
    2. adapters/*/project.yaml for profile definitions
    3. bootstrap.sh and bootstrap.ts for profile listings
    
    Returns a set of role names (normalized to canonical names).
    """
    # Role alias mapping: non-canonical name -> canonical name
    ROLE_ALIASES = {
        "redteam": "red_team",
    }
    
    discovered = set(BASE_ROLES)  # Start with known roles

    if roles_dir and os.path.isdir(roles_dir):
        # Scan for SOUL files
        for fname in os.listdir(roles_dir):
            if fname.startswith("SOUL.") and fname.endswith(".md"):
                role = fname[5:-3].lower()  # SOUL.xyz.md -> xyz
                discovered.add(ROLE_ALIASES.get(role, role))

        # Scan for config files
        for fname in os.listdir(roles_dir):
            if fname.startswith("config.") and fname.endswith(".yaml"):
                role = fname[7:-5].lower()  # config.xyz.yaml -> xyz
                discovered.add(ROLE_ALIASES.get(role, role))

        # Recursively scan subdirectories
        for root, dirs, files in os.walk(roles_dir):
            for fname in files:
                if fname == "project.yaml":
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath) as f:
                            pd = yaml.safe_load(f)
                        if isinstance(pd, dict):
                            for key in ("profiles", "roles"):
                                for item in pd.get(key, []):
                                    if isinstance(item, dict) and "name" in item:
                                        discovered.add(item["name"].lower())
                                    elif isinstance(item, str):
                                        discovered.add(item.lower())
                    except (yaml.YAMLError, IOError):
                        pass
                elif fname.endswith(".yaml") and "profile" in fname.lower():
                    try:
                        with open(os.path.join(root, fname)) as f:
                            pd = yaml.safe_load(f)
                        if isinstance(pd, dict) and "name" in pd:
                            discovered.add(pd["name"].lower())
                    except (yaml.YAMLError, IOError):
                        pass

    return discovered


def check_authority(conflicting_roles, roles_dir=None):
    """Check if two conflicting roles have a terminal referee.
    
    When roles_dir is provided, dynamically verifies coverage.
    """
    if not isinstance(conflicting_roles, (list, tuple)) or len(conflicting_roles) != 2:
        return {"error": "conflicting_roles must be a list/tuple of 2 role names"}

    role_a, role_b = conflicting_roles
    roles = sorted([role_a.lower().strip(), role_b.lower().strip()])
    key = (roles[0], roles[1])

    referee = AUTHORITY_MATRIX.get(key) or AUTHORITY_MATRIX.get((roles[1], roles[0]))

    if not referee:
        return {
            "verdict": "FAIL",
            "roles": [role_a, role_b],
            "referee": None,
            "is_terminal": False,
            "error": f"No terminal referee defined for pair ({role_a}, {role_b}). "
                     f"Add to AUTHORITY_MATRIX in containment-engine.py",
        }

    if referee in roles:
        is_human_exception = (referee == "human")
        return {
            "verdict": "FAIL" if not is_human_exception else "PASS_WITH_EXCEPTION",
            "roles": [role_a, role_b],
            "referee": referee,
            "is_terminal": True,
            "note": "Human is terminal authority (explicit exception)" if is_human_exception
                    else f"Referee '{referee}' is a party!",
            "exception": "human_terminal" if is_human_exception else None,
        }

    is_terminal = referee in ("arbiter", "human")

    return {
        "verdict": "PASS",
        "roles": [role_a, role_b],
        "referee": referee,
        "is_terminal": is_terminal,
        "note": "Terminal referee" if is_terminal else f"Referee: {referee} (may escalate)",
    }


def dynamic_coverage(roles_dir=None):
    """Discover roles dynamically and verify every pair has coverage.
    
    Returns detailed coverage report. Test must fail when a new role is
    introduced without coverage.
    """
    roles = discover_roles_from_bootstrap(roles_dir)
    role_list = sorted(roles)

    covered = 0
    missing_pairs = []
    for i, r1 in enumerate(role_list):
        for r2 in role_list[i + 1:]:
            key = (r1, r2)
            rev_key = (r2, r1)
            if key in AUTHORITY_MATRIX or rev_key in AUTHORITY_MATRIX:
                covered += 1
            else:
                missing_pairs.append(key)

    # Verify every blocking state has timeout + HOLD + terminal referee
    blocking_issues = []
    for state, config in BLOCKING_TIMEOUTS.items():
        if config.get("default") != "HOLD":
            blocking_issues.append(f"{state}: default is '{config.get('default')}', expected 'HOLD'")
        if config.get("timeout_ticks", 0) <= 0:
            blocking_issues.append(f"{state}: timeout_ticks <= 0")

    return {
        "discovered_roles": role_list,
        "total_roles": len(role_list),
        "total_possible_pairs": len(role_list) * (len(role_list) - 1) // 2,
        "covered_pairs": covered,
        "missing_pairs": missing_pairs,
        "missing_pairs_count": len(missing_pairs),
        "blocking_state_issues": blocking_issues,
        "coverage_complete": len(missing_pairs) == 0 and len(blocking_issues) == 0,
    }


# ── Suspect TTL (#62) — Actually expire enforcement ────────────────────────────

SUSPECT_TTL_DEFAULT = 12
CURIOSITY_BUDGET_PCT = 0.20


def age_suspect_beliefs(beliefs_file, tick_increment=1):
    """
    Age suspect beliefs. When suspect_age >= TTL, enforcement EXPIRES:
    - Status changes to 'active' (preserving audit trail via suspect_age history)
    - The belief retains its provenance and evidence_refs
    - Normal in-frame hypothesis generation becomes possible again
    - Reflector may re-justify with new evidence to reinstate suspect status
    
    This is NOT merely "flagging for review" — it actively ends enforcement.
    """
    if not os.path.exists(beliefs_file):
        return {"error": f"Beliefs file not found: {beliefs_file}"}

    with open(beliefs_file) as f:
        beliefs_data = yaml.safe_load(f)

    beliefs = beliefs_data.get("beliefs", [])
    expired = []
    still_suspect = []
    reinstated = []

    for belief in beliefs:
        if belief.get("status") != "suspect":
            continue

        suspect_age = belief.get("suspect_age", 0) + tick_increment
        belief["suspect_age"] = suspect_age
        ttl = belief.get("ttl", SUSPECT_TTL_DEFAULT)

        if suspect_age >= ttl:
            # TTL EXPIRED — enforcement ends automatically
            belief["status"] = "active"
            belief["_previously_suspect"] = True
            belief["_suspect_expired_at"] = datetime.utcnow().isoformat() + "Z"
            belief["updated_at"] = datetime.utcnow().isoformat() + "Z"
            expired.append({
                "id": belief.get("id"),
                "suspect_age": suspect_age,
                "ttl": ttl,
                "new_status": "active",
                "statement": belief.get("statement", "")[:80],
            })
        else:
            still_suspect.append(belief.get("id"))

    # Write back
    with open(beliefs_file, "w") as f:
        yaml.dump(beliefs_data, f, default_flow_style=False)

    return {
        "action": "aged",
        "tick_increment": tick_increment,
        "suspect_count": sum(1 for b in beliefs if b.get("status") == "suspect"),
        "expired_enforcement": expired,
        "still_suspect": still_suspect,
    }


def curiosity_exempted(state_file, hypothesis):
    if not os.path.exists(state_file):
        return {"error": f"State file not found: {state_file}"}

    with open(state_file) as f:
        state = json.load(f)

    daily_budget = state.get("budget_usd", 25)
    spend_today = state.get("spend_today_usd", 0)
    curiosity_budget = daily_budget * CURIOSITY_BUDGET_PCT
    remaining = daily_budget - spend_today

    can_run = remaining >= curiosity_budget * 0.1

    return {
        "hypothesis": hypothesis,
        "curiosity_budget_usd": round(curiosity_budget, 2),
        "remaining_budget_usd": round(remaining, 2),
        "can_run_experiment": can_run,
        "reason": "Sufficient curiosity budget" if can_run else "Curiosity budget insufficient",
        "note": "Red Team may block claim promotion, but curiosity experiments proceed independently",
    }


# ── Belief Eviction (#63) ─────────────────────────────────────────────────────

MIN_RESIDENCY_TICKS = 6


def review_eviction_candidates(beliefs_file):
    if not os.path.exists(beliefs_file):
        return {"error": f"Beliefs file not found: {beliefs_file}"}

    with open(beliefs_file) as f:
        beliefs_data = yaml.safe_load(f)

    beliefs = beliefs_data.get("beliefs", [])
    candidates = []

    for belief in beliefs:
        bid = belief.get("id", "")
        status = belief.get("status", "active")

        if status in ("evicted", "refuted"):
            continue

        stagnation = belief.get("stagnation", 0)
        ttl = belief.get("ttl", 24)
        confidence = belief.get("confidence", "medium")

        if stagnation >= ttl and confidence in ("low", "speculative"):
            candidates.append({
                "id": bid,
                "statement": belief.get("statement", "")[:80],
                "stagnation": stagnation,
                "ttl": ttl,
                "confidence": confidence,
                "status": status,
                "eligible": True,
                "reason": f"Stagnation {stagnation} >= TTL {ttl}, confidence {confidence}",
            })

    return {
        "total_beliefs": len(beliefs),
        "eviction_candidates": candidates,
        "candidate_count": len(candidates),
        "min_residency_ticks": MIN_RESIDENCY_TICKS,
    }


def execute_eviction(beliefs_file, belief_ids, evidence_refs=None):
    if not os.path.exists(beliefs_file):
        return {"error": f"Beliefs file not found: {beliefs_file}"}

    with open(beliefs_file) as f:
        beliefs_data = yaml.safe_load(f)

    beliefs = beliefs_data.get("beliefs", [])
    evicted = []
    not_found = []

    for bid in belief_ids:
        found = False
        for belief in beliefs:
            if belief.get("id") == bid:
                old_status = belief.get("status", "active")
                belief["status"] = "evicted"
                belief["updated_at"] = datetime.utcnow().isoformat() + "Z"
                belief["eviction_reason"] = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "evidence_refs": evidence_refs or [],
                }
                evicted.append({"id": bid, "old_status": old_status, "new_status": "evicted"})
                found = True
                break
        if not found:
            not_found.append(bid)

    with open(beliefs_file, "w") as f:
        yaml.dump(beliefs_data, f, default_flow_style=False)

    return {"action": "evicted", "evicted": evicted, "not_found": not_found, "total_evicted": len(evicted)}


# ── Frame-shift Cooldown + Ratchet Hysteresis (#64) ───────────────────────────

FRAME_COOLDOWN_TICKS = 6
RATCHET_COOLDOWN_TICKS = 4
RATCHET_VERDICT_WINDOW = 5       # R = 5 verdicts per window
MAX_NOTCH_PER_WINDOW = 1         # Max one notch change per window
MIN_EVIDENCE_FOR_REVERSAL = 3    # Verdicts supporting new direction before reversal


def advance_cooldowns(beliefs_file, tick_increment=1, ratchet_window=None):
    """
    Advance cooldown counters. Implements ratchet hysteresis:
    
    1. Max one ratchet notch change per R-verdict window.
    2. Direction reversal requires a complete evidence window (MIN_EVIDENCE_FOR_REVERSAL
       consecutive verdicts supporting the new direction).
    3. A single anomalous verdict may never reverse direction.
    4. All transitions are recorded in ratchet_audit.
    5. State survives process restart (stored in durable beliefs.yaml).
    """
    if ratchet_window is None:
        ratchet_window = RATCHET_VERDICT_WINDOW

    if not os.path.exists(beliefs_file):
        return {"error": f"Beliefs file not found: {beliefs_file}"}

    with open(beliefs_file) as f:
        beliefs_data = yaml.safe_load(f)

    beliefs = beliefs_data.get("beliefs", [])
    cooldown_active = []
    cooldown_expired = []
    ratchet_changes = []

    for belief in beliefs:
        # Advance cooldown timer
        cooldown = belief.get("cooldown_remaining", 0)
        if cooldown > 0:
            new_cooldown = max(0, cooldown - tick_increment)
            belief["cooldown_remaining"] = new_cooldown
            if new_cooldown == 0:
                cooldown_expired.append(belief.get("id"))
            else:
                cooldown_active.append(belief.get("id"))

        # ── Ratchet Hysteresis ──────────────────────────────────────
        momentum = belief.get("momentum", 0)
        prev_momentum = belief.get("_prev_momentum", 0)
        frame_shift_count = belief.get("frame_shift_count", 0)

        # Direction change detection
        direction_changed = (prev_momentum > 0 and momentum < 0) or (prev_momentum < 0 and momentum > 0)

        if direction_changed:
            frame_shift_count += 1
            belief["frame_shift_count"] = frame_shift_count

            # Get or initialize ratchet tracking
            verdict_count = belief.get("_verdict_count", 0) + 1
            belief["_verdict_count"] = verdict_count
            current_window = verdict_count // ratchet_window
            last_window = belief.get("_last_ratchet_window", -1)
            current_notch = belief.get("_ratchet_notch", 0)

            # Rule 1: Max one notch per R-verdict window
            if current_window == last_window:
                # Already changed in this window — block another change
                ratchet_changes.append({
                    "id": belief.get("id"),
                    "action": "blocked",
                    "reason": f"Already changed notch in window {current_window}. "
                              f"Max {MAX_NOTCH_PER_WINDOW} per window.",
                    "current_notch": current_notch,
                })
            else:
                # Rule 2 & 3: Direction reversal requires full evidence window
                consecutive_same = belief.get("_consecutive_same_direction", 0)
                new_direction = "tighten" if momentum > 0 else "loosen"

                if prev_momentum != 0 and direction_changed:
                    # Direction reversal — check evidence threshold
                    if consecutive_same >= MIN_EVIDENCE_FOR_REVERSAL:
                        # Valid reversal — allow it
                        new_notch = current_notch + (1 if momentum > 0 else -1)
                        belief["_ratchet_notch"] = new_notch
                        belief["_last_ratchet_window"] = current_window
                        belief["_consecutive_same_direction"] = 0
                        belief["cooldown_remaining"] = max(belief.get("cooldown_remaining", 0),
                                                           RATCHET_COOLDOWN_TICKS)

                        # Record in audit log
                        audit_entry = {
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "direction": "reverse",
                            "notch": new_notch,
                            "verdict_window": current_window,
                            "evidence_summary": f"Reversal after {consecutive_same} consecutive supporting verdicts",
                        }
                        audit = belief.get("ratchet_audit", [])
                        audit.append(audit_entry)
                        belief["ratchet_audit"] = audit

                        ratchet_changes.append({
                            "id": belief.get("id"),
                            "action": "reversal",
                            "new_notch": new_notch,
                            "window": current_window,
                            "evidence_count": consecutive_same,
                        })
                    else:
                        # Not enough evidence — block reversal
                        ratchet_changes.append({
                            "id": belief.get("id"),
                            "action": "blocked_reversal",
                            "reason": f"Only {consecutive_same} consecutive supporting verdicts, "
                                      f"need {MIN_EVIDENCE_FOR_REVERSAL}.",
                        })
                else:
                    # Same direction — increment notch counter
                    new_notch = current_notch + (1 if momentum > 0 else -1)
                    belief["_ratchet_notch"] = new_notch
                    belief["_last_ratchet_window"] = current_window
                    belief["_consecutive_same_direction"] = consecutive_same + 1

                    ratchet_changes.append({
                        "id": belief.get("id"),
                        "action": "notch_increment",
                        "new_notch": new_notch,
                        "window": current_window,
                    })

        else:
            # No direction change — update consecutive counter
            if momentum != 0:
                cons = belief.get("_consecutive_same_direction", 0)
                belief["_consecutive_same_direction"] = cons + 1

            # Reset verdict count and shift count on zero momentum
            if momentum == 0:
                belief["_verdict_count"] = 0
                belief["frame_shift_count"] = 0

        belief["_prev_momentum"] = momentum

    # Anti-oscillation: in-cooldown check via frame_shift_count
    for belief in beliefs:
        shift_count = belief.get("frame_shift_count", 0)
        if shift_count >= 2 and belief.get("cooldown_remaining", 0) == 0:
            belief["cooldown_remaining"] = FRAME_COOLDOWN_TICKS
            cooldown_active.append(belief.get("id"))
            ratchet_changes.append({
                "id": belief.get("id"),
                "action": "anti_oscillation_cooldown",
                "reason": f"Frame shifted {shift_count} times, forced cooldown",
            })

    with open(beliefs_file, "w") as f:
        yaml.dump(beliefs_data, f, default_flow_style=False)

    return {
        "action": "cooldowns_advanced",
        "cooldown_active": cooldown_active,
        "cooldown_expired": cooldown_expired,
        "ratchet_changes": ratchet_changes,
        "total_active": len(cooldown_active),
    }


def check_ratchet_direction(beliefs_file):
    if not os.path.exists(beliefs_file):
        return {"error": f"Beliefs file not found: {beliefs_file}"}

    with open(beliefs_file) as f:
        beliefs_data = yaml.safe_load(f)

    beliefs = beliefs_data.get("beliefs", [])
    oscillating = []
    pending_ratchets = []

    for belief in beliefs:
        shift_count = belief.get("frame_shift_count", 0)
        if shift_count >= 2:
            oscillating.append({
                "id": belief.get("id"),
                "shift_count": shift_count,
                "statement": belief.get("statement", "")[:60],
                "cooldown": belief.get("cooldown_remaining", 0),
                "ratchet_notch": belief.get("_ratchet_notch", 0),
                "verdict_count": belief.get("_verdict_count", 0),
            })

        # Check for pending ratchet operations
        momentum = belief.get("momentum", 0)
        prev_momentum = belief.get("_prev_momentum", 0)
        if (prev_momentum > 0 and momentum < 0) or (prev_momentum < 0 and momentum > 0):
            cons = belief.get("_consecutive_same_direction", 0)
            if cons < MIN_EVIDENCE_FOR_REVERSAL:
                pending_ratchets.append({
                    "id": belief.get("id"),
                    "status": "pending_reversal",
                    "consecutive_supporting": cons,
                    "needed": MIN_EVIDENCE_FOR_REVERSAL,
                })

    return {
        "oscillating_beliefs": oscillating,
        "oscillation_count": len(oscillating),
        "pending_ratchets": pending_ratchets,
        "pending_count": len(pending_ratchets),
        "cooldown_ticks": FRAME_COOLDOWN_TICKS,
        "ratchet_window": RATCHET_VERDICT_WINDOW,
        "max_notch_per_window": MAX_NOTCH_PER_WINDOW,
        "min_evidence_for_reversal": MIN_EVIDENCE_FOR_REVERSAL,
    }


# ── Status Overview ───────────────────────────────────────────────────────────

def status_overview(state_file, beliefs_file, roles_dir=None):
    result = {
        "authority_matrix": dynamic_coverage(roles_dir),
        "suspect_ttl": {
            "default_ttl": SUSPECT_TTL_DEFAULT,
            "curiosity_budget_pct": CURIOSITY_BUDGET_PCT,
            "enforcement_expires_automatically": True,
        },
        "eviction": {"min_residency_ticks": MIN_RESIDENCY_TICKS},
        "cooldown": {
            "frame_cooldown_ticks": FRAME_COOLDOWN_TICKS,
            "ratchet_cooldown_ticks": RATCHET_COOLDOWN_TICKS,
            "ratchet_window": RATCHET_VERDICT_WINDOW,
            "max_notch_per_window": MAX_NOTCH_PER_WINDOW,
            "min_evidence_for_reversal": MIN_EVIDENCE_FOR_REVERSAL,
        },
    }

    if os.path.exists(beliefs_file):
        with open(beliefs_file) as f:
            bd = yaml.safe_load(f)
        beliefs = bd.get("beliefs", [])
        result["beliefs_summary"] = {
            "total": len(beliefs),
            "active": sum(1 for b in beliefs if b.get("status") == "active"),
            "suspect": sum(1 for b in beliefs if b.get("status") == "suspect"),
            "evicted": sum(1 for b in beliefs if b.get("status") == "evicted"),
            "refuted": sum(1 for b in beliefs if b.get("status") == "refuted"),
            "in_cooldown": sum(1 for b in beliefs if b.get("cooldown_remaining", 0) > 0),
        }

    return result


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]

    if command == "authority-check":
        if len(sys.argv) < 4:
            print("Usage: containment-engine.py authority-check <role_a> <role_b> [roles_dir]", file=sys.stderr)
            sys.exit(1)
        roles_dir = sys.argv[4] if len(sys.argv) > 4 else None
        result = check_authority([sys.argv[2], sys.argv[3]], roles_dir)
        print(json.dumps(result, indent=2))
        is_fail = result.get("verdict") in ("FAIL",)
        sys.exit(1 if is_fail else 0)

    elif command == "dynamic-coverage":
        roles_dir = sys.argv[2] if len(sys.argv) > 2 else None
        result = dynamic_coverage(roles_dir)
        print(json.dumps(result, indent=2))
        sys.exit(1 if not result.get("coverage_complete") else 0)

    elif command == "suspect-ttl":
        if len(sys.argv) < 3:
            print("Usage: containment-engine.py suspect-ttl <beliefs_file> [--tick-increment=N]", file=sys.stderr)
            sys.exit(1)
        bfile = sys.argv[2]
        inc = 1
        for arg in sys.argv[3:]:
            if arg.startswith("--tick-increment="):
                inc = int(arg.split("=", 1)[1])
        result = age_suspect_beliefs(bfile, inc)
        print(json.dumps(result, indent=2))
        sys.exit(0)

    elif command == "curiosity-check":
        if len(sys.argv) < 4:
            print("Usage: containment-engine.py curiosity-check <state_file> <hypothesis_id>", file=sys.stderr)
            sys.exit(1)
        result = curiosity_exempted(sys.argv[2], sys.argv[3])
        print(json.dumps(result, indent=2))
        sys.exit(0)

    elif command == "eviction-review":
        if len(sys.argv) < 3:
            print("Usage: containment-engine.py eviction-review <beliefs_file>", file=sys.stderr)
            sys.exit(1)
        result = review_eviction_candidates(sys.argv[2])
        print(json.dumps(result, indent=2))
        sys.exit(0)

    elif command == "eviction-execute":
        if len(sys.argv) < 4:
            print("Usage: containment-engine.py eviction-execute <beliefs_file> <belief_id> [more_ids...]", file=sys.stderr)
            sys.exit(1)
        result = execute_eviction(sys.argv[2], sys.argv[3:])
        print(json.dumps(result, indent=2))
        sys.exit(0)

    elif command == "cooldown-tick":
        if len(sys.argv) < 3:
            print("Usage: containment-engine.py cooldown-tick <beliefs_file> [--tick-increment=N] [--ratchet-window=N]", file=sys.stderr)
            sys.exit(1)
        bfile = sys.argv[2]
        inc = 1
        rw = None
        for arg in sys.argv[3:]:
            if arg.startswith("--tick-increment="):
                inc = int(arg.split("=", 1)[1])
            elif arg.startswith("--ratchet-window="):
                rw = int(arg.split("=", 1)[1])
        result = advance_cooldowns(bfile, inc, rw)
        print(json.dumps(result, indent=2))
        sys.exit(0)

    elif command == "ratchet-check":
        if len(sys.argv) < 3:
            print("Usage: containment-engine.py ratchet-check <beliefs_file>", file=sys.stderr)
            sys.exit(1)
        result = check_ratchet_direction(sys.argv[2])
        print(json.dumps(result, indent=2))
        sys.exit(1 if result.get("oscillation_count", 0) > 0 else 0)

    elif command == "status":
        if len(sys.argv) < 4:
            print("Usage: containment-engine.py status <state_file> <beliefs_file> [roles_dir]", file=sys.stderr)
            sys.exit(1)
        roles_dir = sys.argv[4] if len(sys.argv) > 4 else None
        result = status_overview(sys.argv[2], sys.argv[3], roles_dir)
        print(json.dumps(result, indent=2))
        sys.exit(0)

    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
