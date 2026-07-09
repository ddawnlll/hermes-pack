"""Verify Issue #15: Global budget pool — budget fields and project priorities."""
import json
import os
import re
import sys
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_control_schema_has_max_llm_spend():
    """control.schema.json must have max_llm_spend_per_day_usd field."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "control.schema.json"))
    assert "max_llm_spend_per_day_usd" in schema["properties"], (
        "max_llm_spend_per_day_usd field not found"
    )
    props = schema["properties"]["max_llm_spend_per_day_usd"]
    assert props["type"] == "number", "max_llm_spend_per_day_usd must be number"
    assert props.get("minimum") == 0, "max_llm_spend_per_day_usd must have minimum 0"
    assert props.get("default") == 25, "max_llm_spend_per_day_usd default should be 25"


def test_templates_state_has_budget_fields():
    """templates/state.json must have spend_today_usd and budget_usd."""
    state = load_json(os.path.join(REPO_ROOT, "templates", "state.json"))
    assert "spend_today_usd" in state, "spend_today_usd not in state.json"
    assert isinstance(state["spend_today_usd"], (int, float)), "spend_today_usd must be numeric"
    assert "budget_usd" in state, "budget_usd not in state.json"
    assert isinstance(state["budget_usd"], (int, float)), "budget_usd must be numeric"


def test_templates_control_has_budget_line():
    """templates/control.yaml must contain max_llm_spend_per_day_usd template var."""
    text = read_text(os.path.join(REPO_ROOT, "templates", "control.yaml"))
    assert "max_llm_spend_per_day_usd:" in text, (
        "max_llm_spend_per_day_usd not in control.yaml"
    )


def test_templates_control_has_priority_line():
    """templates/control.yaml must contain current_priority."""
    text = read_text(os.path.join(REPO_ROOT, "templates", "control.yaml"))
    assert "current_priority:" in text, "current_priority not in control.yaml"


def test_templates_control_has_human_instruction_line():
    """templates/control.yaml must contain human_instruction."""
    text = read_text(os.path.join(REPO_ROOT, "templates", "control.yaml"))
    assert "human_instruction:" in text, "human_instruction not in control.yaml"


def test_control_schema_has_risk_based_gating():
    """control.schema.json must have risk_based_gating section."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "control.schema.json"))
    assert "risk_based_gating" in schema["properties"], (
        "risk_based_gating not in control.schema.json"
    )
    rbg = schema["properties"]["risk_based_gating"]
    assert rbg["type"] == "object", "risk_based_gating must be object"
    for level in ("low", "medium", "high", "critical"):
        assert level in rbg.get("properties", {}), (
            f"risk_based_gating missing {level} section"
        )


def test_project_yaml_matches_budget():
    """project.yaml must also have max_llm_spend_per_day_usd."""
    data = load_yaml(os.path.join(REPO_ROOT, "adapters", "v7-alphaforge", "project.yaml"))
    assert "max_llm_spend_per_day_usd" in data, (
        "max_llm_spend_per_day_usd not in project.yaml"
    )
    assert data["max_llm_spend_per_day_usd"] == 25, "project.yaml budget should be 25"


if __name__ == "__main__":
    import traceback
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"  PASS  {name}")
            except Exception as e:
                print(f"  FAIL  {name}: {e}")
                traceback.print_exc()
                failures += 1
    sys.exit(1 if failures else 0)
