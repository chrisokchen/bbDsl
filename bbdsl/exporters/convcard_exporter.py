"""BBDSL → Convention Card HTML exporter.

Produces a single self-contained, printable HTML file styled as a
WBF or ACBL convention card.  Use File → Print in your browser to
save as PDF.

Sections produced:
  - Opening bids table (Bid | HCP | Description | Flags)
  - 1NT section (HCP range, Stayman / Jacoby Transfer indicators)
  - Strong 2C section (if an artificial 2C opening is present)
  - Weak Two section (if preemptive 2x openings are present)
  - Conventions list (ID, name, description)
  - Completeness status bar
  - ACBL-specific section headings when style="acbl"
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import BaseLoader, Environment

from bbdsl.models.system import BBDSLDocument


# ---------------------------------------------------------------------------
# i18n helpers (same pattern as html_exporter / bml_exporter)
# ---------------------------------------------------------------------------

def _t(value: Any, locale: str) -> str:
    """Extract localised string from I18nString (str | dict | None)."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get(locale) or value.get("en") or next(iter(value.values()), "")
    return str(value)


# ---------------------------------------------------------------------------
# Hand constraint → concise summary
# ---------------------------------------------------------------------------

_SUIT_EN = {"spades": "spades", "hearts": "hearts",
            "diamonds": "diamonds", "clubs": "clubs"}
_SUIT_ZH = {"spades": "黑桃", "hearts": "紅心",
            "diamonds": "方塊", "clubs": "梅花"}
_SUIT_SYM = {"spades": "♠", "hearts": "♥", "diamonds": "♦", "clubs": "♣"}
_SHAPE_EN = {"balanced": "balanced", "semi_balanced": "semi-balanced",
             "semi-balanced": "semi-balanced"}
_SHAPE_ZH = {"balanced": "平均", "semi_balanced": "半平均",
             "semi-balanced": "半平均"}
_FORCING_EN = {"game": "GF", "invitational": "INV", "one_round": "F1",
               "signoff": "S/O", "none": "NF"}
_FORCING_ZH = {"game": "成局強迫", "invitational": "邀請",
               "one_round": "一輪強迫", "signoff": "到叫", "none": "非強迫"}


def _hand_summary(hand: Any, locale: str) -> str:
    """Return a compact hand constraint summary, e.g. '15-17 HCP, balanced'."""
    if hand is None:
        return ""
    parts: list[str] = []

    if hand.hcp:
        h = hand.hcp
        if h.min is not None and h.max is not None:
            parts.append(f"{h.min}-{h.max} HCP")
        elif h.min is not None:
            parts.append(f"{h.min}+ HCP")
        elif h.max is not None:
            parts.append(f"≤{h.max} HCP")

    suit_labels = _SUIT_ZH if locale == "zh-TW" else _SUIT_EN
    for suit in ("spades", "hearts", "diamonds", "clubs"):
        r = getattr(hand, suit, None)
        if r is None:
            continue
        label = suit_labels[suit]
        if r.min is not None and r.max is not None:
            if r.min == r.max:
                parts.append(f"{r.min}={label}")
            else:
                parts.append(f"{r.min}-{r.max} {label}")
        elif r.min is not None:
            parts.append(f"{r.min}+ {label}")
        elif r.max is not None:
            parts.append(f"≤{r.max} {label}")

    if hand.shape and isinstance(hand.shape, dict) and "ref" in hand.shape:
        ref = hand.shape["ref"]
        lkp = _SHAPE_ZH if locale == "zh-TW" else _SHAPE_EN
        parts.append(lkp.get(ref, ref.replace("_", "-")))
    elif isinstance(hand.shape, str) and hand.shape not in ("any", ""):
        parts.append(hand.shape)

    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------

def _extract_opening_rows(doc: BBDSLDocument, locale: str) -> list[dict]:
    """Extract a row dict for each opening in doc.openings."""
    rows: list[dict] = []
    for node in (doc.openings or []):
        bid = getattr(node, "bid", None) or ""
        if not bid:
            continue
        meaning = getattr(node, "meaning", None)
        hand = getattr(meaning, "hand", None) if meaning else None

        hcp_str = ""
        if hand and hand.hcp:
            h = hand.hcp
            if h.min is not None and h.max is not None:
                hcp_str = f"{h.min}-{h.max}"
            elif h.min is not None:
                hcp_str = f"{h.min}+"
            elif h.max is not None:
                hcp_str = f"≤{h.max}"

        desc = ""
        if meaning:
            desc = _t(meaning.description, locale)
            if not desc:
                desc = _hand_summary(hand, locale)

        forcing = None
        if meaning and meaning.forcing:
            fval = meaning.forcing.value if hasattr(meaning.forcing, "value") else str(meaning.forcing)
            forcing = (_FORCING_ZH if locale == "zh-TW" else _FORCING_EN).get(fval, fval)

        rows.append({
            "bid": bid,
            "hcp": hcp_str,
            "description": desc,
            "artificial": bool(meaning and meaning.artificial),
            "alertable": bool(meaning and meaning.alertable),
            "preemptive": bool(meaning and meaning.preemptive),
            "forcing": forcing,
        })
    return rows


def _extract_nt_info(doc: BBDSLDocument, locale: str) -> dict | None:
    """Find the 1NT opening and return NT section data."""
    for node in (doc.openings or []):
        if getattr(node, "bid", None) != "1NT":
            continue
        meaning = getattr(node, "meaning", None)
        hand = getattr(meaning, "hand", None) if meaning else None

        hcp_range = ""
        if hand and hand.hcp:
            h = hand.hcp
            if h.min is not None and h.max is not None:
                hcp_range = f"{h.min}-{h.max}"
            elif h.min is not None:
                hcp_range = f"{h.min}+"

        # Detect Stayman / Jacoby from conventions_applied or responses with ref
        applied = getattr(node, "conventions_applied", None) or []
        applied_refs = {(a.get("ref") or "") for a in applied if isinstance(a, dict)}
        responses = getattr(node, "responses", None) or []
        resp_refs = {(r.get("ref") or "") for r in responses if isinstance(r, dict) and r.get("ref")}
        all_refs = applied_refs | resp_refs

        has_stayman = any("stayman" in r.lower() for r in all_refs)
        has_jacoby = any("jacoby" in r.lower() for r in all_refs)
        has_transfer = any("transfer" in r.lower() for r in all_refs)

        desc = ""
        if meaning:
            desc = _t(meaning.description, locale)
        return {
            "hcp_range": hcp_range,
            "description": desc,
            "has_stayman": has_stayman,
            "has_jacoby_transfer": has_jacoby or has_transfer,
        }
    return None


def _extract_strong_2c_info(doc: BBDSLDocument, locale: str) -> dict | None:
    """Find an artificial 2C opening and return its data."""
    for node in (doc.openings or []):
        if getattr(node, "bid", None) != "2C":
            continue
        meaning = getattr(node, "meaning", None)
        if not (meaning and meaning.artificial):
            continue
        hand = getattr(meaning, "hand", None)
        return {
            "hcp_summary": _hand_summary(hand, locale),
            "description": _t(meaning.description, locale),
        }
    return None


def _extract_weak_twos(doc: BBDSLDocument, locale: str) -> list[dict]:
    """Find preemptive 2-level openings."""
    result: list[dict] = []
    for node in (doc.openings or []):
        bid = getattr(node, "bid", None) or ""
        if not bid.startswith("2") or bid == "2C":
            continue
        meaning = getattr(node, "meaning", None)
        if not (meaning and meaning.preemptive):
            continue
        hand = getattr(meaning, "hand", None)
        result.append({
            "bid": bid,
            "hcp_summary": _hand_summary(hand, locale),
            "description": _t(meaning.description, locale),
        })
    return result


def _extract_conventions_list(doc: BBDSLDocument, locale: str) -> list[dict]:
    """Return a list of {id, name, description} for each convention."""
    convs: list[dict] = []
    for key, conv in (doc.conventions or {}).items():
        conv_id = getattr(conv, "id", key) or key
        name = _t(getattr(conv, "name", None), locale) or key
        desc = _t(getattr(conv, "description", None), locale)
        convs.append({"id": conv_id, "name": name, "description": desc})
    return convs


def _completeness_items(doc: BBDSLDocument, locale: str) -> list[dict]:
    comp = getattr(doc.system, "completeness", None)
    if comp is None:
        return []
    labels_en = {
        "openings": "Openings", "responses_to_1c": "Responses to 1C",
        "responses_to_1nt": "Responses to 1NT", "defensive": "Defensive",
        "competitive": "Competitive", "slam_bidding": "Slam Bidding",
    }
    labels_zh = {
        "openings": "開叫", "responses_to_1c": "1梅花回應",
        "responses_to_1nt": "1NT回應", "defensive": "防守競叫",
        "competitive": "競叫", "slam_bidding": "滿貫叫牌",
    }
    colors = {"complete": "bg-green-500", "partial": "bg-yellow-400",
              "draft": "bg-orange-400", "todo": "bg-gray-300"}
    labels = labels_zh if locale == "zh-TW" else labels_en
    items: list[dict] = []
    for field, label in labels.items():
        val = getattr(comp, field, None)
        if val is None:
            continue
        status = val.value if hasattr(val, "value") else str(val)
        items.append({"label": label, "status": status, "color": colors.get(status, "bg-gray-300")})
    return items


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

_CONVCARD_TEMPLATE = r"""<!DOCTYPE html>
<html lang="{{ locale }}">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{{ page_title }}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { font-family: 'Segoe UI', system-ui, sans-serif; }
    .flag-badge {
      display: inline-block;
      font-size: 0.65rem;
      font-weight: 600;
      padding: 1px 5px;
      border-radius: 3px;
      line-height: 1.4;
    }
    .bid-cell { font-family: monospace; font-weight: 700; font-size: 1rem; }
    .check { color: #16a34a; }
    .cross { color: #dc2626; }
    .section-head {
      font-size: 0.7rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #6b7280;
      border-bottom: 1px solid #e5e7eb;
      padding-bottom: 4px;
      margin-bottom: 8px;
    }
    @media print {
      .no-print { display: none !important; }
      body { margin: 0; padding: 0; }
      main { max-width: 100% !important; margin: 0 !important; padding: 8mm !important; }
      @page { size: A4 portrait; margin: 10mm; }
    }
  </style>
</head>
<body class="bg-gray-100 min-h-screen py-6">

<main class="max-w-4xl mx-auto bg-white shadow rounded-lg p-6">

  <!-- ══ Header ══ -->
  <header class="mb-6 border-b pb-4 flex items-start justify-between gap-4">
    <div>
      <h1 class="text-2xl font-bold text-gray-900">{{ system_name }}</h1>
      {% if system_version %}
      <span class="text-xs text-gray-500">v{{ system_version }}</span>
      {% endif %}
      {% if authors %}
      <p class="text-sm text-gray-500 mt-1">{{ authors }}</p>
      {% endif %}
    </div>
    <div class="flex-shrink-0 flex flex-col items-end gap-1">
      <span class="flag-badge {{ 'bg-blue-100 text-blue-800' if style == 'wbf' else 'bg-red-100 text-red-800' }}">
        {{ 'WBF Style' if style == 'wbf' else 'ACBL Style' }}
      </span>
      {% if completeness_items %}
      <div class="flex flex-wrap gap-1 justify-end mt-1">
        {% for item in completeness_items %}
        <span class="flag-badge {{ item.color }} text-white" title="{{ item.status }}">{{ item.label }}</span>
        {% endfor %}
      </div>
      {% endif %}
    </div>
  </header>

  <!-- ══ Opening Bids ══ -->
  <section class="mb-6">
    <div class="section-head">{{ 'Opening Bids' if locale == 'en' else '開叫系統' }}</div>
    <table class="w-full text-sm border-collapse">
      <thead>
        <tr class="bg-gray-50">
          <th class="border border-gray-200 px-3 py-1.5 text-left font-semibold text-gray-700 w-16">
            {{ 'Bid' if locale == 'en' else '叫品' }}
          </th>
          <th class="border border-gray-200 px-3 py-1.5 text-left font-semibold text-gray-700 w-24">
            {{ 'HCP' }}
          </th>
          <th class="border border-gray-200 px-3 py-1.5 text-left font-semibold text-gray-700">
            {{ 'Description' if locale == 'en' else '說明' }}
          </th>
          <th class="border border-gray-200 px-3 py-1.5 text-center font-semibold text-gray-700 w-28 no-print">
            {{ 'Flags' if locale == 'en' else '旗標' }}
          </th>
        </tr>
      </thead>
      <tbody>
        {% for row in opening_rows %}
        <tr class="hover:bg-gray-50">
          <td class="border border-gray-200 px-3 py-1 bid-cell text-blue-700">{{ row.bid }}</td>
          <td class="border border-gray-200 px-3 py-1 text-gray-600 font-mono text-xs">{{ row.hcp }}</td>
          <td class="border border-gray-200 px-3 py-1 text-gray-700">{{ row.description }}</td>
          <td class="border border-gray-200 px-3 py-1 text-center no-print">
            {% if row.artificial %}
            <span class="flag-badge bg-purple-200 text-purple-800 mr-0.5">
              {{ 'art' if locale == 'en' else '人工' }}
            </span>
            {% endif %}
            {% if row.preemptive %}
            <span class="flag-badge bg-red-200 text-red-800 mr-0.5">
              {{ 'pre' if locale == 'en' else '先制' }}
            </span>
            {% endif %}
            {% if row.forcing %}
            <span class="flag-badge bg-orange-200 text-orange-800">{{ row.forcing }}</span>
            {% endif %}
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </section>

  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">

    <!-- ══ 1NT Section ══ -->
    {% if nt_info %}
    <section class="border rounded p-4">
      <div class="section-head">
        {{ '1NT Opening' if locale == 'en' else '1NT 開叫' }}
      </div>
      <div class="space-y-2 text-sm">
        <div class="flex justify-between">
          <span class="text-gray-500">{{ 'HCP Range' if locale == 'en' else 'HCP 範圍' }}</span>
          <span class="font-mono font-bold text-blue-700">{{ nt_info.hcp_range }}</span>
        </div>
        {% if nt_info.description %}
        <p class="text-gray-600 text-xs">{{ nt_info.description }}</p>
        {% endif %}
        <div class="pt-2 border-t mt-2">
          <div class="flex justify-between">
            <span class="text-gray-500">Stayman</span>
            <span class="{{ 'check' if nt_info.has_stayman else 'cross' }}">
              {{ '✓' if nt_info.has_stayman else '✗' }}
            </span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500">{{ 'Jacoby Transfer' if locale == 'en' else '乘乘轉換' }}</span>
            <span class="{{ 'check' if nt_info.has_jacoby_transfer else 'cross' }}">
              {{ '✓' if nt_info.has_jacoby_transfer else '✗' }}
            </span>
          </div>
        </div>
      </div>
    </section>
    {% endif %}

    <!-- ══ Strong 2C Section ══ -->
    {% if strong_2c %}
    <section class="border rounded p-4">
      <div class="section-head">
        {{ 'Strong 2♣ Opening' if locale == 'en' else '強2♣ 開叫' }}
      </div>
      <div class="text-sm space-y-1">
        {% if strong_2c.hcp_summary %}
        <p class="font-mono text-xs text-gray-600">{{ strong_2c.hcp_summary }}</p>
        {% endif %}
        {% if strong_2c.description %}
        <p class="text-gray-700">{{ strong_2c.description }}</p>
        {% endif %}
        <span class="flag-badge bg-purple-200 text-purple-800">
          {{ 'Artificial' if locale == 'en' else '人工叫品' }}
        </span>
      </div>
    </section>
    {% endif %}

    <!-- ══ Weak Two Section ══ -->
    {% if weak_twos %}
    <section class="border rounded p-4">
      <div class="section-head">
        {{ ('Weak Twos' if style == 'wbf' else 'Two-Level Openings') if locale == 'en' else '弱二開叫' }}
      </div>
      <div class="space-y-2 text-sm">
        {% for wt in weak_twos %}
        <div class="flex gap-3">
          <span class="bid-cell text-blue-700 w-8 flex-shrink-0">{{ wt.bid }}</span>
          <span class="text-gray-500 font-mono text-xs">{{ wt.hcp_summary }}</span>
          {% if wt.description %}
          <span class="text-gray-600 text-xs">{{ wt.description }}</span>
          {% endif %}
        </div>
        {% endfor %}
        {% if style == 'acbl' %}
        <p class="text-xs text-gray-400 mt-1">{{ 'Sound / Light / Variable' if locale == 'en' else '牌力要求' }}</p>
        {% endif %}
      </div>
    </section>
    {% endif %}

    <!-- ══ Conventions ══ -->
    {% if conventions_list %}
    <section class="border rounded p-4 {{ 'md:col-span-2' if not (nt_info or strong_2c or weak_twos) else '' }}">
      <div class="section-head">
        {{ ('Conventions & Agreements' if style == 'acbl' else 'Conventions') if locale == 'en' else '特約' }}
      </div>
      <div class="space-y-2">
        {% for conv in conventions_list %}
        <div class="text-sm">
          <div class="flex items-center gap-2">
            <span class="font-semibold text-gray-800">{{ conv.name }}</span>
            <span class="font-mono text-xs text-gray-400">{{ conv.id }}</span>
          </div>
          {% if conv.description %}
          <p class="text-gray-600 text-xs mt-0.5">{{ conv.description }}</p>
          {% endif %}
        </div>
        {% endfor %}
      </div>
    </section>
    {% endif %}

  </div><!-- end grid -->

  <!-- ══ Footer ══ -->
  <footer class="mt-6 pt-4 border-t text-xs text-gray-400 flex justify-between no-print">
    <span>BBDSL Convention Card Generator</span>
    <span>{{ style.upper() }} Format</span>
  </footer>

</main>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_convcard(
    doc: BBDSLDocument,
    output_path: Path | None = None,
    locale: str = "en",
    style: str = "wbf",
    title: str | None = None,
) -> str:
    """Export a BBDSLDocument to a printable Convention Card HTML file.

    Args:
        doc: The BBDSL document.
        output_path: If given, write to this file.
        locale: 'en' or 'zh-TW'.
        style: 'wbf' or 'acbl' — determines card section labels.
        title: Override page title (default: system name + " Convention Card").

    Returns:
        The HTML string.
    """
    system_name = _t(doc.system.name, locale)
    system_version = getattr(doc.system, "version", None) or ""
    page_title = title or f"{system_name} — Convention Card"

    # Authors
    authors_list = getattr(doc.system, "authors", None) or []
    authors_str = ", ".join(
        (a.name if hasattr(a, "name") else str(a)) for a in authors_list
    )

    # Extract data
    opening_rows = _extract_opening_rows(doc, locale)
    nt_info = _extract_nt_info(doc, locale)
    strong_2c = _extract_strong_2c_info(doc, locale)
    weak_twos = _extract_weak_twos(doc, locale)
    conventions_list = _extract_conventions_list(doc, locale)
    completeness_items = _completeness_items(doc, locale)

    # Render
    env = Environment(loader=BaseLoader(), autoescape=True)
    tmpl = env.from_string(_CONVCARD_TEMPLATE)
    html = tmpl.render(
        page_title=page_title,
        system_name=system_name,
        system_version=system_version,
        authors=authors_str,
        locale=locale,
        style=style,
        opening_rows=opening_rows,
        nt_info=nt_info,
        strong_2c=strong_2c,
        weak_twos=weak_twos,
        conventions_list=conventions_list,
        completeness_items=completeness_items,
    )

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

    return html
