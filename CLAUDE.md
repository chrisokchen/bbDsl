# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**BBDSL** (Bridge Bidding Description Specification Language) is a domain-specific language for describing bridge bidding systems in structured, machine-readable YAML. It bridges the semantic gap between existing formats (BML, BBOalert, Dealer, PBN) by providing verifiable logic, AI-readable semantics, and ecosystem interoperability.

**Current status**: Phase 4.3 complete. 851 tests, 82% coverage. All sprints 1.1–4.3 implemented.

## Canonical References

- **BBDSL-SPEC-v0.3.md** — Core specification (hand constraints, bidding semantics, opponent patterns, validation rules)
- **BBDSL-SUPPLEMENT-v0.3.md** — Design refinements (selection rules, PBN bridge, BML import mapping, BSS/LIN compatibility)
- **BBDSL_IMPLEMENTATION-PLAN.md** — 5-phase / 32-week roadmap with sprint breakdowns and Pydantic model examples
- **bbdsl-schema-v0.3.json** — JSON Schema (draft-07) for external validation

## Tech Stack

Python 3.11+, Pydantic v2 (strict mode), ruamel.yaml, jsonschema, Click (CLI), Jinja2 (templates), pytest (testing). Package management via **uv** (`pyproject.toml` + `uv.lock`).

### Test & Lint Commands

```bash
uv run pytest tests/                                        # All tests
uv run pytest tests/test_core/test_validator.py            # Single test file
uv run pytest tests/test_core/test_validator.py::TestVal002NoOverlap -v  # Single class
uv run ruff check bbdsl/ tests/                            # Lint
uv run ruff format bbdsl/ tests/                           # Format
```

### CLI (all implemented)

```bash
# Core
uv run bbdsl load <file>.bbdsl.yaml
uv run bbdsl expand <file>.bbdsl.yaml [-o out.json]
uv run bbdsl validate <file>.bbdsl.yaml [--rules val-002,val-008] [-o report.json]
uv run bbdsl schema

# Import
uv run bbdsl import bml <file>.bml [-n "Name"] [-o out.yaml]
uv run bbdsl import bboalert <file>.bboalert [-n "Name"] [-o out.yaml]

# Export
uv run bbdsl export bml <path> [-o out.bml] [--locale zh-TW] [--suit-symbols]
uv run bbdsl export bboalert <path> [-o out.bboalert] [--locale zh-TW]
uv run bbdsl export html <path> [-o out.html] [--locale zh-TW] [--suit-symbols] [--title "Title"]
uv run bbdsl export convcard <path> [-o out.html] [--style wbf|acbl] [--locale zh-TW]
uv run bbdsl export svg <path> [-o out.svg] [--max-depth 2] [--suit-symbols]
uv run bbdsl export ai-kb <path> [-o out.jsonl] [--format json|jsonl] [--locale zh-TW]
uv run bbdsl export dealer <path> [-o out.dds] [--seat south] [--locale zh-TW]
uv run bbdsl export pbn <path> [-o out.pbn] [--deals 10] [--seed 42] [--dealer N]

# Simulation & Comparison
uv run bbdsl simulate <path> [-n 5] [--seed 42] [--dealer N] [-o out.json]
uv run bbdsl compare <path_a> <path_b> [-n 50] [--seed 42] [-o report.json] [--locale zh-TW]
uv run bbdsl select <path> --hcp 18 [--hearts 5] [--shape balanced]
uv run bbdsl quiz <path> [-o out.html] [--locale zh-TW] [-n 20] [--seed N]
```

Exit codes: `validate` and `import` commands return 0=pass, 1=warnings, 2=errors.

## Architecture

```
Declarative YAML → Pydantic Models → Validation → Simulation → Export
```

Key architectural patterns:

1. **Modular Conventions**: Independent `.bbdsl-conv.yaml` files with namespace IDs (`bbdsl/stayman-v1`). Conventions declare parameters, conflicts, and dependencies.

2. **foreach_suit Expansion**: Write-time macro expanding suit templates. Variables: `${M}`, `${M.lower}`, `${M.zh-TW}`, `${M.symbol}`, `${M.rank}`, `${M.other}`, `${M.transfer_from}`. Max 2-level nesting.

3. **Context Overrides**: Base system + seat/vulnerability-specific overrides. Opponent action patterns use 9 syntax forms (concrete bids, ranges, types, logical combinations).

4. **Selection Rules Engine**: Priority-based bid selection with Dealer-compatible expression conditions. Ordered evaluation, first match wins (`bbdsl/core/selector.py`).

5. **14 Validation Rules**: HCP coverage gaps (val-001), bid overlap (val-002), through convention ID format (val-011), selection rule exhaustiveness (val-014). Each has type (error/warning) and scope.

6. **Simulation Engine**: Two-phase random deal generation (rejection sampling from 52-card deck). Auction tree navigation by `ns_path` (N/S non-Pass bids): even depth → responses, odd depth → continuations.

### Package Structure

```
bbdsl/
├── models/         # Pydantic v2: common.py, bid.py, convention.py, context.py, system.py
├── core/
│   ├── loader.py          # load_document() → BBDSLDocument
│   ├── expander.py        # expand_document(), foreach_suit, SUIT_META
│   ├── validator.py       # Validator, ValidationResult/Report (14 rules)
│   ├── selector.py        # evaluate_condition(), select_opening()
│   ├── hand_generator.py  # BridgeHand, generate_hand(), two-phase rejection sampling
│   ├── quiz_generator.py  # QuizQuestion, generate_quiz()
│   ├── sim_engine.py      # Deal, AuctionStep, SimulationResult, generate_deal(), simulate()
│   ├── comparator.py      # DiffCase, ComparisonReport, compare_systems()
│   └── dealer_bridge.py   # constraint_to_dealer(), openings_to_dealer_script()
├── exporters/
│   ├── bml_exporter.py        # export_bml() → indented BML
│   ├── bboalert_exporter.py   # export_bboalert() → CSV
│   ├── html_exporter.py       # export_html() → interactive HTML viewer
│   ├── convcard_exporter.py   # export_convcard() → printable convention card HTML
│   ├── svg_tree.py            # export_svg() → SVG bidding tree
│   ├── quiz_exporter.py       # export_quiz() → interactive HTML quiz
│   ├── ai_kb_exporter.py      # export_ai_kb() → JSON/JSONL for RAG
│   └── pbn_exporter.py        # export_pbn() → PBN牌譜（含[Note]嵌入BBDSL語義）
├── importers/
│   ├── bml_importer.py        # import_bml(), UnresolvedNode for parse failures
│   └── bboalert_importer.py   # import_bboalert()
└── cli/main.py    # Click CLI: all commands above
examples/
├── precision.bbdsl.yaml     # Precision Club (9 openings, all 14 rules pass)
├── sayc.bbdsl.yaml          # SAYC (14 openings, all 14 rules pass)
└── two_over_one.bbdsl.yaml  # 2/1 GF (9 openings, all 14 rules pass)
```

## Coding Conventions

- **Language**: Documentation in Traditional Chinese (繁體中文); code follows PEP 8
- 4 spaces indentation, max 79 chars per line; f-strings for formatting
- Pydantic models with strict validation and type hints
- i18n strings use `{ zh-TW: "...", en: "..." }` dicts
- IDs use snake_case internally, `scope/name-vN` for convention namespaces
- `Author` model: `{name: str, contact: str|None, role: str|None}` — not a plain string

## Key Implementation Notes

- **Deal generation**: 52-card deck shuffled and split 4×13; each card appears exactly once
- **Auction termination**: 3 consecutive Passes after a non-Pass bid, OR 4 initial Passes (passed out), OR max 40 steps
- **PBN Note tag**: Only N/S non-Pass bids shown; format `"BBDSL: {system} | N:1C(16+ HCP) | S:1D(neg)"`
- **val-002 overlap**: Conservative — only flags same suit + overlapping HCP ranges + neither artificial + neither has shape ref
- **UnresolvedNode**: `{is_unresolved: true, bml_original: ..., reason: ...}` (no `_` prefix)
- **Fixtures**: Use `authors: [{name: "Test"}]` not `authors: ["Test"]`
- **selection_rules format**: Top-level dict with either `rules: [...]` or `{group_name: {rules: [...]}}`

## Key Architectural Decisions (ADR)

See `BBDSL_IMPLEMENTATION-PLAN.md` § 架構決策記錄 for full details:

- **ADR-1**: Dual licensing — MIT (code) + CC-BY-SA-4.0 (convention files)
- **ADR-4**: `UnresolvedNode` polymorphic type for BML import failures
- **ADR-5**: `OpponentPattern` is pure data; matching logic lives in `core/opponent_matcher.py`
- **ADR-7**: Phase 5 (community platform) is a separate repo

## Workflow Skills (`.claude/skills/`)

- **es-kick-off-discovery**: Event Storming to clarify raw user ideas into structured specs
- **formulation**: Transform ES output into feature files, API specs, and entity models
- **new-requirement**: Handle incremental requirement changes across all spec artifacts
