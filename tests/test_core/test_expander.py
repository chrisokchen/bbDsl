"""Tests for bbdsl.core.expander."""

import pytest

from bbdsl.core.expander import (
    DEFAULT_SUIT_GROUPS,
    SUIT_META,
    _build_replacements,
    _expand_node,
    _replace_in_obj,
    expand_document,
    count_expanded,
)
from bbdsl.core.loader import load_document


class TestSuitMeta:
    def test_all_suits_present(self):
        assert set(SUIT_META.keys()) == {"C", "D", "H", "S"}

    def test_suit_properties(self):
        h = SUIT_META["H"]
        assert h["lower"] == "h"
        assert h["zh-TW"] == "紅心"
        assert h["en"] == "hearts"
        assert h["symbol"] == "♥"
        assert h["rank"] == 2
        assert h["color"] == "red"
        assert h["group"] == "major"
        assert h["other"] == "S"
        assert h["transfer_from"] == "D"

    def test_suit_groups(self):
        assert DEFAULT_SUIT_GROUPS["majors"] == ["H", "S"]
        assert DEFAULT_SUIT_GROUPS["minors"] == ["C", "D"]
        assert len(DEFAULT_SUIT_GROUPS["all"]) == 4


class TestBuildReplacements:
    def test_basic_replacements(self):
        r = _build_replacements("M", "H")
        assert r["${M}"] == "H"
        assert r["${M.lower}"] == "h"
        assert r["${M.en}"] == "hearts"
        assert r["${M.zh-TW}"] == "紅心"
        assert r["${M.symbol}"] == "♥"

    def test_transfer_from_none(self):
        r = _build_replacements("X", "C")
        assert "${X.transfer_from}" not in r  # None values excluded


class TestReplaceInObj:
    def test_replace_string(self):
        r = {"${M}": "H", "${M.en}": "hearts"}
        assert _replace_in_obj("1${M}", r) == "1H"
        assert _replace_in_obj("5+ ${M.en}", r) == "5+ hearts"

    def test_replace_in_dict(self):
        r = {"${M}": "S", "${M.en}": "spades"}
        obj = {"bid": "1${M}", "desc": {"en": "5+ ${M.en}"}}
        result = _replace_in_obj(obj, r)
        assert result["bid"] == "1S"
        assert result["desc"]["en"] == "5+ spades"

    def test_replace_in_list(self):
        r = {"${M}": "H"}
        obj = [{"bid": "1${M}"}, {"bid": "2${M}"}]
        result = _replace_in_obj(obj, r)
        assert result[0]["bid"] == "1H"
        assert result[1]["bid"] == "2H"

    def test_non_string_unchanged(self):
        r = {"${M}": "H"}
        assert _replace_in_obj(42, r) == 42
        assert _replace_in_obj(True, r) is True


class TestExpandNode:
    def test_no_foreach_passthrough(self):
        node = {"bid": "1C", "meaning": {"hand": {"hcp": {"min": 16}}}}
        result = _expand_node(node, DEFAULT_SUIT_GROUPS)
        assert len(result) == 1
        assert result[0]["bid"] == "1C"

    def test_expand_majors(self):
        node = {
            "bid": "1${M}",
            "foreach_suit": {"variable": "M", "over": "majors"},
            "meaning": {"description": {"en": "5+ ${M.en}"}},
        }
        result = _expand_node(node, DEFAULT_SUIT_GROUPS)
        assert len(result) == 2
        assert result[0]["bid"] == "1H"
        assert result[1]["bid"] == "1S"
        assert result[0]["meaning"]["description"]["en"] == "5+ hearts"
        assert result[1]["meaning"]["description"]["en"] == "5+ spades"
        assert "_expanded_from" in result[0]
        assert result[0]["_expanded_from"]["value"] == "H"
        assert "foreach_suit" not in result[0]

    def test_expand_all(self):
        node = {
            "bid": "3${M}",
            "foreach_suit": {"variable": "M", "over": "all"},
        }
        result = _expand_node(node, DEFAULT_SUIT_GROUPS)
        assert len(result) == 4
        bids = [n["bid"] for n in result]
        assert bids == ["3C", "3D", "3H", "3S"]

    def test_expand_with_responses(self):
        node = {
            "bid": "1${M}",
            "foreach_suit": {"variable": "M", "over": "majors"},
            "responses": [
                {"bid": "2${M}", "meaning": {"description": "raise"}},
            ],
        }
        result = _expand_node(node, DEFAULT_SUIT_GROUPS)
        assert result[0]["responses"][0]["bid"] == "2H"
        assert result[1]["responses"][0]["bid"] == "2S"

    def test_expand_zh_tw(self):
        node = {
            "bid": "1${M}",
            "foreach_suit": {"variable": "M", "over": "majors"},
            "meaning": {"description": {"zh-TW": "${M.zh-TW}開叫"}},
        }
        result = _expand_node(node, DEFAULT_SUIT_GROUPS)
        assert result[0]["meaning"]["description"]["zh-TW"] == "紅心開叫"
        assert result[1]["meaning"]["description"]["zh-TW"] == "黑桃開叫"

    def test_max_nesting_exceeded(self):
        node = {
            "bid": "1${M}",
            "foreach_suit": {"variable": "M", "over": "majors"},
            "responses": [{
                "bid": "2${N}",
                "foreach_suit": {"variable": "N", "over": "minors"},
                "responses": [{
                    "bid": "3${P}",
                    "foreach_suit": {"variable": "P", "over": "all"},
                }],
            }],
        }
        with pytest.raises(ValueError, match="nesting exceeds maximum"):
            _expand_node(node, DEFAULT_SUIT_GROUPS)

    def test_nested_two_levels(self):
        node = {
            "bid": "1${M}",
            "foreach_suit": {"variable": "M", "over": "majors"},
            "responses": [{
                "bid": "2${N}",
                "foreach_suit": {"variable": "N", "over": "minors"},
            }],
        }
        result = _expand_node(node, DEFAULT_SUIT_GROUPS)
        assert len(result) == 2  # 1H, 1S
        assert len(result[0]["responses"]) == 2  # 2C, 2D
        assert result[0]["responses"][0]["bid"] == "2C"
        assert result[0]["responses"][1]["bid"] == "2D"


class TestExpandDocument:
    def test_expand_precision(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        expanded = expand_document(doc)
        # Precision example has no foreach_suit, so no expansion
        assert count_expanded(expanded) == 0
        assert len(expanded["openings"]) == 9

    def test_expand_foreach_fixture(self, fixtures_dir):
        doc = load_document(fixtures_dir / "valid" / "with-foreach.yaml")
        expanded = expand_document(doc)
        # foreach over majors → 2 nodes
        assert len(expanded["openings"]) == 2
        assert expanded["openings"][0]["bid"] == "1H"
        assert expanded["openings"][1]["bid"] == "1S"
        assert count_expanded(expanded) == 2
