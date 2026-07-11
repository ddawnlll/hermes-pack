#!/usr/bin/env bash
# Janus Gate — two-faced meta-gate that coordinates forward (Explorer #25,
# divergence) and backward (Red Team, falsification) checks.
#
# Janus looks forward to see whether this work explores genuinely new
# territory (not regurgitating a refuted hypothesis), and backward to
# enforce the falsifiability contract (every hypothesis must make a
# concrete, testable prediction).
#
# This is a DETERMINISTIC gate (no LLM) — it checks structural properties
# of the evidence and scar-tissue records.
#
# Usage:
#   bash janus-gate.sh <evidence_bundle_path> <scar_tissue_path> <explorer_divergence_score>
#
# Args:
#   evidence_bundle_path   Path to the worker's evidence bundle (JSON)
#   scar_tissue_path       Path to scar-tissue records (objections.jsonl)
#   explorer_divergence_score  Numeric divergence score from Explorer #25 (0.0–1.0)
#
# Output (stdout): {"verdict":"PASS"|"HOLD"|"FAIL","forward":{...},"backward":{...}}
# Exit code: 0=PASS, 1=HOLD, 2=FAIL, 3=error
#
# Conventions follow prereg-lock.sh / prereg-verify.sh patterns.

set -u

PACK_DIR="$(cd "$(dirname "$0")/../../" && pwd)"
LEDGER_DIR="__HERMES_LEDGER_DIR__"
REPO="__HERMES_REPO_DIR__"

# ── Parse args ────────────────────────────────────────────────────────────────
if [ $# -lt 3 ]; then
  echo '{"verdict":"FAIL","forward":{"verdict":"error","reason":"Missing arguments"},"backward":{"verdict":"error","reason":"Usage: janus-gate.sh <evidence_bundle_path> <scar_tissue_path> <explorer_divergence_score>"}}'
  exit 3
fi

EVIDENCE_BUNDLE="$1"
SCAR_TISSUE_PATH="$2"
EXPLORER_DIVERGENCE="$3"

# ── Validate evidence bundle exists ────────────────────────────────────────────
if [ ! -f "$EVIDENCE_BUNDLE" ]; then
  echo "{\"verdict\":\"FAIL\",\"forward\":{\"verdict\":\"error\",\"reason\":\"Evidence bundle not found at ${EVIDENCE_BUNDLE}\"},\"backward\":{\"verdict\":\"error\",\"reason\":\"Evidence bundle not found, cannot evaluate falsifiability\"}}"
  exit 3
fi

# ── Validate divergence score ──────────────────────────────────────────────────
if ! echo "$EXPLORER_DIVERGENCE" | grep -qE '^[0-9]+\.?[0-9]*$'; then
  echo "{\"verdict\":\"FAIL\",\"forward\":{\"verdict\":\"error\",\"reason\":\"Invalid explorer_divergence_score '${EXPLORER_DIVERGENCE}'; must be numeric\"},\"backward\":{\"verdict\":\"error\",\"reason\":\"Invalid divergence score, cannot evaluate\"}}"
  exit 3
fi

# Convert to integer basis points for comparison (multiply by 1000, strip decimal)
DIVERGENCE_BP=$(echo "$EXPLORER_DIVERGENCE * 1000 / 1" | bc 2>/dev/null || echo 0)

# ═══════════════════════════════════════════════════════════════════════════════
# Forward Face: "Does this work explore new territory?"
# Checks scar-tissue memory for similar refuted hypotheses.
# If the hypothesis re-litigates a refuted idea without new evidence → FAIL.
# ═══════════════════════════════════════════════════════════════════════════════

FORWARD_VERDICT="PASS"
FORWARD_REASON=""
FORWARD_MATCHES=""

# Read the evidence bundle to extract hypothesis_id and metric_name
EVIDENCE_HYPOTHESIS=""
EVIDENCE_METRIC=""
if command -v python3 &>/dev/null; then
  EVIDENCE_HYPOTHESIS=$(python3 -c "
import json, sys
try:
    with open('$EVIDENCE_BUNDLE') as f:
        d = json.load(f)
    print(d.get('hypothesis_id', d.get('hypothesis', d.get('id', ''))))
except Exception:
    print('')
" 2>/dev/null)
  EVIDENCE_METRIC=$(python3 -c "
import json, sys
try:
    with open('$EVIDENCE_BUNDLE') as f:
        d = json.load(f)
    print(d.get('metric_name', d.get('metric', d.get('target_metric', ''))))
except Exception:
    print('')
" 2>/dev/null)
fi

# If scar-tissue file exists, scan for refuted hypotheses matching this one
if [ -f "$SCAR_TISSUE_PATH" ]; then
  # Count how many scar-tissue records reference a similar hypothesis or metric
  # A "match" = a prior objection whose hypothesis_id or claim_attacked overlaps
  # with the current evidence bundle's hypothesis or metric.
  if command -v python3 &>/dev/null; then
    SCAR_MATCH_RESULT=$(python3 -c "
import json, sys
hypothesis = '${EVIDENCE_HYPOTHESIS}'
metric = '${EVIDENCE_METRIC}'
matches = []
with open('${SCAR_TISSUE_PATH}') as f:
    for line_num, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Check if this scar record matches our hypothesis or metric
        record_id = record.get('hypothesis_id', record.get('objection_id', ''))
        record_claim = record.get('claim_attacked', record.get('claim', ''))
        record_status = record.get('status', record.get('resolution', ''))
        # Skip resolved/superseded objections — only match active refutations
        if record_status in ('resolved', 'superseded', 'withdrawn'):
            continue
        # Match on hypothesis_id
        if hypothesis and hypothesis == record.get('hypothesis_id', ''):
            matches.append({
                'line': line_num,
                'id': record_id,
                'reason': record.get('why', record.get('reason', 'No reason given')),
                'type': 'hypothesis_id_match'
            })
        # Match on metric name overlap
        elif metric and metric == record.get('metric_name', ''):
            matches.append({
                'line': line_num,
                'id': record_id,
                'reason': record.get('why', record.get('reason', 'No reason given')),
                'type': 'metric_match'
            })
        # Match on claim_attacked containing metric
        elif metric and metric in record_claim:
            matches.append({
                'line': line_num,
                'id': record_id,
                'reason': record.get('why', record.get('reason', 'No reason given')),
                'type': 'claim_overlap'
            })
print(json.dumps({'match_count': len(matches), 'matches': matches}))
" 2>/dev/null)
  else
    SCAR_MATCH_RESULT='{"match_count":0,"matches":[]}'
  fi

  SCAR_MATCH_COUNT=$(echo "$SCAR_MATCH_RESULT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('match_count', 0))" 2>/dev/null || echo 0)
  SCAR_MATCH_DETAIL=$(echo "$SCAR_MATCH_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d.get('matches', [])))" 2>/dev/null || echo "[]")

  if [ "$SCAR_MATCH_COUNT" -gt 0 ]; then
    FORWARD_VERDICT="FAIL"
    FORWARD_REASON="Scar-tissue match: ${SCAR_MATCH_COUNT} prior refuted hypothesis(es) match this evidence bundle"
    FORWARD_MATCHES="$SCAR_MATCH_DETAIL"
  else
    FORWARD_REASON="No scar-tissue matches — hypothesis explores new territory"
  fi
else
  FORWARD_REASON="No scar-tissue records — nothing to check (first hypothesis in family)"
fi

# Low divergence check: if divergence is extremely low (< 0.05), flag as advisory
if [ "$DIVERGENCE_BP" -lt 50 ] 2>/dev/null; then
  if [ "$FORWARD_VERDICT" = "PASS" ]; then
    # Low divergence alone doesn't fail, but annotate the reason
    FORWARD_REASON="${FORWARD_REASON}; Low divergence (${EXPLORER_DIVERGENCE}) — hypothesis closely resembles prior work"
  fi
fi

FORWARD_OUTPUT=$(cat <<JSON_FWD
{
  "verdict": "${FORWARD_VERDICT}",
  "reason": "${FORWARD_REASON}",
  "explorer_divergence": ${EXPLORER_DIVERGENCE},
  "scar_matches": ${FORWARD_MATCHES:-[]}
}
JSON_FWD
)

# ═══════════════════════════════════════════════════════════════════════════════
# Backward Face: "Is this work falsifiable?" (Falsifiability Contract)
# Checks if the hypothesis makes a concrete, testable prediction.
# If no concrete prediction → HOLD (advisory).
# ═══════════════════════════════════════════════════════════════════════════════

BACKWARD_VERDICT="PASS"
BACKWARD_REASON=""

# Parse the evidence bundle for falsifiability criteria
if command -v python3 &>/dev/null; then
  FALSIFIABILITY_CHECK=$(python3 -c "
import json, sys
try:
    with open('${EVIDENCE_BUNDLE}') as f:
        d = json.load(f)
except Exception:
    print(json.dumps({'has_prediction': False, 'has_metric': False, 'has_threshold': False, 'has_direction': False, 'prediction_text': ''}))
    sys.exit(0)

has_prediction = bool(d.get('prediction') or d.get('testable_prediction') or d.get('hypothesis_prediction'))
has_metric = bool(d.get('metric_name') or d.get('metric') or d.get('target_metric'))
has_threshold = bool(d.get('threshold') or d.get('target') or d.get('success_threshold'))
has_direction = bool(d.get('direction') or d.get('comparison') or d.get('improvement_direction'))
prediction_text = d.get('prediction', d.get('testable_prediction', d.get('hypothesis_prediction', '')))

print(json.dumps({
    'has_prediction': has_prediction,
    'has_metric': has_metric,
    'has_threshold': has_threshold,
    'has_direction': has_direction,
    'prediction_text': prediction_text
}))
" 2>/dev/null)
else
  FALSIFIABILITY_CHECK='{"has_prediction":false,"has_metric":false,"has_threshold":false,"has_direction":false,"prediction_text":""}'
fi

HAS_PREDICTION=$(echo "$FALSIFIABILITY_CHECK" | python3 -c "import json,sys; print(json.load(sys.stdin).get('has_prediction', False))" 2>/dev/null || echo "False")
HAS_METRIC=$(echo "$FALSIFIABILITY_CHECK" | python3 -c "import json,sys; print(json.load(sys.stdin).get('has_metric', False))" 2>/dev/null || echo "False")
HAS_THRESHOLD=$(echo "$FALSIFIABILITY_CHECK" | python3 -c "import json,sys; print(json.load(sys.stdin).get('has_threshold', False))" 2>/dev/null || echo "False")
HAS_DIRECTION=$(echo "$FALSIFIABILITY_CHECK" | python3 -c "import json,sys; print(json.load(sys.stdin).get('has_direction', False))" 2>/dev/null || echo "False")
PREDICTION_TEXT=$(echo "$FALSIFIABILITY_CHECK" | python3 -c "import json,sys; print(json.load(sys.stdin).get('prediction_text', ''))" 2>/dev/null || echo "")

# The hypothesis is falsifiable if it has ALL of: a prediction, a metric, a threshold, and a direction
# Missing any one → HOLD (advisory)
# Missing all → FAIL
FALSIFIABLE_FIELDS=0
MISSING_FIELDS=""

if [ "$HAS_PREDICTION" = "True" ]; then
  FALSIFIABLE_FIELDS=$((FALSIFIABLE_FIELDS + 1))
else
  MISSING_FIELDS="${MISSING_FIELDS} prediction"
fi

if [ "$HAS_METRIC" = "True" ]; then
  FALSIFIABLE_FIELDS=$((FALSIFIABLE_FIELDS + 1))
else
  MISSING_FIELDS="${MISSING_FIELDS} metric"
fi

if [ "$HAS_THRESHOLD" = "True" ]; then
  FALSIFIABLE_FIELDS=$((FALSIFIABLE_FIELDS + 1))
else
  MISSING_FIELDS="${MISSING_FIELDS} threshold"
fi

if [ "$HAS_DIRECTION" = "True" ]; then
  FALSIFIABLE_FIELDS=$((FALSIFIABLE_FIELDS + 1))
else
  MISSING_FIELDS="${MISSING_FIELDS} direction"
fi

if [ "$FALSIFIABLE_FIELDS" -ge 4 ]; then
  BACKWARD_VERDICT="PASS"
  BACKWARD_REASON="Hypothesis is falsifiable: prediction + metric + threshold + direction all present"
elif [ "$FALSIFIABLE_FIELDS" -ge 1 ]; then
  BACKWARD_VERDICT="HOLD"
  BACKWARD_REASON="Hypothesis is partially falsifiable (${FALSIFIABLE_FIELDS}/4 fields present). Missing:${MISSING_FIELDS}. Add a concrete, testable prediction with metric, threshold, and direction."
else
  BACKWARD_VERDICT="HOLD"
  BACKWARD_REASON="Hypothesis is NOT falsifiable (0/4 fields present). A hypothesis must make a concrete, testable prediction with a measurable metric, threshold, and direction of improvement."
fi

BACKWARD_OUTPUT=$(cat <<JSON_BCK
{
  "verdict": "${BACKWARD_VERDICT}",
  "reason": "${BACKWARD_REASON}",
  "falsifiability": {
    "has_prediction": ${HAS_PREDICTION},
    "has_metric": ${HAS_METRIC},
    "has_threshold": ${HAS_THRESHOLD},
    "has_direction": ${HAS_DIRECTION},
    "fields_present": ${FALSIFIABLE_FIELDS},
    "fields_required": 4
  }
}
JSON_BCK
)

# ═══════════════════════════════════════════════════════════════════════════════
# Combine verdicts
# Forward FAIL is binding (the worker re-litigated a refuted idea).
# Backward HOLD is advisory (the hypothesis should be fixed but doesn't block).
# Both PASS → overall PASS.
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$FORWARD_VERDICT" = "FAIL" ]; then
  OVERALL_VERDICT="FAIL"
  OVERALL_REASON="Forward face failed: ${FORWARD_REASON}"
elif [ "$BACKWARD_VERDICT" = "HOLD" ]; then
  OVERALL_VERDICT="HOLD"
  OVERALL_REASON="Backward face advisory: ${BACKWARD_REASON}"
elif [ "$FORWARD_VERDICT" = "PASS" ] && [ "$BACKWARD_VERDICT" = "PASS" ]; then
  OVERALL_VERDICT="PASS"
  OVERALL_REASON="Both faces pass: hypothesis explores new territory and is falsifiable"
else
  OVERALL_VERDICT="FAIL"
  OVERALL_REASON="Unexpected state: forward=${FORWARD_VERDICT}, backward=${BACKWARD_VERDICT}"
fi

# ── Output JSON ────────────────────────────────────────────────────────────────
cat <<JSON
{
  "verdict": "${OVERALL_VERDICT}",
  "reason": "${OVERALL_REASON}",
  "forward": ${FORWARD_OUTPUT},
  "backward": ${BACKWARD_OUTPUT}
}
JSON

# ── Exit with appropriate code ─────────────────────────────────────────────────
case "$OVERALL_VERDICT" in
  PASS) exit 0 ;;
  HOLD) exit 1 ;;
  FAIL) exit 2 ;;
  *)    exit 3 ;;
esac
