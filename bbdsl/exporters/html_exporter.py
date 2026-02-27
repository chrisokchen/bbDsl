"""BBDSL → interactive HTML Viewer exporter.

Produces a single self-contained HTML file with:
  - Collapsible/expandable bidding tree
  - Color coding: opener=blue, responder=green
  - Hover tooltips: full bid path + hand constraints
  - Search/highlight by bid sequence
  - Convention module blocks (collapsible)
  - Responsive layout (Tailwind CSS via CDN)
  - i18n: locale='en' or 'zh-TW'
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, BaseLoader

from bbdsl.models.system import BBDSLDocument


# ---------------------------------------------------------------------------
# i18n helpers
# ---------------------------------------------------------------------------

def _t(value: Any, locale: str) -> str:
    """Extract localised string."""
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get(locale) or value.get("en") or next(iter(value.values()), "")
    return str(value)


# ---------------------------------------------------------------------------
# Hand constraint → description fragments
# ---------------------------------------------------------------------------

_SUIT_SYMBOLS = {"spades": "♠", "hearts": "♥", "diamonds": "♦", "clubs": "♣"}
_SUIT_EN = {"spades": "spades", "hearts": "hearts", "diamonds": "diamonds", "clubs": "clubs"}
_SUIT_ZH = {"spades": "黑桃", "hearts": "紅心", "diamonds": "方塊", "clubs": "梅花"}
_FORCING_EN = {"game": "GF", "invitational": "INV", "one_round": "F1",
               "signoff": "S/O", "none": "NF"}
_FORCING_ZH = {"game": "成局強迫", "invitational": "邀請", "one_round": "一輪強迫",
               "signoff": "到叫", "none": "非強迫"}
_SHAPE_ZH = {"balanced": "平均", "semi_balanced": "半平均", "semi-balanced": "半平均"}


def _hand_parts(hand: Any, locale: str, suit_symbols: bool) -> list[str]:
    parts: list[str] = []
    if hand is None:
        return parts
    suit_labels = _SUIT_SYMBOLS if suit_symbols else (_SUIT_ZH if locale == "zh-TW" else _SUIT_EN)

    if hand.hcp:
        h = hand.hcp
        if h.min is not None and h.max is not None:
            parts.append(f"{h.min}-{h.max} HCP")
        elif h.min is not None:
            parts.append(f"{h.min}+ HCP")
        elif h.max is not None:
            parts.append(f"≤{h.max} HCP")

    for suit in ("spades", "hearts", "diamonds", "clubs"):
        r = getattr(hand, suit, None)
        if r is None:
            continue
        label = suit_labels[suit]
        if r.min is not None and r.max is not None:
            parts.append(f"{r.min}-{r.max} {label}")
        elif r.min is not None:
            parts.append(f"{r.min}+ {label}")
        elif r.max is not None:
            parts.append(f"≤{r.max} {label}")

    if hand.shape and isinstance(hand.shape, dict) and "ref" in hand.shape:
        ref = hand.shape["ref"]
        if locale == "zh-TW":
            parts.append(_SHAPE_ZH.get(ref, ref))
        else:
            parts.append(ref.replace("_", "-"))
    elif isinstance(hand.shape, str) and hand.shape not in ("any", ""):
        parts.append(hand.shape)

    return parts


def _build_description(node: Any, locale: str, suit_symbols: bool) -> str:
    meaning = getattr(node, "meaning", None)
    if meaning is None:
        ref = getattr(node, "ref", None)
        return f"→ {ref}" if ref else ""
    parts: list[str] = []
    desc = _t(meaning.description, locale)
    if desc:
        parts.append(desc)
    if not parts and meaning.hand:
        parts.extend(_hand_parts(meaning.hand, locale, suit_symbols))
    if meaning.artificial:
        parts.append("art")
    if meaning.forcing:
        fval = meaning.forcing.value if hasattr(meaning.forcing, "value") else str(meaning.forcing)
        parts.append((_FORCING_ZH if locale == "zh-TW" else _FORCING_EN).get(fval, fval))
    if meaning.preemptive:
        parts.append("先制" if locale == "zh-TW" else "preemptive")
    if meaning.transfer_to:
        parts.append(f"→{meaning.transfer_to}")
    ref = getattr(node, "ref", None)
    if ref:
        parts.append(f"[{ref}]")
    return ", ".join(parts)


def _build_hand_tooltip(node: Any, locale: str, suit_symbols: bool) -> str:
    meaning = getattr(node, "meaning", None)
    if meaning is None or meaning.hand is None:
        return ""
    return " · ".join(_hand_parts(meaning.hand, locale, suit_symbols))


# ---------------------------------------------------------------------------
# Tree flattener → list of view-model dicts
# ---------------------------------------------------------------------------

def _node_id(path: str) -> str:
    """Convert bid path to safe HTML id."""
    return "n-" + path.replace(" ", "_").replace("-", "_").replace("/", "_")


def _flatten_tree(
    nodes: list[Any],
    parent_path: str,
    depth: int,
    locale: str,
    suit_symbols: bool,
    result: list[dict],
) -> None:
    for node in nodes:
        bid = getattr(node, "bid", None) or ""
        if not bid:
            continue
        path = f"{parent_path}-{bid}" if parent_path else bid
        by = getattr(node, "by", None)
        meaning = getattr(node, "meaning", None)

        artificial = bool(meaning and meaning.artificial) if meaning else False
        preemptive = bool(meaning and meaning.preemptive) if meaning else False
        alertable = bool(meaning and meaning.alertable) if meaning else False
        forcing = None
        if meaning and meaning.forcing:
            fval = meaning.forcing.value if hasattr(meaning.forcing, "value") else str(meaning.forcing)
            forcing = (_FORCING_ZH if locale == "zh-TW" else _FORCING_EN).get(fval, fval)

        responses = getattr(node, "responses", None) or []
        continuations = getattr(node, "continuations", None) or []
        has_children = bool(responses or continuations)

        result.append({
            "bid": bid,
            "path": path,
            "depth": depth,
            "by": by or ("opener" if depth == 0 else "responder"),
            "description": _build_description(node, locale, suit_symbols),
            "hand_tooltip": _build_hand_tooltip(node, locale, suit_symbols),
            "has_children": has_children,
            "artificial": artificial,
            "preemptive": preemptive,
            "alertable": alertable,
            "forcing": forcing,
            "node_id": _node_id(path),
            "parent_id": _node_id(parent_path) if parent_path else "",
            "parent_path": parent_path,
        })

        _flatten_tree(responses, path, depth + 1, locale, suit_symbols, result)
        _flatten_tree(continuations, path, depth + 1, locale, suit_symbols, result)


# ---------------------------------------------------------------------------
# Convention view builder
# ---------------------------------------------------------------------------

def _build_conv_views(doc: BBDSLDocument, locale: str, suit_symbols: bool) -> list[dict]:
    views = []
    for key, conv in (doc.conventions or {}).items():
        desc = _t(getattr(conv, "description", None), locale)
        name = _t(getattr(conv, "name", None), locale) or key
        conv_id = getattr(conv, "id", key)
        bids = []
        for rb in getattr(conv, "responses", None) or []:
            bid = getattr(rb, "bid", None) or ""
            m = getattr(rb, "meaning", None)
            rdesc = _t(getattr(m, "description", None), locale) if m else ""
            if bid:
                bids.append({"bid": bid, "description": rdesc})
        views.append({
            "key": key,
            "conv_id": conv_id,
            "name": name,
            "description": desc,
            "bids": bids,
            "node_id": "conv-" + key.replace("/", "-"),
        })
    return views


# ---------------------------------------------------------------------------
# Completeness bar helper
# ---------------------------------------------------------------------------

def _completeness_items(doc: BBDSLDocument, locale: str) -> list[dict]:
    comp = getattr(doc.system, "completeness", None)
    if comp is None:
        return []
    items = []
    labels_en = {
        "openings": "Openings", "responses_to_1c": "Responses to 1C",
        "responses_to_1nt": "Responses to 1NT", "defensive": "Defensive",
        "competitive": "Competitive", "slam_bidding": "Slam Bidding",
    }
    labels_zh = {
        "openings": "開叫", "responses_to_1c": "1梅花回應",
        "responses_to_1nt": "1NT回應", "defensive": "競叫防守",
        "competitive": "競叫", "slam_bidding": "滿貫叫牌",
    }
    colors = {"complete": "bg-green-500", "partial": "bg-yellow-400",
              "draft": "bg-orange-400", "todo": "bg-gray-300"}
    labels = labels_zh if locale == "zh-TW" else labels_en
    for field, label in labels.items():
        val = getattr(comp, field, None)
        if val is None:
            continue
        status = val.value if hasattr(val, "value") else str(val)
        items.append({"label": label, "status": status, "color": colors.get(status, "bg-gray-300")})
    return items


# ---------------------------------------------------------------------------
# HTML template (embedded Jinja2)
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="{{ locale }}">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{{ page_title }}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    [data-hidden="true"] { display: none; }
    .bid-row { transition: background-color 0.15s; }
    .bid-row:hover { filter: brightness(0.97); }
    .highlight { outline: 2px solid #f59e0b; background-color: #fef3c7 !important; }
    .bid-badge { font-size: 0.65rem; padding: 0 4px; border-radius: 3px; font-weight: 600;
                 display: inline-block; margin-left: 4px; vertical-align: middle; }
    .tooltip-box { position: absolute; z-index: 50; background: #1e293b; color: #f8fafc;
                   padding: 6px 10px; border-radius: 6px; font-size: 0.78rem; max-width: 320px;
                   pointer-events: none; white-space: pre-wrap; box-shadow: 0 4px 12px rgba(0,0,0,.3); }
    .conv-block { border-left: 3px solid #818cf8; }
  </style>
</head>
<body class="bg-gray-50 text-gray-800 font-sans min-h-screen">

<!-- ════ HEADER ════ -->
<header class="bg-white border-b border-gray-200 shadow-sm sticky top-0 z-40">
  <div class="max-w-6xl mx-auto px-4 py-3 flex flex-wrap items-center gap-4">
    <div class="flex-1 min-w-0">
      <h1 class="text-xl font-bold text-gray-900 truncate">{{ system_name }}</h1>
      {% if system_version %}<span class="text-sm text-gray-500 ml-2">v{{ system_version }}</span>{% endif %}
    </div>
    <!-- Search -->
    <div class="flex items-center gap-2">
      <input id="search" type="text" placeholder="{{ 'Search bid (e.g. 1C-1D)' if locale == 'en' else '搜尋叫品路徑 (例: 1C-1D)' }}"
             class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm w-52 focus:outline-none focus:ring-2 focus:ring-blue-400"
             oninput="handleSearch(this.value)"/>
      <button onclick="expandAll()" class="text-xs bg-blue-100 hover:bg-blue-200 text-blue-800 px-2 py-1 rounded">
        {{ '展開全部' if locale == 'zh-TW' else 'Expand All' }}
      </button>
      <button onclick="collapseAll()" class="text-xs bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded">
        {{ '收合全部' if locale == 'zh-TW' else 'Collapse All' }}
      </button>
    </div>
  </div>
  {% if completeness_items %}
  <div class="max-w-6xl mx-auto px-4 pb-2 flex flex-wrap gap-2">
    {% for item in completeness_items %}
    <div class="flex items-center gap-1 text-xs text-gray-600">
      <span class="inline-block w-2 h-2 rounded-full {{ item.color }}"></span>
      <span>{{ item.label }}</span>
      <span class="text-gray-400">({{ item.status }})</span>
    </div>
    {% endfor %}
  </div>
  {% endif %}
</header>

<!-- ════ MAIN ════ -->
<main class="max-w-6xl mx-auto px-4 py-6 space-y-6">

  <!-- Legend -->
  <div class="flex flex-wrap gap-3 text-xs text-gray-600">
    <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-blue-100 border border-blue-300 inline-block"></span>{{ 'Opener' if locale == 'en' else '開叫方' }}</span>
    <span class="flex items-center gap-1"><span class="w-3 h-3 rounded bg-green-100 border border-green-300 inline-block"></span>{{ 'Responder' if locale == 'en' else '回應方' }}</span>
    <span class="flex items-center gap-1"><span class="bid-badge bg-purple-200 text-purple-800">art</span>{{ 'Artificial' if locale == 'en' else '人工叫' }}</span>
    <span class="flex items-center gap-1"><span class="bid-badge bg-orange-200 text-orange-800">GF</span>{{ 'Game Force' if locale == 'en' else '成局強迫' }}</span>
    <span class="flex items-center gap-1"><span class="bid-badge bg-red-200 text-red-800">pre</span>{{ 'Preemptive' if locale == 'en' else '先制' }}</span>
  </div>

  <!-- ── Conventions ── -->
  {% if conv_views %}
  <section>
    <button onclick="toggleSection('conv-section')"
            class="flex items-center gap-2 text-sm font-semibold text-indigo-700 hover:text-indigo-900 mb-2">
      <span id="conv-section-icon">▶</span>
      {{ 'Conventions (' + conv_views|length|string + ')' if locale == 'en' else 'Convention 定義 (' + conv_views|length|string + ')' }}
    </button>
    <div id="conv-section" data-hidden="true" class="space-y-3">
      {% for conv in conv_views %}
      <div class="conv-block bg-indigo-50 rounded-r-lg px-4 py-3">
        <div class="flex items-center gap-2 cursor-pointer" onclick="toggleSection('{{ conv.node_id }}')">
          <span id="{{ conv.node_id }}-icon" class="text-indigo-400 text-xs">▶</span>
          <span class="font-semibold text-indigo-800">{{ conv.name }}</span>
          <code class="text-xs text-gray-500 bg-gray-100 px-1 rounded">{{ conv.conv_id }}</code>
        </div>
        <div id="{{ conv.node_id }}" data-hidden="true" class="mt-2 space-y-1">
          {% if conv.description %}
          <p class="text-sm text-gray-600 italic">{{ conv.description }}</p>
          {% endif %}
          {% for b in conv.bids %}
          <div class="flex gap-3 text-sm">
            <span class="font-mono font-bold text-indigo-700 w-8">{{ b.bid }}</span>
            <span class="text-gray-700">{{ b.description }}</span>
          </div>
          {% endfor %}
        </div>
      </div>
      {% endfor %}
    </div>
  </section>
  {% endif %}

  <!-- ── Bidding Tree ── -->
  <section>
    <h2 class="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
      {{ 'Opening Bids' if locale == 'en' else '開叫系統' }}
    </h2>
    <div id="bid-tree" class="space-y-0.5">
      {% for node in nodes %}
      <div id="{{ node.node_id }}"
           data-path="{{ node.path }}"
           data-parent="{{ node.parent_id }}"
           data-depth="{{ node.depth }}"
           data-hidden="{{ 'true' if node.depth > 0 else 'false' }}"
           class="bid-row relative flex items-start gap-2 px-3 py-1.5 rounded-lg text-sm
                  {% if node.by == 'opener' %}bg-blue-50 border border-blue-200{% else %}bg-green-50 border border-green-200{% endif %}"
           style="margin-left: {{ node.depth * 20 }}px">

        <!-- Toggle button -->
        {% if node.has_children %}
        <button class="toggle-btn flex-shrink-0 w-5 h-5 flex items-center justify-center
                       text-gray-400 hover:text-gray-700 text-xs font-mono"
                data-node="{{ node.node_id }}"
                onclick="toggleNode('{{ node.node_id }}')"
                title="{{ 'Expand/Collapse' if locale == 'en' else '展開/收合' }}">▶</button>
        {% else %}
        <span class="flex-shrink-0 w-5 h-5"></span>
        {% endif %}

        <!-- Bid label -->
        <span class="font-mono font-bold
                     {% if node.by == 'opener' %}text-blue-800{% else %}text-green-800{% endif %}
                     w-12 flex-shrink-0 text-base leading-5">{{ node.bid }}</span>

        <!-- Description -->
        <span class="flex-1 text-gray-700 leading-5">{{ node.description }}</span>

        <!-- Badges -->
        <div class="flex-shrink-0 flex items-center gap-1">
          {% if node.artificial %}
          <span class="bid-badge bg-purple-200 text-purple-800">art</span>
          {% endif %}
          {% if node.forcing %}
          <span class="bid-badge bg-orange-200 text-orange-800">{{ node.forcing }}</span>
          {% endif %}
          {% if node.preemptive %}
          <span class="bid-badge bg-red-200 text-red-800">pre</span>
          {% endif %}
        </div>

        <!-- Tooltip trigger (hand constraints) -->
        {% if node.hand_tooltip %}
        <span class="flex-shrink-0 w-4 h-4 text-gray-400 hover:text-gray-600 cursor-help text-xs leading-4"
              onmouseenter="showTooltip(event, '{{ node.path }}: {{ node.hand_tooltip }}')"
              onmouseleave="hideTooltip()">ℹ</span>
        {% endif %}

        <!-- Path breadcrumb (shown on hover via data attr, used for search) -->
      </div>
      {% endfor %}
    </div>
  </section>

</main>

<!-- Tooltip container -->
<div id="tooltip" class="tooltip-box hidden"></div>

<!-- ════ JAVASCRIPT ════ -->
<script>
// Node tree data (for expand/collapse)
const nodeData = {{ node_json }};

// ── Tooltip ──
function showTooltip(e, text) {
  const tip = document.getElementById('tooltip');
  tip.textContent = text;
  tip.classList.remove('hidden');
  positionTooltip(e);
}
function hideTooltip() {
  document.getElementById('tooltip').classList.add('hidden');
}
function positionTooltip(e) {
  const tip = document.getElementById('tooltip');
  let x = e.clientX + 12, y = e.clientY + 12;
  if (x + 340 > window.innerWidth) x = e.clientX - 340;
  if (y + 80 > window.innerHeight) y = e.clientY - 80;
  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
  tip.style.position = 'fixed';
}
document.addEventListener('mousemove', e => {
  const tip = document.getElementById('tooltip');
  if (!tip.classList.contains('hidden')) positionTooltip(e);
});

// ── Toggle single node's children ──
function toggleNode(nodeId) {
  const btn = document.querySelector(`[data-node="${nodeId}"] `);
  const children = document.querySelectorAll(`[data-parent="${nodeId}"]`);
  const allHidden = Array.from(children).every(c => c.dataset.hidden === 'true');

  children.forEach(child => {
    if (allHidden) {
      // expand: show direct children, keep grand-children hidden
      child.dataset.hidden = 'false';
    } else {
      // collapse: hide this child and ALL its descendants
      setSubtreeHidden(child.dataset.path, true);
    }
  });

  // Update toggle button icon
  const toggleBtn = document.querySelector(`.toggle-btn[data-node="${nodeId}"]`);
  if (toggleBtn) toggleBtn.textContent = allHidden ? '▼' : '▶';
}

function setSubtreeHidden(path, hidden) {
  document.querySelectorAll(`[data-path^="${path}"]`).forEach(el => {
    if (el.dataset.path === path || el.dataset.path.startsWith(path + '-')) {
      el.dataset.hidden = hidden ? 'true' : 'false';
    }
  });
  // Reset toggle buttons in the subtree
  document.querySelectorAll(`[data-path^="${path}"] .toggle-btn`).forEach(btn => {
    btn.textContent = '▶';
  });
}

// ── Section toggle (conventions, etc.) ──
function toggleSection(id) {
  const el = document.getElementById(id);
  const icon = document.getElementById(id + '-icon');
  if (!el) return;
  const hidden = el.dataset.hidden === 'true';
  el.dataset.hidden = hidden ? 'false' : 'true';
  if (icon) icon.textContent = hidden ? '▼' : '▶';
}

// ── Expand / Collapse All ──
function expandAll() {
  document.querySelectorAll('#bid-tree [data-hidden]').forEach(el => {
    el.dataset.hidden = 'false';
  });
  document.querySelectorAll('.toggle-btn').forEach(btn => btn.textContent = '▼');
}
function collapseAll() {
  document.querySelectorAll('#bid-tree [data-depth]').forEach(el => {
    el.dataset.hidden = el.dataset.depth === '0' ? 'false' : 'true';
  });
  document.querySelectorAll('.toggle-btn').forEach(btn => btn.textContent = '▶');
}

// ── Search / highlight ──
let searchTimer = null;
function handleSearch(query) {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => applySearch(query.trim().toUpperCase()), 200);
}

function applySearch(query) {
  const allNodes = document.querySelectorAll('#bid-tree [data-path]');
  allNodes.forEach(el => el.classList.remove('highlight'));

  if (!query) return;

  // Find matching nodes
  const matches = Array.from(allNodes).filter(el =>
    el.dataset.path.toUpperCase().includes(query)
  );
  if (matches.length === 0) return;

  matches.forEach(el => {
    // Highlight the match
    el.classList.add('highlight');
    // Reveal all ancestors
    let parentId = el.dataset.parent;
    while (parentId) {
      const parent = document.getElementById(parentId);
      if (!parent) break;
      parent.dataset.hidden = 'false';
      const btn = parent.querySelector('.toggle-btn');
      if (btn) btn.textContent = '▼';
      // Also show the matched element
      el.dataset.hidden = 'false';
      parentId = parent.dataset.parent;
    }
    el.dataset.hidden = 'false';
  });
}

// ── Initial state: only show depth-0 (openings) ──
document.addEventListener('DOMContentLoaded', () => {
  collapseAll();
});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_html(
    doc: BBDSLDocument,
    output_path: Path | None = None,
    locale: str = "en",
    suit_symbols: bool = False,
    title: str | None = None,
) -> str:
    """Export a BBDSLDocument to a self-contained interactive HTML file.

    Args:
        doc: The BBDSL document.
        output_path: If given, write to this file.
        locale: 'en' or 'zh-TW'.
        suit_symbols: Use ♠♥♦♣ in suit descriptions.
        title: Override page title (default: system name).

    Returns:
        The HTML string.
    """
    system_name = _t(doc.system.name, locale)
    system_version = getattr(doc.system, "version", None) or ""
    page_title = title or f"BBDSL Viewer — {system_name}"

    # Flatten bidding tree
    nodes: list[dict] = []
    _flatten_tree(doc.openings or [], "", 0, locale, suit_symbols, nodes)

    # Node JSON for JS
    node_json = json.dumps(
        [{"id": n["node_id"], "path": n["path"], "parent": n["parent_id"],
          "depth": n["depth"]} for n in nodes],
        ensure_ascii=False,
    )

    # Convention views
    conv_views = _build_conv_views(doc, locale, suit_symbols)

    # Completeness items
    completeness_items = _completeness_items(doc, locale)

    # Render template
    env = Environment(loader=BaseLoader(), autoescape=True)
    tmpl = env.from_string(_HTML_TEMPLATE)
    html = tmpl.render(
        page_title=page_title,
        system_name=system_name,
        system_version=system_version,
        locale=locale,
        nodes=nodes,
        node_json=node_json,
        conv_views=conv_views,
        completeness_items=completeness_items,
    )

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

    return html
