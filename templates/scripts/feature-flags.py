#!/usr/bin/env python3
"""
feature-flags.py — Feature flags for gradual rollout (#70)

Controls which Hephaestus v0.5 features are active.
Default configuration is SAFE: all new features disabled/shadow.

Commands:
  status   — Show current feature flag state
  check    — Check if a feature is allowed to execute (gate function)
  set      — Set a feature flag value

Usage:
  feature-flags.py status <state_file>
  feature-flags.py check <state_file> <feature_name>
  feature-flags.py set <state_file> <feature_name> <value>

Exit codes:
  0 = check passed (feature allowed) / status success
  1 = check failed (feature blocked / not allowed) / error
"""

import json
import os
import sys

# Flag defaults when not present in state
FLAG_DEFAULTS = {
    "reflector": "shadow",         # shadow | active | disabled
    "suspect_enforcement": False,  # bool
    "analogy_channel": False,      # bool
    "dream_channel": False,        # bool
    "affect_modulation": False,    # bool
    "whisper_channel": False,      # bool
}

# Valid values per flag
FLAG_VALID = {
    "reflector": ["shadow", "active", "disabled"],
    "suspect_enforcement": [True, False],
    "analogy_channel": [True, False],
    "dream_channel": [True, False],
    "affect_modulation": [True, False],
    "whisper_channel": [True, False],
}


def load_flags(state_file):
    """Load feature flags from state.json."""
    if not os.path.exists(state_file):
        return dict(FLAG_DEFAULTS)

    with open(state_file) as f:
        state = json.load(f)

    features = state.get("features", {})
    result = {}
    for key, default in FLAG_DEFAULTS.items():
        result[key] = features.get(key, default)

    return result


def save_flags(state_file, flags):
    """Save feature flags to state.json."""
    with open(state_file) as f:
        state = json.load(f)

    if "features" not in state:
        state["features"] = {}

    state["features"].update(flags)

    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)


def check_feature(state_file, feature_name):
    """Check if a feature is allowed to execute. This is the gate function."""
    flags = load_flags(state_file)

    if feature_name not in FLAG_DEFAULTS:
        return {
            "feature": feature_name,
            "allowed": False,
            "reason": f"Unknown feature '{feature_name}'",
        }

    value = flags.get(feature_name, FLAG_DEFAULTS[feature_name])

    if feature_name == "reflector":
        # Reflector allowed in both shadow and active mode
        allowed = value in ("shadow", "active")
        return {
            "feature": feature_name,
            "allowed": allowed,
            "value": value,
            "mode": value,
            "reason": "" if allowed else f"Reflector is '{value}', must be 'shadow' or 'active'",
        }

    # Boolean features
    if isinstance(value, bool):
        return {
            "feature": feature_name,
            "allowed": value,
            "value": value,
            "reason": "" if value else f"Feature '{feature_name}' is disabled",
        }

    # String features
    return {
        "feature": feature_name,
        "allowed": value != "disabled",
        "value": value,
        "reason": "" if value != "disabled" else f"Feature '{feature_name}' is 'disabled'",
    }


def cmd_status(state_file):
    """Show all feature flags and their current values."""
    flags = load_flags(state_file)
    print(json.dumps({
        "flags": flags,
        "all_safe": all(
            v == FLAG_DEFAULTS[k] if isinstance(v, str) else v == bool(FLAG_DEFAULTS[k])
            for k, v in flags.items()
        ),
    }, indent=2))
    sys.exit(0)


def cmd_check(state_file, feature_name):
    """Check if a feature is allowed."""
    result = check_feature(state_file, feature_name)
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["allowed"] else 1)


def cmd_set(state_file, feature_name, value_str):
    """Set a feature flag value."""
    if feature_name not in FLAG_DEFAULTS:
        print(json.dumps({"error": f"Unknown feature '{feature_name}'"}, indent=2))
        sys.exit(1)

    # Parse value
    if value_str.lower() in ("true", "false"):
        value = value_str.lower() == "true"
    else:
        value = value_str.lower()

    # Validate
    valid_values = FLAG_VALID[feature_name]
    if value not in valid_values:
        print(json.dumps({
            "error": f"Invalid value '{value_str}' for '{feature_name}'. Valid: {valid_values}",
        }, indent=2))
        sys.exit(1)

    # Load existing flags, update, save
    flags = load_flags(state_file)
    old_val = flags.get(feature_name)
    flags[feature_name] = value

    # Need to write back to state
    with open(state_file) as f:
        state = json.load(f)
    if "features" not in state:
        state["features"] = {}
    state["features"][feature_name] = value
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

    print(json.dumps({
        "feature": feature_name,
        "old_value": old_val,
        "new_value": value,
        "changed": old_val != value,
    }, indent=2))
    sys.exit(0)


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    state_file = sys.argv[2]

    if command == "status":
        cmd_status(state_file)
    elif command == "check":
        if len(sys.argv) < 4:
            print("Error: check requires <feature_name>", file=sys.stderr)
            sys.exit(1)
        cmd_check(state_file, sys.argv[3])
    elif command == "set":
        if len(sys.argv) < 5:
            print("Error: set requires <feature_name> <value>", file=sys.stderr)
            sys.exit(1)
        cmd_set(state_file, sys.argv[3], sys.argv[4])
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
