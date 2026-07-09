"""Verify Issue #8: Challenger/arbiter profiles in project.yaml."""
import os
import sys
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_challenger_chain_exists():
    """project.yaml must have challenger_model and challenger_chain."""
    data = load_yaml(os.path.join(REPO_ROOT, "adapters", "v7-alphaforge", "project.yaml"))
    provider = data["hermes"]["provider"]
    assert "challenger_model" in provider, "challenger_model not found"
    assert "challenger_chain" in provider, "challenger_chain not found"
    assert isinstance(provider["challenger_chain"], list), "challenger_chain must be a list"
    assert len(provider["challenger_chain"]) > 0, "challenger_chain is empty"


def test_arbiter_chain_exists():
    """project.yaml must have arbiter_model and arbiter_chain."""
    data = load_yaml(os.path.join(REPO_ROOT, "adapters", "v7-alphaforge", "project.yaml"))
    provider = data["hermes"]["provider"]
    assert "arbiter_model" in provider, "arbiter_model not found"
    assert "arbiter_chain" in provider, "arbiter_chain not found"
    assert isinstance(provider["arbiter_chain"], list), "arbiter_chain must be a list"
    assert len(provider["arbiter_chain"]) > 0, "arbiter_chain is empty"


def test_challenger_different_from_orchestrator():
    """Challenger model should differ from orchestrator model for independence."""
    data = load_yaml(os.path.join(REPO_ROOT, "adapters", "v7-alphaforge", "project.yaml"))
    provider = data["hermes"]["provider"]
    chall = provider["challenger_chain"][0]
    orch = provider["orchestrator_chain"][0]
    assert chall != orch, "challenger_chain[0] should differ from orchestrator_chain[0]"


def test_arbiter_premium():
    """Arbiter should use a premium model (claude-sonnet)."""
    data = load_yaml(os.path.join(REPO_ROOT, "adapters", "v7-alphaforge", "project.yaml"))
    provider = data["hermes"]["provider"]
    arbiter = provider["arbiter_chain"][0]
    assert "claude-sonnet" in arbiter.lower(), f"arbiter_chain[0] should be premium, got: {arbiter}"


def _gating():
    """Helper: return risk_based_gating dict from project.yaml (top-level praxis key)."""
    data = load_yaml(os.path.join(REPO_ROOT, "adapters", "v7-alphaforge", "project.yaml"))
    return data["praxis"]["risk_based_gating"]


def test_risk_based_gating_sections_exist():
    """risk_based_gating must have low/medium/high/critical sections."""
    gating = _gating()
    for level in ("low", "medium", "high", "critical"):
        assert level in gating, f"risk_based_gating.{level} not found"
        assert isinstance(gating[level], dict), f"risk_based_gating.{level} must be a dict"


def test_risk_based_gating_low_has_challenger_false():
    """risk_based_gating.low should have challenger: false."""
    gating = _gating()
    assert gating["low"].get("challenger") is False, "low risk should have challenger: false"


def test_risk_based_gating_critical_human_always():
    """risk_based_gating.critical should have human_always: true."""
    gating = _gating()
    assert gating["critical"].get("human_always") is True, "critical should have human_always: true"


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
