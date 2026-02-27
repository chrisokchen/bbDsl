"""BBOalert → BBDSL importer.

Parses BBOalert CSV format (context, call, explanation) and reconstructs
a BBDSL bidding tree. Uses the same semantic extractor as the BML importer.
Descriptions that yield no hand constraints become UnresolvedNode blocks (ADR-4).

BBOalert CSV format:
    context,call,explanation
    ,1C,16+ HCP; artificial [Alert]
    1C,1D,0-7 HCP; artificial [Alert]
    1C,1H,8+ HCP; 5+ hearts [GF]
    1C-1H,2H,6-9 HCP; 3+ hearts; raise
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any

from bbdsl.importers.bml_importer import extract_semantics

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

BBORow = tuple[str, str, str]  # (context, call, explanation)


def parse_bboalert_text(text: str) -> list[BBORow]:
    """Parse BBOalert CSV text into (context, call, explanation) tuples.

    Skips comment lines (starting with '#') and blank lines.
    """
    rows: list[BBORow] = []
    reader = csv.reader(io.StringIO(text))
    for line_parts in reader:
        # Skip comment lines and blank lines
        raw = ','.join(line_parts).strip()
        if not raw or raw.startswith('#'):
            continue
        if len(line_parts) < 2:
            continue
        context = line_parts[0].strip()
        call = line_parts[1].strip().upper()
        explanation = line_parts[2].strip() if len(line_parts) > 2 else ''
        if call:
            rows.append((context, call, explanation))
    return rows


def parse_bboalert_file(path: Path) -> list[BBORow]:
    """Parse a BBOalert file and return its rows."""
    text = path.read_text(encoding='utf-8')
    return parse_bboalert_text(text)


# ---------------------------------------------------------------------------
# Tree builder
# ---------------------------------------------------------------------------

def _row_to_bid_dict(call: str, explanation: str) -> dict[str, Any]:
    """Convert a single BBOalert row to a BBDSL BidNode dict."""
    semantics = extract_semantics(explanation)
    resolved = semantics.pop('_resolved')
    reason = semantics.pop('_reason')
    orig_desc = semantics.pop('description')

    if not resolved:
        return {
            'bid': call,
            'is_unresolved': True,
            'bml_original': orig_desc,
            'reason': reason,
        }

    bid_dict: dict[str, Any] = {'bid': call}
    meaning: dict[str, Any] = {}

    if orig_desc:
        meaning['description'] = {'en': orig_desc}

    hand = semantics.pop('hand', None)
    if hand:
        meaning['hand'] = hand

    for key in ('forcing', 'artificial', 'alertable', 'preemptive'):
        val = semantics.get(key)
        if val is not None:
            meaning[key] = val

    if meaning:
        bid_dict['meaning'] = meaning

    return bid_dict


def _build_tree_from_rows(rows: list[BBORow]) -> list[dict[str, Any]]:
    """Reconstruct a nested BBDSL bid tree from flat (context, call, explanation) rows.

    Algorithm:
    1. For each row, compute full path = context_parts + [call]
    2. Insert into a path-keyed dict
    3. Build nested structure bottom-up
    """
    # path_str → bid_dict (mutable, children added later)
    node_map: dict[str, dict[str, Any]] = {}
    # Preserve insertion order for siblings
    order: list[str] = []

    for context, call, explanation in rows:
        if not call:
            continue
        ctx_parts = [p for p in context.split('-') if p] if context else []
        path_parts = ctx_parts + [call]
        path_key = '-'.join(path_parts)

        if path_key not in node_map:
            bid_dict = _row_to_bid_dict(call, explanation)
            node_map[path_key] = bid_dict
            order.append(path_key)
        # else: duplicate path, skip (keep first)

    # Wire children into parents
    for path_key in order:
        parts = path_key.split('-')
        if len(parts) <= 1:
            continue  # root node, no parent
        parent_key = '-'.join(parts[:-1])
        if parent_key in node_map:
            parent = node_map[parent_key]
            parent.setdefault('responses', []).append(node_map[path_key])

    # Return only root nodes (depth 1 = single bid in path)
    roots = [node_map[k] for k in order if '-' not in k]
    return roots


def _count_unresolved(nodes: list[dict]) -> int:
    count = 0
    for node in nodes:
        if node.get('is_unresolved'):
            count += 1
        for child_key in ('responses', 'continuations'):
            children = node.get(child_key)
            if children:
                count += _count_unresolved(children)
    return count


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def import_bboalert(
    path: Path,
    system_name: str | None = None,
    output_path: Path | None = None,
) -> tuple[dict[str, Any], int]:
    """Import a BBOalert CSV file to a BBDSL document dict.

    Returns:
        (doc_dict, n_unresolved)
    """
    from ruamel.yaml import YAML

    rows = parse_bboalert_file(path)
    roots = _build_tree_from_rows(rows)

    name = system_name or path.stem.replace('_', ' ').replace('-', ' ').title()
    doc_dict: dict[str, Any] = {
        'bbdsl': '0.3',
        'system': {'name': {'en': name}},
        'openings': roots,
    }

    n_unresolved = _count_unresolved(roots)

    if output_path:
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.allow_unicode = True
        yaml.width = 120
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            if n_unresolved:
                f.write(
                    f'# BBDSL import from BBOalert: {path.name}\n'
                    f'# WARNING: {n_unresolved} unresolved node(s) need manual fixing.\n\n'
                )
            yaml.dump(doc_dict, f)

    return doc_dict, n_unresolved
