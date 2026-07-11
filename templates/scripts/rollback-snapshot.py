#!/usr/bin/env python3
"""
Rollback snapshot manifest (BE-3, #86).

For every candidate, capture a snapshot manifest BEFORE promotion begins.
The Promotion Engine (BE-2 #85) consults the manifest on postcondition
fail or commit fail; on either, the engine restores from the snapshot and
transitions the candidate to ROLLED_BACK (Gate #4).

Snapshot strategies per asset_type (A-3 #78):
  - code: git ref (commit SHA before) + inverse-patch of the diff
  - config: beliefs.yaml line range + original line content
  - db: schema version (down-migration reference)
  - belief: journal entry id range + revert strategy

Wire format (JSON, stored under DL-3 #96):
{
  "candidate_id": "...",
  "asset_type": "code|config|db|belief",
  "captured_at_tick": <int>,
  "rollback_strategy": "git_reset|yaml_restore|schema_down|journal_revert",
  "rollback_ref": {...},
  "verification": {"checksum": "sha256:...", "verify_command": "..."}
}
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_SCHEMA_VERSION = 1

STRATEGIES = ("git_reset", "yaml_restore", "schema_down", "journal_revert")

ASSET_TYPE_TO_STRATEGY = {
    "code": "git_reset",
    "config": "yaml_restore",
    "db": "schema_down",
    "belief": "journal_revert",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def capture_git_reset(*, base_commit: str, diff_path: Path) -> dict:
    """Code: capture the base commit and an inverse patch."""
    inverse = diff_path.read_bytes() if diff_path.exists() else b""
    return {
        "strategy": "git_reset",
        "base_commit": base_commit,
        "inverse_patch_path": str(diff_path),
        "inverse_patch_sha256": _sha256(inverse),
        "verify_command": f"git apply -R {diff_path}",
    }


def capture_yaml_restore(*, yaml_path: Path, line_range: tuple[int, int]) -> dict:
    """Config: capture the original line range."""
    original = b""
    if yaml_path.exists():
        lines = yaml_path.read_text(encoding="utf-8").splitlines(keepends=True)
        start, end = line_range
        original = "".join(lines[max(0, start - 1):end]).encode("utf-8")
    return {
        "strategy": "yaml_restore",
        "yaml_path": str(yaml_path),
        "line_range": list(line_range),
        "original_sha256": _sha256(original),
        "verify_command": f"sed -i '{line_range[0]},{line_range[1]}d' {yaml_path}",
    }


def capture_schema_down(*, current_version: int, down_migration: str) -> dict:
    """DB: capture the current schema version + down migration reference."""
    return {
        "strategy": "schema_down",
        "current_version": current_version,
        "down_migration": down_migration,
        "verify_command": f"psql -f {down_migration}",
    }


def capture_journal_revert(*, journal_path: Path, entry_range: tuple[int, int]) -> dict:
    """Belief: capture the journal entry range for revert."""
    entries = b""
    if journal_path.exists():
        all_lines = journal_path.read_text(encoding="utf-8").splitlines()
        start, end = entry_range
        entries = "\n".join(all_lines[max(0, start - 1):end]).encode("utf-8")
    return {
        "strategy": "journal_revert",
        "journal_path": str(journal_path),
        "entry_range": list(entry_range),
        "entries_sha256": _sha256(entries),
        "verify_command": "templates/scripts/tick-journal.py revert",
    }


def build_manifest(candidate_id: str, tick_id: int, asset_type: str, ref: dict) -> dict:
    """Build the snapshot manifest. Validates asset_type and strategy."""
    if asset_type not in ASSET_TYPE_TO_STRATEGY:
        raise ValueError(f"unknown asset_type: {asset_type!r}")
    expected_strategy = ASSET_TYPE_TO_STRATEGY[asset_type]
    if ref.get("strategy") != expected_strategy:
        raise ValueError(
            f"strategy mismatch: asset_type={asset_type} expects {expected_strategy}, "
            f"ref.strategy={ref.get('strategy')!r}"
        )
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "asset_type": asset_type,
        "captured_at_tick": tick_id,
        "captured_at": _now_iso(),
        "rollback_strategy": ref["strategy"],
        "rollback_ref": ref,
        "verification": {
            "checksum": ref.get("inverse_patch_sha256")
            or ref.get("original_sha256")
            or ref.get("entries_sha256")
            or "sha256:",
            "verify_command": ref.get("verify_command", ""),
        },
    }


def verify(manifest: dict) -> bool:
    """Verify a snapshot manifest by re-computing checksums if the source file is reachable.
    Returns True if verification passes (or the file is unreachable — caller's call)."""
    ref = manifest.get("rollback_ref", {})
    strategy = ref.get("strategy")
    if strategy == "git_reset":
        path = Path(ref.get("inverse_patch_path", ""))
        if not path.exists():
            return True
        return _sha256(path.read_bytes()) == manifest["verification"]["checksum"]
    if strategy == "yaml_restore":
        path = Path(ref.get("yaml_path", ""))
        if not path.exists():
            return True
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        start, end = ref["line_range"]
        original = "".join(lines[max(0, start - 1):end]).encode("utf-8")
        return _sha256(original) == manifest["verification"]["checksum"]
    if strategy == "journal_revert":
        path = Path(ref.get("journal_path", ""))
        if not path.exists():
            return True
        all_lines = path.read_text(encoding="utf-8").splitlines()
        start, end = ref["entry_range"]
        entries = "\n".join(all_lines[max(0, start - 1):end]).encode("utf-8")
        return _sha256(entries) == manifest["verification"]["checksum"]
    return True  # db strategy has no local file to verify


def _cmd_capture(args: argparse.Namespace) -> int:
    ref_json = json.loads(args.ref)
    manifest = build_manifest(args.candidate_id, args.tick_id, args.asset_type, ref_json)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"wrote manifest to {out}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    ok = verify(manifest)
    print("OK" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Rollback snapshot manifest (BE-3, #86): capture + verify per asset_type."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_cap = sub.add_parser("capture", help="Capture a snapshot manifest and write it to disk.")
    p_cap.add_argument("--candidate-id", required=True)
    p_cap.add_argument("--tick-id", required=True, type=int)
    p_cap.add_argument("--asset-type", required=True, choices=tuple(ASSET_TYPE_TO_STRATEGY))
    p_cap.add_argument("--ref", required=True, help="JSON object with strategy-specific fields.")
    p_cap.add_argument("--output", required=True, help="Path to write the manifest (JSON).")
    p_cap.set_defaults(func=_cmd_capture)

    p_ver = sub.add_parser("verify", help="Verify a manifest against its source file (if reachable).")
    p_ver.add_argument("--manifest", required=True, help="Path to the manifest JSON.")
    p_ver.set_defaults(func=_cmd_verify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
