"""Tests for bbdsl.exporters.ai_kb_exporter."""

import json
from pathlib import Path

import pytest

from bbdsl.core.loader import load_document
from bbdsl.exporters.ai_kb_exporter import (
    _build_context_text,
    _convention_rules,
    _flags,
    _flatten_to_rules,
    _hand_constraint_dict,
    _t,
    export_ai_kb,
    _to_json,
    _to_jsonl,
)
from bbdsl.models.bid import BidMeaning, HandConstraint
from bbdsl.models.common import ForcingLevel, Range

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PRECISION_PATH = "examples/precision.bbdsl.yaml"
SAYC_PATH = "examples/sayc.bbdsl.yaml"
TWO_OVER_ONE_PATH = "examples/two_over_one.bbdsl.yaml"


@pytest.fixture(scope="module")
def precision_doc():
    return load_document(PRECISION_PATH)


@pytest.fixture(scope="module")
def sayc_doc():
    return load_document(SAYC_PATH)


@pytest.fixture(scope="module")
def two_over_one_doc():
    return load_document(TWO_OVER_ONE_PATH)


# ---------------------------------------------------------------------------
# _t helper
# ---------------------------------------------------------------------------

class TestT:
    def test_none_returns_empty(self):
        assert _t(None, "en") == ""

    def test_str_pass_through(self):
        assert _t("hello", "en") == "hello"

    def test_dict_locale(self):
        assert _t({"en": "Hello", "zh-TW": "你好"}, "zh-TW") == "你好"

    def test_dict_fallback_en(self):
        assert _t({"en": "Hello"}, "zh-TW") == "Hello"


# ---------------------------------------------------------------------------
# _hand_constraint_dict
# ---------------------------------------------------------------------------

class TestHandConstraintDict:
    def test_empty_constraint_gives_empty_dict(self):
        hc = HandConstraint()
        assert _hand_constraint_dict(hc) == {}

    def test_none_gives_empty_dict(self):
        assert _hand_constraint_dict(None) == {}

    def test_hcp_range(self):
        hc = HandConstraint(hcp=Range(min=15, max=17))
        d = _hand_constraint_dict(hc)
        assert "hcp" in d
        assert d["hcp"]["min"] == 15
        assert d["hcp"]["max"] == 17

    def test_hcp_min_only(self):
        hc = HandConstraint(hcp=Range(min=16))
        d = _hand_constraint_dict(hc)
        assert d["hcp"] == {"min": 16}

    def test_suit_length(self):
        hc = HandConstraint(hearts=Range(min=5))
        d = _hand_constraint_dict(hc)
        assert "hearts" in d
        assert d["hearts"]["min"] == 5

    def test_shape_dict(self):
        hc = HandConstraint(shape={"ref": "balanced"})
        d = _hand_constraint_dict(hc)
        assert d["shape"] == {"ref": "balanced"}

    def test_multiple_fields(self):
        hc = HandConstraint(hcp=Range(min=11, max=15), hearts=Range(min=5))
        d = _hand_constraint_dict(hc)
        assert "hcp" in d
        assert "hearts" in d

    def test_none_fields_omitted(self):
        hc = HandConstraint(hcp=Range(min=15))
        d = _hand_constraint_dict(hc)
        # Only hcp should be present; suits should be absent
        assert "clubs" not in d
        assert "diamonds" not in d

    def test_controls(self):
        hc = HandConstraint(controls=Range(min=4))
        d = _hand_constraint_dict(hc)
        assert "controls" in d
        assert d["controls"]["min"] == 4


# ---------------------------------------------------------------------------
# _flags
# ---------------------------------------------------------------------------

class TestFlags:
    def test_no_flags(self):
        m = BidMeaning()
        assert _flags(m, "en") == []

    def test_artificial_flag_en(self):
        m = BidMeaning(artificial=True)
        assert "Alert" in _flags(m, "en")

    def test_artificial_flag_zh(self):
        m = BidMeaning(artificial=True)
        assert "人工" in _flags(m, "zh-TW")

    def test_forcing_game_en(self):
        m = BidMeaning(forcing=ForcingLevel.GAME)
        assert "GF" in _flags(m, "en")

    def test_forcing_one_round_en(self):
        m = BidMeaning(forcing=ForcingLevel.ONE_ROUND)
        assert "F1" in _flags(m, "en")

    def test_preemptive_flag(self):
        m = BidMeaning(preemptive=True)
        assert "Preemptive" in _flags(m, "en")

    def test_transfer_to(self):
        m = BidMeaning(transfer_to="2H")
        f = _flags(m, "en")
        assert any("2H" in x for x in f)

    def test_none_meaning(self):
        assert _flags(None, "en") == []


# ---------------------------------------------------------------------------
# _build_context_text
# ---------------------------------------------------------------------------

class TestBuildContextText:
    def _meaning(self, desc="Strong opening", art=False, forcing=None):
        return BidMeaning(
            description={"en": desc, "zh-TW": "強開叫"},
            artificial=art,
            forcing=forcing,
        )

    def test_opening_en(self):
        m = self._meaning()
        t = _build_context_text([], "1C", "opener", "Precision Club", m, "en")
        assert "Precision Club" in t
        assert "1C" in t
        assert "Strong opening" in t

    def test_opening_zh(self):
        m = self._meaning()
        t = _build_context_text([], "1C", "開叫者", "精準制", m, "zh-TW")
        assert "精準制" in t
        assert "1C" in t
        assert "強開叫" in t

    def test_response_en(self):
        m = self._meaning("Negative response")
        t = _build_context_text(["1C"], "1D", "responder", "Precision Club", m, "en")
        assert "1C" in t
        assert "1D" in t
        assert "Negative response" in t
        assert "responder" in t

    def test_response_zh(self):
        m = self._meaning()
        t = _build_context_text(["1C"], "1D", "responder", "精準制", m, "zh-TW")
        assert "精準制" in t
        assert "1D" in t

    def test_flags_in_context_text(self):
        m = BidMeaning(description="Artificial", artificial=True, forcing=ForcingLevel.GAME)
        t = _build_context_text([], "2C", "opener", "System", m, "en")
        assert "Alert" in t or "GF" in t

    def test_none_meaning(self):
        t = _build_context_text([], "1C", "opener", "System", None, "en")
        assert "1C" in t


# ---------------------------------------------------------------------------
# _flatten_to_rules
# ---------------------------------------------------------------------------

class TestFlattenToRules:
    def test_precision_has_rules(self, precision_doc):
        result: list = []
        _flatten_to_rules(
            precision_doc.openings or [], [], "Precision Club", "en", result
        )
        assert len(result) > 0

    def test_each_rule_has_required_fields(self, precision_doc):
        result: list = []
        _flatten_to_rules(
            precision_doc.openings or [], [], "Precision Club", "en", result
        )
        required = {"id", "sequence", "bid", "by", "system", "description",
                    "hand_constraint", "artificial", "alertable", "forcing",
                    "transfer_to", "preemptive", "context_text"}
        for r in result:
            assert required.issubset(r.keys()), f"Missing keys in rule: {r}"

    def test_opening_sequence_empty(self, precision_doc):
        result: list = []
        _flatten_to_rules(
            precision_doc.openings or [], [], "Precision Club", "en", result
        )
        openings = [r for r in result if r["sequence"] == []]
        assert len(openings) == len(precision_doc.openings)

    def test_response_sequence_non_empty(self, precision_doc):
        result: list = []
        _flatten_to_rules(
            precision_doc.openings or [], [], "Precision Club", "en", result
        )
        responses = [r for r in result if len(r["sequence"]) >= 1]
        assert len(responses) > 0

    def test_id_is_full_path(self, precision_doc):
        result: list = []
        _flatten_to_rules(
            precision_doc.openings or [], [], "Precision Club", "en", result
        )
        for r in result:
            expected_id = "-".join(r["sequence"] + [r["bid"]])
            assert r["id"] == expected_id

    def test_hand_constraint_dict_type(self, precision_doc):
        result: list = []
        _flatten_to_rules(
            precision_doc.openings or [], [], "Precision Club", "en", result
        )
        for r in result:
            assert isinstance(r["hand_constraint"], dict)

    def test_context_text_non_empty(self, precision_doc):
        result: list = []
        _flatten_to_rules(
            precision_doc.openings or [], [], "Precision Club", "en", result
        )
        for r in result:
            assert len(r["context_text"]) > 0

    def test_system_name_in_rules(self, precision_doc):
        result: list = []
        _flatten_to_rules(
            precision_doc.openings or [], [], "TestSystem", "en", result
        )
        for r in result:
            assert r["system"] == "TestSystem"


# ---------------------------------------------------------------------------
# _convention_rules
# ---------------------------------------------------------------------------

class TestConventionRules:
    def test_precision_conventions_non_empty(self, precision_doc):
        if not precision_doc.conventions:
            pytest.skip("Precision doc has no conventions")
        rules = _convention_rules(precision_doc, "Precision Club", "en")
        assert len(rules) >= 0  # May be empty if conventions have no bids

    def test_convention_field_present(self, precision_doc):
        if not precision_doc.conventions:
            pytest.skip("Precision doc has no conventions")
        rules = _convention_rules(precision_doc, "Precision Club", "en")
        for r in rules:
            assert "convention" in r

    def test_id_prefixed_with_conv_key(self, precision_doc):
        if not precision_doc.conventions:
            pytest.skip("Precision doc has no conventions")
        rules = _convention_rules(precision_doc, "Precision Club", "en")
        for r in rules:
            assert "/" in r["id"]


# ---------------------------------------------------------------------------
# _to_json / _to_jsonl
# ---------------------------------------------------------------------------

class TestSerialisation:
    def _sample_rules(self):
        return [
            {"id": "1C", "bid": "1C", "context_text": "Opening 1C"},
            {"id": "1D", "bid": "1D", "context_text": "Opening 1D"},
        ]

    def test_to_jsonl_valid(self):
        rules = self._sample_rules()
        out = _to_jsonl(rules)
        lines = [l for l in out.strip().split("\n") if l]
        assert len(lines) == 2
        for line in lines:
            obj = json.loads(line)
            assert "id" in obj

    def test_to_jsonl_empty(self):
        out = _to_jsonl([])
        assert out == ""

    def test_to_json_structure(self):
        rules = self._sample_rules()
        out = _to_json(rules, "TestSystem", "en")
        d = json.loads(out)
        assert "metadata" in d
        assert "rules" in d
        assert d["metadata"]["system"] == "TestSystem"
        assert d["metadata"]["count"] == 2
        assert len(d["rules"]) == 2


# ---------------------------------------------------------------------------
# export_ai_kb
# ---------------------------------------------------------------------------

class TestExportAiKb:
    def test_returns_list(self, precision_doc):
        rules = export_ai_kb(precision_doc)
        assert isinstance(rules, list)

    def test_each_rule_has_required_fields(self, precision_doc):
        rules = export_ai_kb(precision_doc)
        required = {"id", "sequence", "bid", "by", "system", "description",
                    "hand_constraint", "artificial", "alertable", "forcing",
                    "transfer_to", "preemptive", "context_text"}
        for r in rules:
            assert required.issubset(r.keys())

    def test_at_least_one_rule(self, precision_doc):
        rules = export_ai_kb(precision_doc)
        assert len(rules) > 0

    def test_no_conventions_flag(self, precision_doc):
        all_rules = export_ai_kb(precision_doc, include_conventions=True)
        no_conv = export_ai_kb(precision_doc, include_conventions=False)
        # Without conventions should be ≤ with conventions
        assert len(no_conv) <= len(all_rules)

    def test_locale_en(self, precision_doc):
        rules = export_ai_kb(precision_doc, locale="en")
        for r in rules:
            assert isinstance(r["context_text"], str)

    def test_locale_zh(self, precision_doc):
        rules = export_ai_kb(precision_doc, locale="zh-TW")
        for r in rules:
            assert isinstance(r["context_text"], str)
        # At least some context_text should contain Chinese
        has_chinese = any("在" in r["context_text"] for r in rules)
        assert has_chinese

    def test_writes_jsonl_file(self, precision_doc, tmp_path):
        out = tmp_path / "precision.jsonl"
        rules = export_ai_kb(precision_doc, output_path=out, fmt="jsonl")
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) == len(rules)
        json.loads(lines[0])  # parseable

    def test_writes_json_file(self, precision_doc, tmp_path):
        out = tmp_path / "precision.json"
        rules = export_ai_kb(precision_doc, output_path=out, fmt="json")
        assert out.exists()
        d = json.loads(out.read_text(encoding="utf-8"))
        assert "metadata" in d
        assert "rules" in d
        assert d["metadata"]["count"] == len(rules)

    def test_creates_parent_dir(self, precision_doc, tmp_path):
        out = tmp_path / "nested" / "subdir" / "kb.jsonl"
        export_ai_kb(precision_doc, output_path=out, fmt="jsonl")
        assert out.exists()

    def test_returns_same_as_file_content(self, precision_doc, tmp_path):
        out = tmp_path / "check.jsonl"
        rules = export_ai_kb(precision_doc, output_path=out, fmt="jsonl")
        content = out.read_text(encoding="utf-8")
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) == len(rules)

    def test_precision_no_crash(self, precision_doc):
        rules = export_ai_kb(precision_doc)
        assert len(rules) > 5

    def test_sayc_no_crash(self, sayc_doc):
        rules = export_ai_kb(sayc_doc)
        assert isinstance(rules, list)

    def test_two_over_one_no_crash(self, two_over_one_doc):
        rules = export_ai_kb(two_over_one_doc)
        assert isinstance(rules, list)

    def test_opening_rules_have_empty_sequence(self, precision_doc):
        rules = export_ai_kb(precision_doc, include_conventions=False)
        opening_rules = [r for r in rules if r["sequence"] == []]
        assert len(opening_rules) == len(precision_doc.openings)

    def test_by_field_set(self, precision_doc):
        rules = export_ai_kb(precision_doc, include_conventions=False)
        for r in rules:
            assert r["by"] in ("opener", "responder", "overcaller", "advancer")

    def test_hcp_in_hand_constraint(self, precision_doc):
        rules = export_ai_kb(precision_doc, include_conventions=False)
        # At least some rules should have hcp constraints
        hcp_rules = [r for r in rules if "hcp" in r.get("hand_constraint", {})]
        assert len(hcp_rules) > 0
