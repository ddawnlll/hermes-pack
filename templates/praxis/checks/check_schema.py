#!/usr/bin/env python3
"""
Praxis check: validate evidence_bundle.json against its schema.
Fail-closed: malformed or missing bundle = FAIL.
"""
import json, sys, os

def load_schema(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(json.dumps({"check": "evidence_schema", "status": "ERROR", "message": f"Cannot load schema: {e}"}))
        sys.exit(1)

def validate_instance(instance, schema):
    """Simple required-field validation without a JSON Schema library dependency."""
    errors = []
    required = schema.get("required", [])
    for field in required:
        if field not in instance:
            errors.append(f"Missing required field: {field}")

    # Check status enum
    status_enum = schema.get("properties", {}).get("status", {}).get("enum", [])
    if status_enum and instance.get("status") not in status_enum:
        errors.append(f"Invalid status '{instance.get('status')}'. Must be one of {status_enum}")

    # Check claims have evidence
    claims = instance.get("claims", [])
    for i, claim in enumerate(claims):
        evidence = claim.get("evidence", [])
        if not evidence:
            errors.append(f"claims[{i}] has no evidence references")

    # Check context
    ctx = instance.get("context", {})
    if not ctx.get("capsule_hash"):
        errors.append("context.capsule_hash is required")
    if ctx.get("required_context_read") is not True:
        errors.append("context.required_context_read must be true")

    # Check git
    git = instance.get("git", {})
    for field in ["base_sha", "head_sha", "branch"]:
        if not git.get(field):
            errors.append(f"git.{field} is required")

    return errors

def main():
    bundle_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("EVIDENCE_BUNDLE", "")
    schema_path = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("EVIDENCE_SCHEMA", "")

    if not bundle_path or not os.path.exists(bundle_path):
        print(json.dumps({"check": "evidence_schema", "status": "FAIL",
                          "message": f"Evidence bundle not found: {bundle_path}"}))
        sys.exit(1)

    schema = load_schema(schema_path) if schema_path else {}
    try:
        with open(bundle_path) as f:
            instance = json.load(f)
    except json.JSONDecodeError as e:
        print(json.dumps({"check": "evidence_schema", "status": "FAIL",
                          "message": f"Invalid JSON in evidence bundle: {e}"}))
        sys.exit(1)

    errors = validate_instance(instance, schema)

    if errors:
        print(json.dumps({"check": "evidence_schema", "status": "FAIL",
                          "message": "; ".join(errors),
                          "detail": errors}))
        sys.exit(1)

    print(json.dumps({"check": "evidence_schema", "status": "PASS"}))

if __name__ == "__main__":
    main()
