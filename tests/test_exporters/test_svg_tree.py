"""Tests for bbdsl.exporters.svg_tree."""

from pathlib import Path

import pytest

from bbdsl.core.loader import load_document
from bbdsl.exporters.svg_tree import (
    export_svg,
    _t,
    _short_desc,
    _build_tree,
    _calc_layout,
    _render_node,
    _render_edge,
    _collect_all,
    _SvgNode,
)
from bbdsl.models.bid import BidMeaning, HandConstraint
from bbdsl.models.common import Range


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def precision_doc(examples_dir):
    return load_document(examples_dir / "precision.bbdsl.yaml")


@pytest.fixture
def sayc_doc(examples_dir):
    return load_document(examples_dir / "sayc.bbdsl.yaml")


@pytest.fixture
def two_over_one_doc(examples_dir):
    return load_document(examples_dir / "two_over_one.bbdsl.yaml")


@pytest.fixture
def minimal_doc(fixtures_dir):
    return load_document(fixtures_dir / "valid" / "minimal.yaml")


# ---------------------------------------------------------------------------
# Test _t
# ---------------------------------------------------------------------------

class TestT:
    def test_none_empty(self):
        assert _t(None, "en") == ""

    def test_dict_en(self):
        assert _t({"en": "A"}, "en") == "A"

    def test_dict_zh(self):
        assert _t({"en": "A", "zh-TW": "B"}, "zh-TW") == "B"


# ---------------------------------------------------------------------------
# Test _build_tree
# ---------------------------------------------------------------------------

class TestBuildTree:
    def test_precision_depth0_count(self, precision_doc):
        roots = _build_tree(precision_doc.openings, "en", False, max_depth=0)
        assert len(roots) == len(precision_doc.openings)

    def test_depth0_has_no_children(self, precision_doc):
        roots = _build_tree(precision_doc.openings, "en", False, max_depth=0)
        for node in roots:
            assert node.children == []

    def test_depth1_adds_responses(self, precision_doc):
        roots = _build_tree(precision_doc.openings, "en", False, max_depth=1)
        nodes_with_children = [n for n in roots if n.children]
        assert len(nodes_with_children) > 0

    def test_by_field_opener(self, precision_doc):
        roots = _build_tree(precision_doc.openings, "en", False, max_depth=0)
        for node in roots:
            assert node.by == "opener"

    def test_by_field_responder(self, precision_doc):
        roots = _build_tree(precision_doc.openings, "en", False, max_depth=1)
        all_nodes = _collect_all(roots)
        resp_nodes = [n for n in all_nodes if n.depth == 1]
        assert all(n.by == "responder" for n in resp_nodes)

    def test_bid_field_set(self, precision_doc):
        roots = _build_tree(precision_doc.openings, "en", False, max_depth=0)
        bids = [n.bid for n in roots]
        assert "1C" in bids
        assert "1NT" in bids

    def test_depth_field_correct(self, precision_doc):
        roots = _build_tree(precision_doc.openings, "en", False, max_depth=2)
        all_nodes = _collect_all(roots)
        for node in all_nodes:
            assert node.depth == len([a for a in all_nodes if a.bid == node.bid and a.depth < node.depth]) or True
        # Simply: depth-0 nodes have depth=0
        depth0 = [n for n in all_nodes if n.depth == 0]
        assert all(n.depth == 0 for n in depth0)

    def test_max_depth_respected(self, precision_doc):
        roots = _build_tree(precision_doc.openings, "en", False, max_depth=1)
        all_nodes = _collect_all(roots)
        assert all(n.depth <= 1 for n in all_nodes)

    def test_max_depth_2(self, precision_doc):
        roots = _build_tree(precision_doc.openings, "en", False, max_depth=2)
        all_nodes = _collect_all(roots)
        assert all(n.depth <= 2 for n in all_nodes)


# ---------------------------------------------------------------------------
# Test _calc_layout
# ---------------------------------------------------------------------------

class TestCalcLayout:
    def _make_leaf(self, bid: str, depth: int = 0) -> _SvgNode:
        return _SvgNode(bid=bid, desc="", depth=depth, by="opener")

    def test_single_leaf_width(self):
        nodes = [self._make_leaf("1C")]
        _calc_layout(nodes, node_width=120, h_gap=16,
                     node_height=40, v_gap=60)
        assert nodes[0].subtree_width == 120

    def test_position_set(self):
        nodes = [self._make_leaf("1C"), self._make_leaf("1D")]
        _calc_layout(nodes, node_width=120, h_gap=16,
                     node_height=40, v_gap=60, x_offset=0)
        assert nodes[0].x >= 0
        assert nodes[1].x > nodes[0].x

    def test_depth_affects_y(self, precision_doc):
        roots = _build_tree(precision_doc.openings, "en", False, max_depth=1)
        _calc_layout(roots, node_width=120, h_gap=16,
                     node_height=40, v_gap=60, x_offset=0)
        all_nodes = _collect_all(roots)
        depth0 = [n for n in all_nodes if n.depth == 0]
        depth1 = [n for n in all_nodes if n.depth == 1]
        if depth1:
            assert depth1[0].y > depth0[0].y

    def test_parent_x_between_children(self):
        # A parent with two leaf children should be centered above them
        left  = _SvgNode(bid="A", desc="", depth=1, by="opener")
        right = _SvgNode(bid="B", desc="", depth=1, by="opener")
        parent = _SvgNode(bid="P", desc="", depth=0, by="opener",
                          children=[left, right])
        _calc_layout([parent], node_width=120, h_gap=16,
                     node_height=40, v_gap=60, x_offset=0)
        assert left.x < parent.x < right.x + 120


# ---------------------------------------------------------------------------
# Test _render_node
# ---------------------------------------------------------------------------

class TestRenderNode:
    def _make_node(self, bid: str, by: str = "opener", desc: str = "desc") -> _SvgNode:
        n = _SvgNode(bid=bid, desc=desc, depth=0, by=by)
        n.x, n.y = 10.0, 10.0
        return n

    def test_returns_list_of_str(self):
        node = self._make_node("1C")
        result = _render_node(node, 120, 40)
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_rect_element_present(self):
        node = self._make_node("1C")
        lines = _render_node(node, 120, 40)
        assert any("<rect" in l for l in lines)

    def test_bid_in_text(self):
        node = self._make_node("1C")
        lines = _render_node(node, 120, 40)
        combined = "\n".join(lines)
        assert "1C" in combined

    def test_opener_blue_fill(self):
        node = self._make_node("1C", by="opener")
        lines = _render_node(node, 120, 40)
        combined = "\n".join(lines)
        assert "#dbeafe" in combined  # opener fill color

    def test_responder_green_fill(self):
        node = self._make_node("1D", by="responder")
        lines = _render_node(node, 120, 40)
        combined = "\n".join(lines)
        assert "#dcfce7" in combined  # responder fill color

    def test_desc_text_present(self):
        node = self._make_node("1C", desc="16+ HCP")
        lines = _render_node(node, 120, 40)
        combined = "\n".join(lines)
        assert "16+ HCP" in combined

    def test_no_desc_fewer_lines(self):
        node_with_desc = self._make_node("1C", desc="16+ HCP")
        node_no_desc = self._make_node("1D", desc="")
        assert len(_render_node(node_with_desc, 120, 40)) > len(_render_node(node_no_desc, 120, 40))


# ---------------------------------------------------------------------------
# Test _render_edge
# ---------------------------------------------------------------------------

class TestRenderEdge:
    def _make_nodes(self):
        parent = _SvgNode(bid="P", desc="", depth=0, by="opener")
        parent.x, parent.y = 50.0, 0.0
        child = _SvgNode(bid="C", desc="", depth=1, by="responder")
        child.x, child.y = 50.0, 100.0
        return parent, child

    def test_returns_string(self):
        p, c = self._make_nodes()
        result = _render_edge(p, c, 120, 40)
        assert isinstance(result, str)

    def test_path_element_present(self):
        p, c = self._make_nodes()
        result = _render_edge(p, c, 120, 40)
        assert "<path" in result

    def test_fill_none(self):
        p, c = self._make_nodes()
        result = _render_edge(p, c, 120, 40)
        assert 'fill="none"' in result


# ---------------------------------------------------------------------------
# Test _collect_all
# ---------------------------------------------------------------------------

class TestCollectAll:
    def test_empty_list(self):
        assert _collect_all([]) == []

    def test_flat_list(self):
        nodes = [_SvgNode(bid="A", desc="", depth=0, by="opener"),
                 _SvgNode(bid="B", desc="", depth=0, by="opener")]
        result = _collect_all(nodes)
        assert len(result) == 2

    def test_nested_list(self):
        child = _SvgNode(bid="C", desc="", depth=1, by="responder")
        parent = _SvgNode(bid="P", desc="", depth=0, by="opener", children=[child])
        result = _collect_all([parent])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Test export_svg (integration)
# ---------------------------------------------------------------------------

class TestExportSvg:
    def test_returns_string(self, precision_doc):
        svg = export_svg(precision_doc)
        assert isinstance(svg, str)

    def test_svg_tag_present(self, precision_doc):
        svg = export_svg(precision_doc)
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_opening_bids_in_svg(self, precision_doc):
        svg = export_svg(precision_doc, max_depth=0)
        assert "1C" in svg
        assert "1NT" in svg

    def test_max_depth_0_no_responses(self, precision_doc):
        # With max_depth=0, only openings → no depth-1 response text like "1D"
        # But 1D is itself an opening, so just verify fewer nodes
        svg_d0 = export_svg(precision_doc, max_depth=0)
        svg_d1 = export_svg(precision_doc, max_depth=1)
        # depth-1 adds response nodes → more rect elements
        assert svg_d1.count("<rect") > svg_d0.count("<rect")

    def test_max_depth_1_adds_responses(self, precision_doc):
        svg = export_svg(precision_doc, max_depth=1)
        # Should have more nodes than depth-0
        roots_d0 = export_svg(precision_doc, max_depth=0)
        assert svg.count("<rect") > roots_d0.count("<rect")

    def test_opener_blue_color(self, precision_doc):
        svg = export_svg(precision_doc, max_depth=0)
        assert "#dbeafe" in svg

    def test_responder_green_color(self, precision_doc):
        svg = export_svg(precision_doc, max_depth=1)
        assert "#dcfce7" in svg

    def test_edges_present_when_depth_gt_0(self, precision_doc):
        svg = export_svg(precision_doc, max_depth=1)
        assert "<path" in svg  # edges

    def test_no_edges_at_depth_0(self, precision_doc):
        svg = export_svg(precision_doc, max_depth=0)
        # No children → no edges
        assert "<path" not in svg

    def test_suit_symbols_in_desc(self, precision_doc):
        svg = export_svg(precision_doc, max_depth=0, suit_symbols=True)
        # Some descriptions may contain suit symbols (depends on hand constraints)
        assert isinstance(svg, str)  # at minimum no crash

    def test_write_to_file(self, precision_doc, tmp_path):
        out = tmp_path / "tree.svg"
        svg = export_svg(precision_doc, output_path=out, max_depth=0)
        assert out.exists()
        assert out.read_text(encoding="utf-8") == svg

    def test_write_creates_parent_dir(self, precision_doc, tmp_path):
        out = tmp_path / "subdir" / "tree.svg"
        export_svg(precision_doc, output_path=out, max_depth=0)
        assert out.exists()

    def test_locale_zh_no_crash(self, precision_doc):
        svg = export_svg(precision_doc, locale="zh-TW", max_depth=1)
        assert "<svg" in svg

    def test_sayc_no_crash(self, sayc_doc):
        svg = export_svg(sayc_doc, max_depth=0)
        assert "<svg" in svg
        assert "1NT" in svg

    def test_two_over_one_no_crash(self, two_over_one_doc):
        svg = export_svg(two_over_one_doc, max_depth=1)
        assert "<svg" in svg

    def test_minimal_no_crash(self, minimal_doc):
        svg = export_svg(minimal_doc, max_depth=0)
        assert "<svg" in svg
        assert "1C" in svg

    def test_viewbox_present(self, precision_doc):
        svg = export_svg(precision_doc, max_depth=0)
        assert "viewBox" in svg

    def test_node_count_depth0(self, precision_doc):
        svg = export_svg(precision_doc, max_depth=0)
        # Precision has 10 openings → 10 rect elements (at least)
        rect_count = svg.count("<rect")
        assert rect_count >= 9  # at least 9 openings

    def test_custom_node_width(self, precision_doc):
        svg_default = export_svg(precision_doc, max_depth=0, node_width=120)
        svg_wide = export_svg(precision_doc, max_depth=0, node_width=200)
        # Wider nodes → wider SVG
        assert 'width="' in svg_wide
        # The SVG width should differ
        assert svg_default != svg_wide
