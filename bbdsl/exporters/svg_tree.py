"""BBDSL → SVG bidding-tree exporter.

Produces a self-contained SVG file (no external dependencies) showing
the bidding system as a top-down tree diagram.

Node colour coding:
  - Opener nodes  : blue  (#dbeafe fill, #93c5fd stroke)
  - Responder nodes: green (#dcfce7 fill, #86efac stroke)

Usage::

    from bbdsl.exporters.svg_tree import export_svg
    svg = export_svg(doc, max_depth=2)
    Path("tree.svg").write_text(svg)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bbdsl.models.system import BBDSLDocument


# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------

def _t(value: Any, locale: str) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get(locale) or value.get("en") or next(iter(value.values()), "")
    return str(value)


# ---------------------------------------------------------------------------
# Short description builder
# ---------------------------------------------------------------------------

_SUIT_SYM = {"spades": "♠", "hearts": "♥", "diamonds": "♦", "clubs": "♣"}
_SUIT_EN  = {"spades": "S", "hearts": "H", "diamonds": "D", "clubs": "C"}
_MAX_DESC = 18  # chars — keep node labels compact


def _short_desc(node: Any, locale: str, suit_symbols: bool) -> str:
    """Return a compact ≤18-char description for a bid node."""
    meaning = getattr(node, "meaning", None)
    if meaning is None:
        ref = getattr(node, "ref", None)
        return f"→{ref.split('/')[-1][:14]}" if ref else ""

    desc = _t(getattr(meaning, "description", None), locale)
    if desc:
        return desc[:_MAX_DESC]

    # Fallback: HCP range
    hand = getattr(meaning, "hand", None)
    if hand and hand.hcp:
        h = hand.hcp
        if h.min is not None and h.max is not None:
            return f"{h.min}-{h.max} HCP"
        elif h.min is not None:
            return f"{h.min}+ HCP"
        elif h.max is not None:
            return f"≤{h.max} HCP"

    # Suit lengths
    suit_labels = _SUIT_SYM if suit_symbols else _SUIT_EN
    if hand:
        for suit in ("spades", "hearts", "diamonds", "clubs"):
            r = getattr(hand, suit, None)
            if r and r.min is not None:
                label = suit_labels[suit]
                return f"{r.min}+ {label}"

    if meaning.artificial:
        return "artificial"
    if meaning.preemptive:
        return "preemptive"
    return ""


# ---------------------------------------------------------------------------
# Tree data structure
# ---------------------------------------------------------------------------

@dataclass
class _SvgNode:
    bid: str
    desc: str
    depth: int
    by: str                          # "opener" | "responder"
    children: list["_SvgNode"] = field(default_factory=list)
    # Set by _calc_layout:
    x: float = 0.0
    y: float = 0.0
    subtree_width: float = 0.0


def _build_tree(
    bid_nodes: list[Any],
    locale: str,
    suit_symbols: bool,
    max_depth: int,
    depth: int = 0,
) -> list[_SvgNode]:
    """Recursively build _SvgNode tree from BidNode list."""
    result: list[_SvgNode] = []
    for node in (bid_nodes or []):
        bid = getattr(node, "bid", None) or ""
        if not bid:
            continue
        by_raw = getattr(node, "by", None)
        by = by_raw or ("opener" if depth == 0 else "responder")
        desc = _short_desc(node, locale, suit_symbols)

        children: list[_SvgNode] = []
        if depth < max_depth:
            responses = getattr(node, "responses", None) or []
            conts = getattr(node, "continuations", None) or []
            children = _build_tree(responses + conts, locale, suit_symbols,
                                   max_depth, depth + 1)

        result.append(_SvgNode(bid=bid, desc=desc, depth=depth,
                                by=by, children=children))
    return result


# ---------------------------------------------------------------------------
# Layout engine
# ---------------------------------------------------------------------------

def _calc_layout(
    nodes: list[_SvgNode],
    node_width: float,
    h_gap: float,
    node_height: float,
    v_gap: float,
    x_offset: float = 0.0,
    depth: int = 0,
) -> float:
    """Assign x, y, subtree_width to all nodes.  Returns total width consumed."""
    total = 0.0
    for node in nodes:
        node.y = depth * (node_height + v_gap)

        if node.children:
            child_w = _calc_layout(
                node.children, node_width, h_gap, node_height, v_gap,
                x_offset + total, depth + 1,
            )
            node.subtree_width = max(node_width, child_w)
        else:
            node.subtree_width = node_width

        # Centre this node over its subtree
        node.x = x_offset + total + (node.subtree_width - node_width) / 2
        total += node.subtree_width + h_gap

    return max(0.0, total - h_gap)  # strip trailing gap


# ---------------------------------------------------------------------------
# SVG element builders
# ---------------------------------------------------------------------------

_OPENER_FILL   = "#dbeafe"
_OPENER_STROKE = "#93c5fd"
_OPENER_TEXT   = "#1d4ed8"
_RESP_FILL     = "#dcfce7"
_RESP_STROKE   = "#86efac"
_RESP_TEXT     = "#15803d"
_LINE_COLOR    = "#d1d5db"
_DESC_COLOR    = "#6b7280"


def _render_node(
    node: _SvgNode,
    node_width: float,
    node_height: float,
) -> list[str]:
    """Return SVG lines for a single node (rect + bid text + desc text)."""
    fill   = _OPENER_FILL   if node.by == "opener" else _RESP_FILL
    stroke = _OPENER_STROKE if node.by == "opener" else _RESP_STROKE
    tcolor = _OPENER_TEXT   if node.by == "opener" else _RESP_TEXT

    x, y = node.x, node.y
    cx = x + node_width / 2
    lines: list[str] = []

    lines.append(
        f'  <rect x="{x:.1f}" y="{y:.1f}" width="{node_width}" height="{node_height}"'
        f' rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
    )
    # Bid label (bold, centered, upper half)
    bid_y = y + node_height * 0.42
    lines.append(
        f'  <text x="{cx:.1f}" y="{bid_y:.1f}" text-anchor="middle"'
        f' font-family="monospace" font-size="13" font-weight="bold"'
        f' fill="{tcolor}">{_escape(node.bid)}</text>'
    )
    # Description (small, lower half)
    if node.desc:
        desc_y = y + node_height * 0.78
        lines.append(
            f'  <text x="{cx:.1f}" y="{desc_y:.1f}" text-anchor="middle"'
            f' font-family="sans-serif" font-size="9" fill="{_DESC_COLOR}"'
            f'>{_escape(node.desc[:_MAX_DESC])}</text>'
        )
    return lines


def _render_edge(
    parent: _SvgNode,
    child: _SvgNode,
    node_width: float,
    node_height: float,
) -> str:
    """Return an SVG path element for the edge from parent to child."""
    px = parent.x + node_width / 2
    py = parent.y + node_height
    cx_ = child.x + node_width / 2
    cy = child.y
    mid_y = (py + cy) / 2
    return (
        f'  <path d="M{px:.1f},{py:.1f} C{px:.1f},{mid_y:.1f} '
        f'{cx_:.1f},{mid_y:.1f} {cx_:.1f},{cy:.1f}"'
        f' fill="none" stroke="{_LINE_COLOR}" stroke-width="1.2"/>'
    )


def _escape(text: str) -> str:
    """Minimal XML character escaping for SVG text content."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# DFS collectors
# ---------------------------------------------------------------------------

def _collect_all(nodes: list[_SvgNode]) -> list[_SvgNode]:
    """Flatten the tree into a pre-order list."""
    result: list[_SvgNode] = []
    for n in nodes:
        result.append(n)
        result.extend(_collect_all(n.children))
    return result


def _collect_edges(nodes: list[_SvgNode]) -> list[tuple[_SvgNode, _SvgNode]]:
    """Collect all (parent, child) pairs in the tree."""
    edges: list[tuple[_SvgNode, _SvgNode]] = []
    for n in nodes:
        for child in n.children:
            edges.append((n, child))
            edges.extend(_collect_edges([child]))
    return edges


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_svg(
    doc: BBDSLDocument,
    output_path: Path | None = None,
    locale: str = "en",
    suit_symbols: bool = False,
    max_depth: int = 2,
    node_width: int = 120,
    node_height: int = 40,
    h_gap: int = 16,
    v_gap: int = 60,
) -> str:
    """Export a BBDSLDocument as an SVG bidding-tree diagram.

    Args:
        doc: The BBDSL document.
        output_path: If given, write SVG to this file.
        locale: 'en' or 'zh-TW'.
        suit_symbols: Use ♠♥♦♣ in node descriptions.
        max_depth: Maximum tree depth (0 = openings only, 1 = +responses, …).
        node_width: Width of each node rectangle in pixels.
        node_height: Height of each node rectangle in pixels.
        h_gap: Horizontal gap between sibling subtrees.
        v_gap: Vertical gap between tree levels.

    Returns:
        SVG string.
    """
    # Build tree
    roots = _build_tree(
        doc.openings or [], locale, suit_symbols, max_depth, depth=0
    )
    if not roots:
        svg = '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="60"><text x="10" y="30">No openings</text></svg>'
        if output_path:
            Path(output_path).write_text(svg, encoding="utf-8")
        return svg

    # Layout
    padding = 20
    total_w = _calc_layout(
        roots, float(node_width), float(h_gap),
        float(node_height), float(v_gap), x_offset=float(padding),
    )
    all_nodes = _collect_all(roots)
    max_depth_found = max(n.depth for n in all_nodes) if all_nodes else 0
    total_h = (max_depth_found + 1) * (node_height + v_gap) - v_gap + 2 * padding

    svg_w = total_w + 2 * padding
    svg_h = total_h

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="0 0 {svg_w:.0f} {svg_h:.0f}"'
        f' width="{svg_w:.0f}" height="{svg_h:.0f}">'
    )
    lines.append(f'  <!-- BBDSL SVG Bidding Tree — max_depth={max_depth} -->')

    # Edges first (drawn below nodes)
    edges = _collect_edges(roots)
    for parent, child in edges:
        lines.append(_render_edge(parent, child, node_width, node_height))

    # Nodes
    for node in all_nodes:
        lines.extend(_render_node(node, node_width, node_height))

    lines.append("</svg>")

    svg = "\n".join(lines)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(svg, encoding="utf-8")

    return svg
