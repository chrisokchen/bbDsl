# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**BBDSL** (Bridge Bidding Description Specification Language) is a domain-specific language for describing bridge bidding systems in structured, machine-readable YAML. It bridges the semantic gap between existing formats (BML, BBOalert, Dealer, PBN) by providing verifiable logic, AI-readable semantics, and ecosystem interoperability.

**Current status**: Phase 1 complete (Sprint 1.1 + 1.2 + 1.3). Python package with CLI, models, loader, expander, validator, and BML importer are all implemented and tested (141 tests, 82% coverage).

## Canonical References

- **BBDSL-SPEC-v0.3.md** — Core specification (hand constraints, bidding semantics, opponent patterns, validation rules)
- **BBDSL-SUPPLEMENT-v0.3.md** — Design refinements (selection rules, PBN bridge, BML import mapping, BSS/LIN compatibility)
- **BBDSL_IMPLEMENTATION-PLAN.md** — 5-phase / 32-week roadmap with sprint breakdowns and Pydantic model examples
- **bbdsl-schema-v0.3.json** — JSON Schema (draft-07) for external validation

## Planned Tech Stack (Phase 1)

Python 3.11+, Pydantic v2 (strict mode), ruamel.yaml, jsonschema, Click (CLI), Jinja2 (templates), pytest + hypothesis (testing), mkdocs-material (docs). Package management via **uv** (`pyproject.toml` + `uv.lock`).

### Commands

```bash
uv run pytest tests/                             # All tests
uv run pytest tests/test_core/test_validator.py  # Single test file
uv run ruff check bbdsl/ tests/                  # Lint
uv run ruff format bbdsl/ tests/                 # Format
```

### CLI (all implemented)

```bash
uv run bbdsl load <file>.bbdsl.yaml              # Load and print summary
uv run bbdsl expand <file>.bbdsl.yaml            # Expand foreach_suit
uv run bbdsl validate <file>.bbdsl.yaml          # Run 10 validation rules
uv run bbdsl validate <file>.yaml --rules val-002,val-008  # Specific rules
uv run bbdsl import bml <file>.bml               # Import BML → BBDSL YAML
uv run bbdsl import bml <file>.bml -n "Name" -o out.yaml  # With options
uv run bbdsl schema                              # Generate JSON Schema
```

Exit codes: `validate` and `import bml` return 0=pass, 1=warnings, 2=errors.

## Architecture

```
Declarative YAML → Pydantic Models → Validation → Export (BBOalert/BML/PBN/AI KB)
```

Key architectural patterns:

1. **Modular Conventions**: Independent `.bbdsl-conv.yaml` files with namespace IDs (`bbdsl/stayman-v1`, `chris/precision-relay-v2`). Conventions declare parameters, conflicts, and dependencies.

2. **foreach_suit Expansion**: Write-time macro that expands suit templates. Variables: `${M}`, `${M.lower}`, `${M.zh-TW}`, `${M.symbol}`, `${M.rank}`, `${M.other}`, `${M.transfer_from}`. Max 2-level nesting.

3. **Context Overrides**: Base system + seat/vulnerability-specific overrides. Opponent action patterns use 9 syntax forms (concrete bids, ranges, types, logical combinations).

4. **Selection Rules Engine** (Phase 2+): Priority-based bid selection with Dealer-compatible expression conditions. Ordered evaluation, first match wins.

5. **14 Validation Rules**: From HCP coverage gaps (val-001) through convention ID format (val-011) to selection rule exhaustiveness (val-014). Each rule has type (error/warning) and scope.

### Package Structure (Phase 1 implemented)

```
bbdsl/
├── models/       # Pydantic v2 models: common, bid, convention, context, system
├── core/         # loader.py, expander.py, validator.py
├── importers/    # bml_importer.py (BML → BBDSL, with UnresolvedNode for failures)
├── exporters/    # (Phase 2+)
├── viewer/       # (Phase 3+)
├── ai/           # (Phase 4+)
└── cli/main.py   # Click CLI: load, expand, validate, import bml, schema
```

Key modules:
- `bbdsl/core/expander.py` — SUIT_META + foreach_suit recursive expansion
- `bbdsl/core/validator.py` — 10 rules (8 real + 2 stubs); ValidationResult/Report
- `bbdsl/importers/bml_importer.py` — parse_bml_text, extract_semantics, import_bml

## Coding Conventions

- **Language**: Documentation in Traditional Chinese (繁體中文); code follows PEP 8
- 4 spaces indentation, max 79 chars per line
- Descriptive variable names (`total_price` not `tp`), CamelCase for classes
- Imports ordered: standard → third-party → local, with blank lines between groups
- f-strings for string formatting
- Pydantic models with strict validation and type hints
- i18n strings use `{ zh-TW: "...", en: "..." }` dicts
- IDs use snake_case internally, `scope/name-vN` for convention namespaces

## Workflow Skills (`.claude/skills/`)

- **es-kick-off-discovery**: Event Storming to clarify raw user ideas into structured specs
- **formulation**: Transform ES output into feature files, API specs, and entity models
- **new-requirement**: Handle incremental requirement changes across all spec artifacts

## Key Architectural Decisions (ADR)

See `BBDSL_IMPLEMENTATION-PLAN.md` § 架構決策記錄 for full details:

- **ADR-1**: Dual licensing — MIT (code) + CC-BY-SA-4.0 (convention files)
- **ADR-4**: `UnresolvedNode` polymorphic type for BML import failures (no `_` prefix fields)
- **ADR-5**: `OpponentPattern` is pure data; matching logic lives in `core/opponent_matcher.py`
- **ADR-7**: Phase 5 (community platform) is a separate repo

## Key Example

`process/1-discover/sayc.bbdsl.yaml` — Standard American Yellow Card system in BBDSL format.
