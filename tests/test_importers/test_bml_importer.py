"""Tests for bbdsl.importers.bml_importer."""

from pathlib import Path

import pytest

from bbdsl.importers.bml_importer import (
    _count_unresolved,
    bml_nodes_to_document_dict,
    extract_semantics,
    import_bml,
    parse_bml_text,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def bml_samples_dir() -> Path:
    return Path(__file__).parent.parent / "fixtures" / "bml_samples"


# ---------------------------------------------------------------------------
# TestParseBmlText
# ---------------------------------------------------------------------------

class TestParseBmlText:
    def test_single_opening(self):
        text = "1C  16+ HCP, art"
        roots = parse_bml_text(text)
        assert len(roots) == 1
        assert roots[0].bid == "1C"
        assert roots[0].description == "16+ HCP, art"
        assert roots[0].depth == 0

    def test_children_attached(self):
        text = (
            "1C  16+ HCP\n"
            "  1D  0-7 HCP\n"
            "  1H  8+ HCP\n"
        )
        roots = parse_bml_text(text)
        assert len(roots) == 1
        assert len(roots[0].children) == 2
        assert roots[0].children[0].bid == "1D"

    def test_multiple_openings(self):
        text = (
            "1C  16+ HCP\n"
            "1D  11-15 HCP\n"
            "1NT 15-17 HCP, bal\n"
        )
        roots = parse_bml_text(text)
        assert len(roots) == 3

    def test_comments_ignored(self):
        text = (
            "# This is a comment\n"
            "1C  16+ HCP\n"
            "# Another comment\n"
        )
        roots = parse_bml_text(text)
        assert len(roots) == 1

    def test_blank_lines_ignored(self):
        text = "\n\n1C  16+ HCP\n\n\n1D  11-15 HCP\n"
        roots = parse_bml_text(text)
        assert len(roots) == 2

    def test_deep_nesting(self):
        text = (
            "1C  16+ HCP\n"
            "  1D  waiting\n"
            "    1H  8+ HCP, 5+ hearts\n"
        )
        roots = parse_bml_text(text)
        assert len(roots) == 1
        child = roots[0].children[0]
        assert child.bid == "1D"
        assert len(child.children) == 1
        assert child.children[0].bid == "1H"

    def test_bid_uppercase_normalised(self):
        text = "1c  16+ HCP"
        roots = parse_bml_text(text)
        assert roots[0].bid == "1C"

    def test_notrump_bid(self):
        text = "1NT 15-17 HCP, bal"
        roots = parse_bml_text(text)
        assert roots[0].bid == "1NT"

    def test_four_space_indent(self):
        text = (
            "1C  16+ HCP\n"
            "    1D  0-7 HCP\n"
        )
        roots = parse_bml_text(text)
        assert len(roots[0].children) == 1
        assert roots[0].children[0].bid == "1D"


# ---------------------------------------------------------------------------
# TestExtractSemantics
# ---------------------------------------------------------------------------

class TestExtractSemantics:
    def test_hcp_range(self):
        r = extract_semantics("11-15 HCP, 5+ hearts")
        assert r['hand']['hcp'] == {'min': 11, 'max': 15}

    def test_hcp_min_only(self):
        r = extract_semantics("16+ HCP, art")
        assert r['hand']['hcp'] == {'min': 16}

    def test_suit_word(self):
        r = extract_semantics("8+ HCP, 5+ hearts, GF")
        assert r['hand']['hearts'] == {'min': 5}

    def test_suit_char(self):
        r = extract_semantics("8+ HCP, 4+s")
        assert r['hand']['spades'] == {'min': 4}

    def test_balanced_shape(self):
        r = extract_semantics("15-17 HCP, bal")
        assert r['hand']['shape'] == {'ref': 'balanced'}

    def test_semi_balanced_shape(self):
        r = extract_semantics("12-14 HCP, semi-bal")
        assert r['hand']['shape'] == {'ref': 'semi_balanced'}

    def test_game_forcing(self):
        r = extract_semantics("8+ HCP, 5+ hearts, GF")
        assert r['forcing'] == 'game'

    def test_one_round_forcing(self):
        r = extract_semantics("8+ HCP, forcing")
        assert r['forcing'] == 'one_round'

    def test_signoff(self):
        r = extract_semantics("6-9 HCP, sign-off")
        assert r['forcing'] == 'signoff'

    def test_invitational(self):
        r = extract_semantics("11-12 HCP, inv")
        assert r['forcing'] == 'invitational'

    def test_artificial(self):
        r = extract_semantics("0-7 HCP, art, alert")
        assert r['artificial'] is True
        assert r['alertable'] is True

    def test_artificial_auto_alertable(self):
        """Artificial bids default to alertable=True."""
        r = extract_semantics("0-7 HCP, art")
        assert r['artificial'] is True
        assert r.get('alertable') is True

    def test_preemptive(self):
        r = extract_semantics("5-10 HCP, 6+ hearts, preemptive")
        assert r['preemptive'] is True

    def test_resolved_true_when_hand_found(self):
        r = extract_semantics("11-15 HCP, 5+ hearts")
        assert r['_resolved'] is True

    def test_unresolved_when_no_hand(self):
        r = extract_semantics("Strong opening bid")
        assert r['_resolved'] is False
        assert r['_reason']

    def test_empty_description(self):
        r = extract_semantics("")
        assert r['_resolved'] is False

    def test_multiple_suits(self):
        r = extract_semantics("8+ HCP, 4+ hearts, 4+ spades")
        assert r['hand']['hearts'] == {'min': 4}
        assert r['hand']['spades'] == {'min': 4}


# ---------------------------------------------------------------------------
# TestBmlNodesToDocumentDict
# ---------------------------------------------------------------------------

class TestBmlNodesToDocumentDict:
    def test_basic_structure(self):
        roots = parse_bml_text("1C  16+ HCP, art, alert")
        doc = bml_nodes_to_document_dict(roots, "Test System")
        assert doc['bbdsl'] == '0.3'
        assert doc['system']['name'] == {'en': 'Test System'}
        assert len(doc['openings']) == 1

    def test_resolved_node_has_meaning(self):
        roots = parse_bml_text("1C  16+ HCP, art, alert")
        doc = bml_nodes_to_document_dict(roots)
        opening = doc['openings'][0]
        assert opening['bid'] == '1C'
        assert 'meaning' in opening
        assert opening['meaning']['hand']['hcp'] == {'min': 16}
        assert opening['meaning']['artificial'] is True

    def test_unresolved_node_structure(self):
        roots = parse_bml_text("1C  Strong club, unclear")
        doc = bml_nodes_to_document_dict(roots)
        opening = doc['openings'][0]
        assert opening.get('is_unresolved') is True
        assert 'bml_original' in opening
        assert 'reason' in opening
        assert 'Strong club' in opening['bml_original']

    def test_responses_nested(self):
        text = "1C  16+ HCP\n  1D  0-7 HCP, art\n"
        roots = parse_bml_text(text)
        doc = bml_nodes_to_document_dict(roots)
        opening = doc['openings'][0]
        assert 'responses' in opening
        assert opening['responses'][0]['bid'] == '1D'


# ---------------------------------------------------------------------------
# TestCountUnresolved
# ---------------------------------------------------------------------------

class TestCountUnresolved:
    def test_none_unresolved(self):
        nodes = [{'bid': '1C', 'meaning': {}}]
        assert _count_unresolved(nodes) == 0

    def test_one_unresolved(self):
        nodes = [{'bid': '1C', 'is_unresolved': True}]
        assert _count_unresolved(nodes) == 1

    def test_nested_unresolved(self):
        nodes = [
            {
                'bid': '1C',
                'meaning': {},
                'responses': [
                    {'bid': '1D', 'is_unresolved': True},
                    {'bid': '1H', 'meaning': {}},
                ],
            }
        ]
        assert _count_unresolved(nodes) == 1


# ---------------------------------------------------------------------------
# TestImportBml (integration)
# ---------------------------------------------------------------------------

class TestImportBml:
    def test_simple_precision_import(self, bml_samples_dir):
        path = bml_samples_dir / "simple_precision.bml"
        doc, n_unresolved = import_bml(path)
        assert doc['bbdsl'] == '0.3'
        assert n_unresolved == 0  # all descriptions have HCP

    def test_unresolvable_import(self, bml_samples_dir):
        path = bml_samples_dir / "unresolvable.bml"
        doc, n_unresolved = import_bml(path, system_name="Unresolvable Test")
        assert n_unresolved >= 2  # "Strong club", "Negative response" have no HCP

    def test_sayc_opening_import(self, bml_samples_dir):
        path = bml_samples_dir / "sayc_opening.bml"
        doc, n_unresolved = import_bml(path, system_name="SAYC")
        openings = doc['openings']
        assert len(openings) >= 8  # at least 8 opening bids
        # 1NT opening should be present
        nt_opening = next((o for o in openings if o.get('bid') == '1NT'), None)
        assert nt_opening is not None

    def test_system_name_used(self, bml_samples_dir):
        path = bml_samples_dir / "simple_precision.bml"
        doc, _ = import_bml(path, system_name="My Precision")
        assert doc['system']['name']['en'] == 'My Precision'

    def test_default_system_name_from_filename(self, bml_samples_dir):
        path = bml_samples_dir / "simple_precision.bml"
        doc, _ = import_bml(path)
        # Name derived from filename
        assert 'Simple Precision' in doc['system']['name']['en']

    def test_output_file_written(self, bml_samples_dir, tmp_path):
        path = bml_samples_dir / "simple_precision.bml"
        out = tmp_path / "out.bbdsl.yaml"
        doc, _ = import_bml(path, output_path=out)
        assert out.exists()
        content = out.read_text(encoding='utf-8')
        assert 'bbdsl' in content
        assert '1C' in content

    def test_unresolved_warning_in_output(self, bml_samples_dir, tmp_path):
        path = bml_samples_dir / "unresolvable.bml"
        out = tmp_path / "out.bbdsl.yaml"
        doc, n = import_bml(path, output_path=out)
        assert n > 0
        content = out.read_text(encoding='utf-8')
        assert 'WARNING' in content or 'unresolved' in content.lower()
