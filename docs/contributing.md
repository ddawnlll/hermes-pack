# Contributing

Thanks for your interest in Hephaestus! This project follows strict evidence-gated
discipline — contributions are no exception.

## Quick links

- [Code of Conduct](#code-of-conduct)
- [Development setup](#development-setup)
- [Pull request process](#pull-request-process)
- [Issue tracking](#issue-tracking)
- [Style guide](#style-guide)
- [Testing requirements](#testing-requirements)

## Code of conduct

Be respectful. Disagree on substance, not on people. The Hephaestus system itself
is designed to disagree on substance — model decorrelation, Red Team objections,
and Reflector consolidation all exist because we believe adversarial collaboration
produces better outcomes than consensus theater. Bring that energy.

## Development setup

```bash
# Clone
git clone https://github.com/ddawnlll/hephaestus.git
cd hephaestus

# Install Praxis (for evidence verification)
git clone https://github.com/ddawnlll/praxis.git tools/praxis
cd tools/praxis && bun install && cd ../..

# Install mkdocs (for local docs preview)
pip3 install --user --break-system-packages -r requirements-docs.txt

# Run the full test suite
python3 -m pytest schema/tests/ -v

# Build the docs locally
PATH="$HOME/Library/Python/3.14/bin:$PATH" mkdocs serve
```

The docs will be available at <http://localhost:8000>.

## Pull request process

1. **Open or claim an issue first.** Hephaestus issues are pre-tracked with acceptance
   criteria. If your PR doesn't close an issue, open one first describing the
   problem and the proposed solution.
2. **Branch from `main`.** Branch naming: `<type>/<issue-number>-<slug>`.
   Examples: `fix/65-blinker-merge`, `feat/42-new-channel`, `docs/41-readme-toc`.
3. **Add tests.** Every behavior change needs a test. The canary suite has 11
   scenarios — new feature flags need canary tests, new channels need provenance
   recording tests, new SOULs need identity / authority tests.
4. **Run the full test matrix locally** before pushing:

   ```bash
   python3 schema/tests/test_correction_pass.py
   python3 schema/tests/test_canary_suite.py
   python3 schema/tests/test_self_grade_diff.py
   python3 -m pytest schema/tests/ -v
   ```

5. **CI must pass.** PRs without green CI won't be reviewed.
6. **Praxis verification.** For PRs that change scripts, schemas, or
   `bootstrap.sh`/`bootstrap.ts`, include a `.praxis/planspec.yaml` and a
   `.praxis/runs/<id>.jsonl` evidence bundle. See the v0.5 evidence bundle for
   the format.
7. **No drive-by refactors.** Touch only what the task needs. Reformatting
   unrelated code makes diffs hard to review and history hard to bisect.
8. **Match the surrounding style.** KISS, DRY, elitist, shorthand, clever, concise,
   efficient, elegant.
9. **One PR per issue.** If your fix touches multiple issues, split into multiple
   PRs.

## Issue tracking

Hephaestus uses GitHub Issues with a phased label system:

| Label | Purpose |
|---|---|
| `P0` | Foundation / blocker — must land first |
| `P1` | Core value |
| `P2` | Operations / polish |
| `phase-0-debt` | v0.4 debt, prerequisite for v0.5 |
| `phase-1-workspace` | Belief workspace + Reflector |
| `phase-2-containment` | Conflict containment |
| `phase-3-channels` | Idea channels |
| `phase-4-measurement` | Provenance + hit-rate |
| `kaizen-engine` | v0.5 umbrella label |

When opening an issue, use the appropriate phase label. Issues without phase labels
are triaged weekly.

## Style guide

### Bash

- `set -u` and `set -o pipefail` at the top of every script
- `[[ ]]` over `[ ]` for conditionals
- Functions over inline code
- Quote all variables: `"$VAR"` not `$VAR`
- Prefer `command -v` over `which`

### Python

- Python 3.11+ (scripts use type hints)
- `argparse` over raw `sys.argv`
- Pathlib over `os.path`
- `print(..., file=sys.stderr)` for errors
- Fail closed: `sys.exit(1)` on any non-trivial error

### Markdown

- ATX headers (`#`), not Setext (`=====`).
- Sentence case for titles.
- Reference-style links for repeated URLs.
- Code blocks with language hints.
- Tables for any structured data with 3+ rows.

### YAML

- 2-space indentation.
- Quote strings containing special chars or that look like numbers/bools.
- Use `|` for multi-line strings, `>` for folded.
- Comments at the top of every file explaining purpose.

## Testing requirements

### Unit tests

- Place in `schema/tests/test_*.py`
- Use plain `unittest` or `pytest` (not both in the same file)
- Tests must be **deterministic** — no network, no timing dependencies
- Use temporary directories (e.g., `tempfile.TemporaryDirectory()`)
- Tests should not require API keys

### Integration tests

- Place in `schema/tests/test_*_integration.py`
- May use subprocess to call scripts
- Must clean up after themselves
- May require local Praxis install

### Canary tests

- Place in `schema/tests/test_canary_*.py`
- Multi-scenario end-to-end coverage
- Each scenario tests one invariant from the v0.5 spec
- Failure messages must point to the invariant

## What NOT to contribute

- **Opinionated LLM-as-judge replacements** for deterministic gates. The whole
  point of Hephaestus is that the deterministic gates come first.
- **Project-specific hardcoding** in templates or bootstrap. Use `__HERMES_*__`
  template variables or adapter overrides.
- **Auto-merge of critical decisions** when T4 (human) is the only legitimate
  authority. AFK mode parks with HOLD, not auto-merge.
- **Memory writes from workers.** Only the orchestrator (after Praxis PASS) and
  the gate verdict may write canonical memory.

## License

By contributing, you agree that your contributions will be licensed under the
project's MIT license.
