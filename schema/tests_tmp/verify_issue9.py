"""Verify Issue #9: Ideas Engine — schema fields and lifecycle stages."""
import json
import os
import sys
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_ideas_schema_exists():
    """schema/ideas.schema.json must exist."""
    path = os.path.join(REPO_ROOT, "schema", "ideas.schema.json")
    assert os.path.isfile(path), f"ideas.schema.json not found at {path}"


def test_ideas_schema_has_id():
    """ideas.schema.json must have id field."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    assert "id" in schema["properties"], "id field not found"
    assert schema["properties"]["id"]["type"] == "string", "id must be string"


def test_ideas_schema_has_title():
    """ideas.schema.json must have title field."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    assert "title" in schema["properties"], "title field not found"
    assert schema["properties"]["title"]["type"] == "string", "title must be string"


def test_ideas_schema_has_description():
    """ideas.schema.json must have description field."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    assert "description" in schema["properties"], "description field not found"
    assert schema["properties"]["description"]["type"] == "string", "description must be string"


def test_ideas_schema_has_source():
    """ideas.schema.json must have source field."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    assert "source" in schema["properties"], "source field not found"
    assert schema["properties"]["source"]["type"] == "string", "source must be string"


def test_ideas_schema_has_status():
    """ideas.schema.json must have status field with lifecycle stages."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    assert "status" in schema["properties"], "status field not found"
    assert schema["properties"]["status"]["type"] == "string", "status must be string"
    # Lifecycle stages
    assert "enum" in schema["properties"]["status"], "status must have enum"


def test_ideas_schema_has_triage_score():
    """ideas.schema.json must have triage_score field."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    assert "triage_score" in schema["properties"], "triage_score field not found"
    assert schema["properties"]["triage_score"]["type"] == "number", "triage_score must be number"


def test_idea_lifecycle_stages():
    """Status enum must include all lifecycle stages."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    stages = schema["properties"]["status"]["enum"]
    expected = {"spark", "triaged", "hypothesis", "task", "verdict_pass", "verdict_fail", "cancelled"}
    for stage in expected:
        assert stage in stages, f"lifecycle stage '{stage}' missing from status enum"


def test_goal_yaml_exhaustion_policy():
    """templates/goal.yaml must have exhaustion_policy: generate_ideas."""
    goal = load_yaml(os.path.join(REPO_ROOT, "templates", "goal.yaml"))
    never_stop = goal.get("never_stop_rules", {})
    assert "exhaustion_policy" in never_stop, "exhaustion_policy not found in never_stop_rules"
    assert never_stop["exhaustion_policy"] == "generate_ideas", (
        f"expected 'generate_ideas', got '{never_stop['exhaustion_policy']}'"
    )


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
