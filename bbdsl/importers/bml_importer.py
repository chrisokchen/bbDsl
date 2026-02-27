"""BML (Bridge Markup Language) importer → BBDSL YAML.

Supports a simple indented BML format:
    <bid>  <description>   (top-level opening)
      <bid>  <description> (response, indented 2+ spaces)

Lines starting with # are comments; blank lines are ignored.

This is a Phase 1 MVP. Unknown semantics are preserved as
UnresolvedNode blocks (ADR-4) for the user to fix manually.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Extraction patterns
# ---------------------------------------------------------------------------

# HCP range: "12-14 HCP", "16-18", "22+"
HCP_RANGE_RE = re.compile(r'\b(\d+)\s*[-–]\s*(\d+)\s*(?:hcp)?', re.IGNORECASE)
HCP_MIN_RE = re.compile(r'\b(\d+)\+\s*(?:hcp\b)?', re.IGNORECASE)

# Suit length: "5+ hearts", "4+h", "5!h", "6+ clubs"
SUIT_WORD_RE = re.compile(
    r'\b(\d+)\+?\s*(?:[!]?\s*)?(clubs?|diamonds?|hearts?|spades?)',
    re.IGNORECASE,
)
SUIT_CHAR_RE = re.compile(
    r'\b(\d+)\+?\s*[!]?\s*([cdhs])\b',
    re.IGNORECASE,
)
SUIT_SUIT_RE = re.compile(
    r'\b(\d+)\+?\s*(?:[!]?)([♣♦♥♠])',
)

SUIT_WORD_MAP: dict[str, str] = {
    'club': 'clubs', 'clubs': 'clubs',
    'diamond': 'diamonds', 'diamonds': 'diamonds',
    'heart': 'hearts', 'hearts': 'hearts',
    'spade': 'spades', 'spades': 'spades',
}
SUIT_CHAR_MAP: dict[str, str] = {
    'c': 'clubs', '♣': 'clubs',
    'd': 'diamonds', '♦': 'diamonds',
    'h': 'hearts', '♥': 'hearts',
    's': 'spades', '♠': 'spades',
}

# Forcing keywords (checked after lowercasing)
FORCING_MAP: dict[str, str] = {
    'gf': 'game',
    'game force': 'game',
    'game forcing': 'game',
    'game-forcing': 'game',
    'game-force': 'game',
    'inv': 'invitational',
    'invitational': 'invitational',
    'invit': 'invitational',
    'nf': 'none',
    'non-forcing': 'none',
    'nonforcing': 'none',
    'n/f': 'none',
    'sign-off': 'signoff',
    'signoff': 'signoff',
    'to play': 'signoff',
    'pass or correct': 'signoff',
    'f1': 'one_round',
    'one-round force': 'one_round',
    '1rf': 'one_round',
    'forcing': 'one_round',
}

SHAPE_MAP: dict[str, str | None] = {
    'bal': 'balanced',
    'balanced': 'balanced',
    'balance': 'balanced',
    'semi-bal': 'semi_balanced',
    'semi bal': 'semi_balanced',
    'semibal': 'semi_balanced',
}

ARTIFICIAL_KEYWORDS = frozenset({
    'art', 'artificial', 'relay', 'puppet',
    'transfer', 'asking', 'waiting',
})
ALERT_KEYWORDS = frozenset({'alert', 'alertable'})
PREEMPTIVE_KEYWORDS = frozenset({'preemptive', 'preempt', 'wk', 'weak two'})


# ---------------------------------------------------------------------------
# BML tree dataclass
# ---------------------------------------------------------------------------

@dataclass
class BMLNode:
    """A single node parsed from a BML file."""

    bid: str
    description: str
    depth: int
    children: list[BMLNode] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BML file parser
# ---------------------------------------------------------------------------

# A bid token starts a line: e.g. 1C, 1NT, 2H, 3D, P, X, XX, PASS, etc.
BID_LINE_RE = re.compile(
    r'^( *)'                        # leading spaces → depth
    r'(\d[CcDdHhSs]|\d[Nn][Tt]|[Pp][Aa]?[Ss]?[Ss]?'
    r'|[Xx][Xx]?|PASS|DBLE|RDBL|[Pp]|[Xx])'  # bid token
    r'[ \t]+(.*)',                  # description
)


def _detect_indent(lines: list[str]) -> int:
    """Detect the indent unit (spaces per level) from the first indented line."""
    for line in lines:
        stripped = line.rstrip('\n')
        if not stripped.strip() or stripped.strip().startswith('#'):
            continue
        leading = len(stripped) - len(stripped.lstrip(' '))
        if leading > 0:
            return leading
    return 2  # default


def parse_bml_text(text: str) -> list[BMLNode]:
    """Parse BML text into a flat list of BMLNodes with depth information."""
    lines = text.splitlines()
    indent_unit = _detect_indent(lines)
    nodes: list[BMLNode] = []

    for line in lines:
        if not line.strip() or line.strip().startswith('#'):
            continue
        m = BID_LINE_RE.match(line)
        if not m:
            continue
        spaces, bid, desc = m.group(1), m.group(2).upper(), m.group(3).strip()
        depth = len(spaces) // max(indent_unit, 1)
        nodes.append(BMLNode(bid=bid, description=desc, depth=depth))

    return _build_tree(nodes)


def _build_tree(flat: list[BMLNode]) -> list[BMLNode]:
    """Convert flat depth-annotated list to nested tree (roots only)."""
    roots: list[BMLNode] = []
    stack: list[BMLNode] = []

    for node in flat:
        # Pop stack until we find the parent (depth == node.depth - 1)
        while stack and stack[-1].depth >= node.depth:
            stack.pop()

        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)

        stack.append(node)

    return roots


# ---------------------------------------------------------------------------
# Semantic extractor
# ---------------------------------------------------------------------------

def extract_semantics(description: str) -> dict[str, Any]:
    """Extract structured semantics from a free-text BML description.

    Returns a dict with possible keys:
        hand, forcing, artificial, alertable, preemptive, description
    Also sets '_resolved': bool and '_reason': str for import tracking.
    """
    result: dict[str, Any] = {}
    hand: dict[str, Any] = {}
    desc_lower = description.lower()

    # --- HCP ---
    hcp_range = HCP_RANGE_RE.search(description)
    if hcp_range:
        hand['hcp'] = {'min': int(hcp_range.group(1)), 'max': int(hcp_range.group(2))}
    else:
        hcp_min = HCP_MIN_RE.search(description)
        if hcp_min:
            hand['hcp'] = {'min': int(hcp_min.group(1))}

    # --- Suit lengths (word form: "5+ hearts") ---
    for m in SUIT_WORD_RE.finditer(description):
        length = int(m.group(1))
        suit = SUIT_WORD_MAP.get(m.group(2).lower())
        if suit and suit not in hand:
            hand[suit] = {'min': length}

    # --- Suit lengths (char form: "5+h", "4d") ---
    for m in SUIT_CHAR_RE.finditer(description):
        length = int(m.group(1))
        suit = SUIT_CHAR_MAP.get(m.group(2).lower())
        if suit and suit not in hand:
            hand[suit] = {'min': length}

    # --- Suit lengths (Unicode suit symbols) ---
    for m in SUIT_SUIT_RE.finditer(description):
        length = int(m.group(1))
        suit = SUIT_CHAR_MAP.get(m.group(2))
        if suit and suit not in hand:
            hand[suit] = {'min': length}

    # --- Shape (check longer keywords first to avoid "bal" matching "semi-bal") ---
    for keyword, ref in sorted(SHAPE_MAP.items(), key=lambda kv: -len(kv[0])):
        if keyword in desc_lower:
            if ref:
                hand['shape'] = {'ref': ref}
            break

    # --- Forcing ---
    for keyword, level in FORCING_MAP.items():
        if keyword in desc_lower:
            result['forcing'] = level
            break

    # --- Artificial ---
    for kw in ARTIFICIAL_KEYWORDS:
        if kw in desc_lower:
            result['artificial'] = True
            break

    # --- Alertable ---
    for kw in ALERT_KEYWORDS:
        if kw in desc_lower:
            result['alertable'] = True
            break
    if result.get('artificial') and 'alertable' not in result:
        result['alertable'] = True  # artificial bids default to alertable

    # --- Preemptive ---
    for kw in PREEMPTIVE_KEYWORDS:
        if kw in desc_lower:
            result['preemptive'] = True
            break

    # --- Resolve status ---
    resolved = bool(hand)
    result['_resolved'] = resolved
    if not resolved:
        result['_reason'] = 'No hand constraints could be extracted from description'
    else:
        result['_reason'] = ''

    if hand:
        result['hand'] = hand

    result['description'] = description
    return result


# ---------------------------------------------------------------------------
# BML tree → BBDSL dict converter
# ---------------------------------------------------------------------------

def _bml_node_to_bid_dict(node: BMLNode) -> dict[str, Any]:
    """Convert a single BMLNode to a BBDSL BidNode dict."""
    semantics = extract_semantics(node.description)
    resolved = semantics.pop('_resolved')
    reason = semantics.pop('_reason')
    orig_desc = semantics.pop('description')

    if not resolved:
        # ADR-4: UnresolvedNode
        return {
            'bid': node.bid,
            'is_unresolved': True,
            'bml_original': orig_desc,
            'reason': reason,
        }

    bid_dict: dict[str, Any] = {'bid': node.bid}
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

    # Recurse into children
    if node.children:
        bid_dict['responses'] = [_bml_node_to_bid_dict(c) for c in node.children]

    return bid_dict


def bml_nodes_to_document_dict(
    roots: list[BMLNode],
    system_name: str = 'Imported from BML',
) -> dict[str, Any]:
    """Convert a BML tree to a BBDSL document dict."""
    openings = [_bml_node_to_bid_dict(root) for root in roots]
    return {
        'bbdsl': '0.3',
        'system': {
            'name': {'en': system_name},
        },
        'openings': openings,
    }


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

def parse_bml_file(path: Path) -> list[BMLNode]:
    """Parse a BML file and return the root BMLNode list."""
    text = path.read_text(encoding='utf-8')
    return parse_bml_text(text)


def import_bml(
    path: Path,
    system_name: str | None = None,
    output_path: Path | None = None,
) -> tuple[dict[str, Any], int]:
    """Import a BML file to a BBDSL document dict.

    Returns:
        (doc_dict, n_unresolved) where n_unresolved is the number of
        UnresolvedNode blocks (ADR-4) that need manual fixing.
    """
    from ruamel.yaml import YAML

    roots = parse_bml_file(path)
    name = system_name or path.stem.replace('_', ' ').replace('-', ' ').title()
    doc_dict = bml_nodes_to_document_dict(roots, name)
    n_unresolved = _count_unresolved(doc_dict.get('openings', []))

    if output_path:
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.allow_unicode = True
        yaml.width = 120
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            if n_unresolved:
                f.write(
                    f'# BBDSL import from BML: {path.name}\n'
                    f'# WARNING: {n_unresolved} unresolved node(s) need manual fixing.\n'
                    f'# Search for "is_unresolved: true" and replace with proper hand constraints.\n\n'
                )
            yaml.dump(doc_dict, f)

    return doc_dict, n_unresolved
