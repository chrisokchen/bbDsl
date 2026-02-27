"""BBDSL → BML (Bridge Markup Language) exporter.

Produces an indented text format:
    <bid>  <description>
      <bid>  <description>   (response, 2-space indent)
        <bid>  <description> (continuation, 4-space indent)

- The same format parseable by bbdsl.importers.bml_importer
- Supports locale selection (en / zh-TW)
- Optional suit symbols (♠♥♦♣) in descriptions
- Convention refs are noted inline as comments
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bbdsl.models.system import BBDSLDocument

# ---------------------------------------------------------------------------
# Suit symbol tables
# ---------------------------------------------------------------------------

_SUIT_SYMBOLS = {
    'spades': '♠', 'hearts': '♥', 'diamonds': '♦', 'clubs': '♣',
}
_SUIT_LABELS_EN = {
    'spades': 'spades', 'hearts': 'hearts', 'diamonds': 'diamonds', 'clubs': 'clubs',
}
_SUIT_LABELS_ZH = {
    'spades': '黑桃', 'hearts': '紅心', 'diamonds': '方塊', 'clubs': '梅花',
}

_FORCING_BML_EN = {
    'game': 'GF', 'invitational': 'INV', 'one_round': 'f1',
    'signoff': 'S/O', 'none': 'NF',
}
_FORCING_BML_ZH = {
    'game': '成局強迫', 'invitational': '邀請', 'one_round': '一輪強迫',
    'signoff': '到叫', 'none': '非強迫',
}

# ---------------------------------------------------------------------------
# Description builder
# ---------------------------------------------------------------------------

def _get_text(value: Any, locale: str) -> str:
    """Extract localised text from an I18nString or plain string."""
    if value is None:
        return ''
    if isinstance(value, dict):
        return value.get(locale) or value.get('en') or next(iter(value.values()), '')
    return str(value)


def _hand_to_bml(hand: Any, locale: str, suit_symbols: bool) -> list[str]:
    """Convert a HandConstraint to BML-style description fragments."""
    parts: list[str] = []
    if hand is None:
        return parts

    if suit_symbols:
        suit_labels = _SUIT_SYMBOLS
    elif locale == 'zh-TW':
        suit_labels = _SUIT_LABELS_ZH
    else:
        suit_labels = _SUIT_LABELS_EN

    # HCP
    if hand.hcp:
        hcp = hand.hcp
        if hcp.min is not None and hcp.max is not None:
            parts.append(f'{hcp.min}-{hcp.max} HCP')
        elif hcp.min is not None:
            parts.append(f'{hcp.min}+ HCP')
        elif hcp.max is not None:
            parts.append(f'≤{hcp.max} HCP')

    # Suit lengths
    for suit in ('spades', 'hearts', 'diamonds', 'clubs'):
        r = getattr(hand, suit, None)
        if r is None:
            continue
        label = suit_labels[suit]
        if r.min is not None and r.max is not None:
            parts.append(f'{r.min}-{r.max}{("+" + label) if suit_symbols else (" " + label)}')
        elif r.min is not None:
            if suit_symbols:
                parts.append(f'{r.min}+{label}')
            else:
                parts.append(f'{r.min}+ {label}')
        elif r.max is not None:
            if suit_symbols:
                parts.append(f'≤{r.max}{label}')
            else:
                parts.append(f'≤{r.max} {label}')

    # Shape
    if hand.shape and isinstance(hand.shape, dict) and 'ref' in hand.shape:
        ref = hand.shape['ref']
        if locale == 'zh-TW':
            zh_map = {'balanced': '平均', 'semi_balanced': '半平均', 'semi-balanced': '半平均'}
            parts.append(zh_map.get(ref, ref))
        else:
            parts.append(ref.replace('_', '-'))
    elif isinstance(hand.shape, str) and hand.shape not in ('any', ''):
        parts.append(hand.shape)

    return parts


def _build_bml_description(
    node: Any,
    locale: str,
    suit_symbols: bool,
) -> str:
    """Build the BML description line for a bid node."""
    meaning = getattr(node, 'meaning', None)
    if meaning is None:
        # Node has a convention ref but no meaning
        ref = getattr(node, 'ref', None)
        if ref:
            return f'(convention: {ref})'
        return ''

    parts: list[str] = []

    # 1. User description
    desc = _get_text(meaning.description, locale)
    if desc:
        parts.append(desc)

    # 2. Hand constraints (when no description provided)
    if not parts and meaning.hand:
        hand_parts = _hand_to_bml(meaning.hand, locale, suit_symbols)
        parts.extend(hand_parts)

    # 3. Flags
    if meaning.artificial:
        parts.append('art')
    if meaning.alertable and not meaning.artificial:
        # Only add explicit alert if not already implied by artificial
        parts.append('alert')
    if meaning.forcing:
        fval = meaning.forcing.value if hasattr(meaning.forcing, 'value') else str(meaning.forcing)
        flabel = (_FORCING_BML_ZH if locale == 'zh-TW' else _FORCING_BML_EN).get(fval, fval)
        parts.append(flabel)
    if meaning.preemptive:
        parts.append('preemptive' if locale != 'zh-TW' else '先制')
    if meaning.transfer_to:
        parts.append(f'transfer to {meaning.transfer_to}')

    # 4. Convention ref note
    ref = getattr(node, 'ref', None)
    if ref:
        parts.append(f'[→{ref}]')

    return ', '.join(parts)


# ---------------------------------------------------------------------------
# Tree renderer
# ---------------------------------------------------------------------------

_INDENT = '  '  # 2 spaces per level
_BID_WIDTH = 4   # minimum column width for bid (e.g. "1NT " = 4 chars)


def _render_node(
    node: Any,
    depth: int,
    lines: list[str],
    locale: str,
    suit_symbols: bool,
    include_conventions: bool,
) -> None:
    """Render a single BidNode (and its children) into lines."""
    bid = getattr(node, 'bid', None) or ''
    if not bid:
        return

    description = _build_bml_description(node, locale, suit_symbols)
    prefix = _INDENT * depth
    # Align: bid padded to at least _BID_WIDTH, then 2 spaces, then description
    bid_col = bid.ljust(_BID_WIDTH)
    if description:
        lines.append(f'{prefix}{bid_col}  {description}')
    else:
        lines.append(f'{prefix}{bid}')

    # Recurse: responses
    responses = getattr(node, 'responses', None) or []
    for child in responses:
        _render_node(child, depth + 1, lines, locale, suit_symbols, include_conventions)

    # Recurse: continuations
    continuations = getattr(node, 'continuations', None) or []
    for child in continuations:
        _render_node(child, depth + 1, lines, locale, suit_symbols, include_conventions)


# ---------------------------------------------------------------------------
# Convention rendering
# ---------------------------------------------------------------------------

def _render_convention_section(
    name: str,
    conv: Any,
    locale: str,
    suit_symbols: bool,
) -> list[str]:
    """Render a convention definition as a BML comment block."""
    lines: list[str] = []
    lines.append(f'# Convention: {name} ({conv.id})')
    desc = _get_text(getattr(conv, 'description', None), locale)
    if desc:
        lines.append(f'#   {desc}')
    # Render convention bids/responses if available
    responses = getattr(conv, 'responses', None) or []
    for r in responses:
        bid = getattr(r, 'bid', None) or ''
        meaning = getattr(r, 'meaning', None)
        if bid and meaning:
            rdesc = _get_text(getattr(meaning, 'description', None), locale)
            if rdesc:
                lines.append(f'#   {bid}  {rdesc}')
    return lines


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_bml(
    doc: BBDSLDocument,
    output_path: Path | None = None,
    locale: str = 'en',
    suit_symbols: bool = False,
    include_comments: bool = True,
    include_conventions: bool = True,
) -> str:
    """Export a BBDSLDocument to BML indented format.

    Args:
        doc: The BBDSL document.
        output_path: If given, write to this file.
        locale: 'en' or 'zh-TW'.
        suit_symbols: Use ♠♥♦♣ in suit descriptions.
        include_comments: Add system header comment.
        include_conventions: Include convention definitions as comment blocks.

    Returns:
        The BML text as a string.
    """
    lines: list[str] = []

    # Header
    if include_comments:
        name = doc.system.name
        system_name = (
            name.get(locale) or name.get('en') or next(iter(name.values()), 'System')
            if isinstance(name, dict) else str(name)
        )
        lines.append(f'# BML export from BBDSL')
        lines.append(f'# System: {system_name}')
        lines.append(f'# Locale: {locale}')
        lines.append('')

    # Convention definitions (as comments)
    if include_conventions and doc.conventions:
        for name, conv in doc.conventions.items():
            lines.extend(_render_convention_section(name, conv, locale, suit_symbols))
        if doc.conventions:
            lines.append('')

    # Opening bids
    for opening in (doc.openings or []):
        _render_node(opening, 0, lines, locale, suit_symbols, include_conventions)

    text = '\n'.join(lines) + '\n'

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding='utf-8')

    return text
