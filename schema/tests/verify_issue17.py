"""Verify Issue #17: Cross-project fikir transferi (idea transfer)."""
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_ideas_schema_has_source_project():
    """ideas.schema.json must have source_project field."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    assert "source_project" in schema["properties"], "source_project field not found"
    props = schema["properties"]["source_project"]
    assert props["type"] == "string", "source_project must be string"
    assert props.get("default") == "", "source_project default should be empty string"


def test_source_project_description_cross_project():
    """source_project description should mention cross-project transfers."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    desc = schema["properties"]["source_project"].get("description", "")
    assert "cross" in desc.lower() or "transfer" in desc.lower() or "source" in desc.lower(), (
        "source_project description should reference cross-project transfer"
    )


def test_registry_schema_has_projects_array():
    """registry.schema.json must have projects array."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "registry.schema.json"))
    assert "projects" in schema["properties"], "projects field not found"
    props = schema["properties"]["projects"]
    assert props["type"] == "array", "projects must be array"
    assert "items" in props, "projects must have items schema"


def test_registry_project_has_name_field():
    """Registry project must have name field."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "registry.schema.json"))
    project_props = schema["properties"]["projects"]["items"]["properties"]
    assert "name" in project_props, "project item missing name"
    assert project_props["name"]["type"] == "string", "name must be string"


def test_registry_project_has_adapter_field():
    """Registry project must have adapter field."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "registry.schema.json"))
    project_props = schema["properties"]["projects"]["items"]["properties"]
    assert "adapter" in project_props, "project item missing adapter"
    assert project_props["adapter"]["type"] == "string", "adapter must be string"


def test_registry_project_has_status_and_goal_status():
    """Registry project must have status and goal_status fields."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "registry.schema.json"))
    project_props = schema["properties"]["projects"]["items"]["properties"]
    assert "status" in project_props, "project item missing status"
    assert "goal_status" in project_props, "project item missing goal_status"
    assert "enum" in project_props["status"], "status must have enum values"
    assert "enum" in project_props["goal_status"], "goal_status must have enum values"


def test_registry_required_fields():
    """Registry project required fields must include name, repo, ledger, board."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "registry.schema.json"))
    required = schema["properties"]["projects"]["items"].get("required", [])
    for field in ("name", "repo", "ledger", "board"):
        assert field in required, f"'{field}' must be in project required fields"


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
