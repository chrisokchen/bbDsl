"""BBDSL → BBOalert exporter.

Produces a CSV-format BBOalert file where each row is:
    context, call, explanation

- context: dash-separated bid path leading to this bid (empty for openings)
- call:    the bid itself (e.g. "1C", "1NT", "2D")
- explanation: natural-language description with hand constraints + flags

Reference: BBOalert browser extension format (v2.x)
"""

from __future__ import annotations

import csv
import io
from typing import Any

from bbdsl.models.system import BBDSLDocument

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Suit labels for explanation text
_SUIT_LABELS_EN = {
    'clubs': 'clubs',
    'diamonds': 'diamonds',
    'hearts': 'hearts',
    'spades': 'spades',
}
_SUIT_LABELS_ZH = {
    'clubs': '梅花',
    'diamonds': '方塊',
    'hearts': '紅心',
    'spades': '黑桃',
}

_FORCING_LABELS_EN = {
    'game': 'GF',
    'invitational': 'INV',
    'one_round': 'F1',
    'signoff': 'S/O',
    'none': 'NF',
}
_FORCING_LABELS_ZH = {
    'game': '成局強迫',
    'invitational': '邀請',
    'one_round': '一輪強迫',
    'signoff': '到叫',
    'none': '非強迫',
}

# ---------------------------------------------------------------------------
# Explanation builder
# ---------------------------------------------------------------------------

def _hand_summary(hand: Any, locale: str) -> list[str]:
    """Convert a HandConstraint to a list of description fragments."""
    parts: list[str] = []
    if hand is None:
        return parts

    suit_labels = _SUIT_LABELS_ZH if locale == 'zh-TW' else _SUIT_LABELS_EN

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
    for suit in ('clubs', 'diamonds', 'hearts', 'spades'):
        r = getattr(hand, suit, None)
        if r is None:
            continue
        label = suit_labels[suit]
        if r.min is not None and r.max is not None:
            parts.append(f'{r.min}-{r.max} {label}')
        elif r.min is not None:
            parts.append(f'{r.min}+ {label}')
        elif r.max is not None:
            parts.append(f'≤{r.max} {label}')

    # Shape ref
    if hand.shape and isinstance(hand.shape, dict) and 'ref' in hand.shape:
        ref = hand.shape['ref'].replace('_', '-')
        if locale == 'zh-TW':
            zh_map = {'balanced': '平均', 'semi-balanced': '半平均',
                      'semi_balanced': '半平均'}
            parts.append(zh_map.get(ref, ref))
        else:
            parts.append(ref)
    elif isinstance(hand.shape, str) and hand.shape != 'any':
        parts.append(hand.shape)

    return parts


def build_explanation(meaning: Any, locale: str = 'en') -> str:
    """Convert a BidMeaning to a BBOalert explanation string."""
    if meaning is None:
        return ''

    fragments: list[str] = []

    # 1. User-provided description
    desc = meaning.description
    if desc:
        if isinstance(desc, dict):
            text = desc.get(locale) or desc.get('en') or next(iter(desc.values()), '')
        else:
            text = str(desc)
        if text:
            fragments.append(text)

    # 2. Hand constraints (only when no description was provided)
    if meaning.hand and not fragments:
        hand_parts = _hand_summary(meaning.hand, locale)
        fragments.extend(hand_parts)

    # 3. Flags
    flags: list[str] = []
    if meaning.artificial:
        flags.append('Alert')
    if meaning.forcing:
        fval = meaning.forcing.value if hasattr(meaning.forcing, 'value') else str(meaning.forcing)
        flabel = (_FORCING_LABELS_ZH if locale == 'zh-TW' else _FORCING_LABELS_EN).get(fval, fval)
        flags.append(flabel)
    if meaning.preemptive:
        flags.append('Preemptive' if locale != 'zh-TW' else '先制')
    if meaning.transfer_to:
        flags.append(f'→{meaning.transfer_to}')

    if flags:
        fragments.append('[' + ', '.join(flags) + ']')

    return '; '.join(fragments)


# ---------------------------------------------------------------------------
# Tree flattener
# ---------------------------------------------------------------------------

BBORow = tuple[str, str, str]  # (context, call, explanation)


def _flatten_node(
    node: Any,
    path: list[str],
    rows: list[BBORow],
    locale: str,
    context_overrides_prefix: list[str] | None = None,
) -> None:
    """Recursively walk a BidNode, emitting one row per bid."""
    bid = getattr(node, 'bid', None) or ''
    if not bid:
        return

    context = '-'.join(path)
    explanation = build_explanation(getattr(node, 'meaning', None), locale)

    # Emit row for this bid
    rows.append((context, bid, explanation))

    current_path = path + [bid]

    # Recurse into responses
    responses = getattr(node, 'responses', None) or []
    for child in responses:
        _flatten_node(child, current_path, rows, locale)

    # Recurse into continuations
    continuations = getattr(node, 'continuations', None) or []
    for child in continuations:
        _flatten_node(child, current_path, rows, locale)


def flatten_document(doc: BBDSLDocument, locale: str = 'en') -> list[BBORow]:
    """Flatten entire BBDSL document into (context, call, explanation) rows."""
    rows: list[BBORow] = []

    for opening in (doc.openings or []):
        # Root openings have empty context
        _flatten_node(opening, [], rows, locale)

    return rows


# ---------------------------------------------------------------------------
# Formatter / writer
# ---------------------------------------------------------------------------

def _format_bboalert(
    rows: list[BBORow],
    system_name: str,
    locale: str,
    include_comments: bool = True,
) -> str:
    """Render rows as a BBOalert text file."""
    buf = io.StringIO()

    if include_comments:
        buf.write(f'# BBOalert rules generated by BBDSL\n')
        buf.write(f'# System: {system_name}\n')
        buf.write(f'# Locale: {locale}\n')
        buf.write(f'# Format: context,call,explanation\n')
        buf.write(f'#         (empty context = opening bid)\n')
        buf.write('#\n')

    writer = csv.writer(buf, lineterminator='\n')
    for context, call, explanation in rows:
        writer.writerow([context, call, explanation])

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_bboalert(
    doc: BBDSLDocument,
    output_path=None,
    locale: str = 'en',
    include_comments: bool = True,
) -> list[BBORow]:
    """Export a BBDSLDocument to BBOalert format.

    Args:
        doc: The BBDSL document to export.
        output_path: If given, write the result to this file.
        locale: Language code for descriptions ('en' or 'zh-TW').
        include_comments: Include header comments in the output file.

    Returns:
        List of (context, call, explanation) tuples.
    """
    rows = flatten_document(doc, locale)

    name = doc.system.name
    if isinstance(name, dict):
        system_name = name.get(locale) or name.get('en') or next(iter(name.values()), 'System')
    else:
        system_name = str(name)

    if output_path is not None:
        from pathlib import Path
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = _format_bboalert(rows, system_name, locale, include_comments)
        output_path.write_text(content, encoding='utf-8')

    return rows
