# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**BBDSL** (Bridge Bidding Description Specification Language) is a domain-specific language for describing bridge bidding systems in structured, machine-readable YAML. It bridges the semantic gap between existing formats (BML, BBOalert, Dealer, PBN) by providing verifiable logic, AI-readable semantics, and ecosystem interoperability.

**Current status**: Pre-implementation — v0.3 specification is complete, no Python code yet. Ready for Phase 1 kickoff.

## Canonical References

- **BBDSL-SPEC-v0.3.md** — Core specification (hand constraints, bidding semantics, opponent patterns, validation rules)
- **BBDSL-SUPPLEMENT-v0.3.md** — Design refinements (selection rules, PBN bridge, BML import mapping, BSS/LIN compatibility)
- **BBDSL_IMPLEMENTATION-PLAN.md** — 5-phase / 32-week roadmap with sprint breakdowns and Pydantic model examples
- **bbdsl-schema-v0.3.json** — JSON Schema (draft-07) for external validation

## Planned Tech Stack (Phase 1)

Python 3.11+, Pydantic v2 (strict mode), ruamel.yaml, jsonschema, Click (CLI), Jinja2 (templates), pytest + hypothesis (testing), mkdocs-material (docs). Package management via `uv` or `poetry`.

### Expected Commands (once implementation begins)

```bash
pytest tests/                              # All tests
pytest tests/test_core/test_validator.py   # Single test file
ruff check bbdsl/ tests/                   # Lint
ruff format bbdsl/ tests/                  # Format
```

### Expected CLI

```bash
bbdsl load <file>.bbdsl.yaml       # Load and validate
bbdsl expand <file>.bbdsl.yaml     # Expand foreach_suit
bbdsl validate <file>.bbdsl.yaml   # Run 14 validation rules
bbdsl import bml <file>.bml        # Import from BML
bbdsl export bboalert <file>.yaml  # Export to BBOalert (Phase 2+)
```

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

### Planned Package Structure

```
bbdsl/
├── models/       # Pydantic v2 models
├── core/         # Loader, validator, foreach_suit expander
├── importers/    # BML, BBOalert importers
├── exporters/    # BBOalert, BML, PBN, Convention Card, AI KB exporters
├── viewer/       # HTML interactive viewer (Phase 3)
├── ai/           # AI KB export, simulation (Phase 4)
└── cli/          # Click-based CLI
```

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

## Key Example

`process/1-discover/sayc.bbdsl.yaml` — Standard American Yellow Card system in BBDSL format.
