"""Verify Issue #11: Ideas Engine anti-collapse — novelty_score, embedding, family."""
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_novelty_score_field_exists():
    """ideas.schema.json must have novelty_score field (anti-collapse)."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    assert "novelty_score" in schema["properties"], "novelty_score field not found"
    props = schema["properties"]["novelty_score"]
    assert props["type"] == "number", "novelty_score must be number"
    assert props.get("minimum") == 0, "novelty_score must have minimum 0"
    assert props.get("maximum") == 100, "novelty_score must have maximum 100"


def test_embedding_field_exists():
    """ideas.schema.json must have embedding field (dedup via cosine similarity)."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    assert "embedding" in schema["properties"], "embedding field not found"
    props = schema["properties"]["embedding"]
    assert props["type"] == "array", "embedding must be array"
    assert "items" in props, "embedding must have items schema"
    assert props["items"]["type"] == "number", "embedding items must be number"


def test_family_field_exists():
    """ideas.schema.json must have family field (family exhaustion tracking)."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    assert "family" in schema["properties"], "family field not found"
    props = schema["properties"]["family"]
    assert props["type"] == "string", "family must be string"
    assert "default" in props, "family must have default"


def test_novelty_score_default():
    """novelty_score should default to 50 (neutral)."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    default = schema["properties"]["novelty_score"].get("default")
    assert default is not None, "novelty_score must have a default"
    assert 0 <= default <= 100, f"novelty_score default {default} out of range [0, 100]"


def test_embedding_default_empty():
    """embedding should default to empty array."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    default = schema["properties"]["embedding"].get("default")
    assert default is not None, "embedding must have a default"
    assert default == [], f"embedding default should be [], got {default}"


def test_family_default_empty_string():
    """family should default to empty string."""
    schema = load_json(os.path.join(REPO_ROOT, "schema", "ideas.schema.json"))
    default = schema["properties"]["family"].get("default")
    assert default is not None, "family must have a default"
    assert default == "", f"family default should be '', got {default}"


def test_ideas_engine_mentioned_in_orchestration():
    """Project files should reference Ideas Engine in the orchestration flow."""
    soul_path = os.path.join(REPO_ROOT, "templates", "SOUL.orchestrator.md")
    with open(soul_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Ideas Engine" in content, "SOUL.orchestrator.md should mention 'Ideas Engine'"


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
