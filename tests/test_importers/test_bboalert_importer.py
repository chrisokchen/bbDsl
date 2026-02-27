"""Tests for bbdsl.importers.bboalert_importer (+ round-trip)."""

from pathlib import Path

import pytest

from bbdsl.importers.bboalert_importer import (
    _build_tree_from_rows,
    import_bboalert,
    parse_bboalert_text,
)


@pytest.fixture
def bboalert_samples_dir() -> Path:
    return Path(__file__).parent.parent / "fixtures" / "bboalert_samples"


@pytest.fixture
def examples_dir() -> Path:
    return Path(__file__).parent.parent.parent / "examples"


# ---------------------------------------------------------------------------
# TestParseBboalertText
# ---------------------------------------------------------------------------

class TestParseBboalertText:
    def test_basic_row(self):
        text = ',1C,16+ HCP; artificial'
        rows = parse_bboalert_text(text)
        assert len(rows) == 1
        assert rows[0] == ('', '1C', '16+ HCP; artificial')

    def test_response_row(self):
        text = '1C,1D,0-7 HCP; artificial'
        rows = parse_bboalert_text(text)
        assert rows[0] == ('1C', '1D', '0-7 HCP; artificial')

    def test_comment_lines_skipped(self):
        text = '# This is a comment\n,1C,16+ HCP\n'
        rows = parse_bboalert_text(text)
        assert len(rows) == 1

    def test_blank_lines_skipped(self):
        text = '\n\n,1C,16+ HCP\n\n,1D,11-15 HCP\n'
        rows = parse_bboalert_text(text)
        assert len(rows) == 2

    def test_call_uppercased(self):
        text = ',1nt,15-17 HCP'
        rows = parse_bboalert_text(text)
        assert rows[0][1] == '1NT'

    def test_missing_explanation(self):
        text = ',1C,'
        rows = parse_bboalert_text(text)
        assert rows[0] == ('', '1C', '')

    def test_multiple_rows(self):
        text = ',1C,strong\n1C,1D,negative\n1C,1H,positive\n'
        rows = parse_bboalert_text(text)
        assert len(rows) == 3

    def test_chained_context(self):
        text = '1C-1D,1H,relay continuation'
        rows = parse_bboalert_text(text)
        assert rows[0] == ('1C-1D', '1H', 'relay continuation')


# ---------------------------------------------------------------------------
# TestBuildTree
# ---------------------------------------------------------------------------

class TestBuildTree:
    def test_root_nodes_only(self):
        rows = [('', '1C', 'strong'), ('', '1D', 'natural')]
        roots = _build_tree_from_rows(rows)
        assert len(roots) == 2

    def test_response_attached_to_parent(self):
        rows = [
            ('', '1C', '16+ HCP'),
            ('1C', '1D', '0-7 HCP'),
        ]
        roots = _build_tree_from_rows(rows)
        assert len(roots) == 1
        assert 'responses' in roots[0]
        assert roots[0]['responses'][0]['bid'] == '1D'

    def test_multiple_responses(self):
        rows = [
            ('', '1C', '16+ HCP'),
            ('1C', '1D', '0-7 HCP'),
            ('1C', '1H', '8+ HCP'),
        ]
        roots = _build_tree_from_rows(rows)
        assert len(roots[0]['responses']) == 2

    def test_deep_nesting(self):
        rows = [
            ('', '1C', '16+ HCP'),
            ('1C', '1D', '0-7 HCP'),
            ('1C-1D', '1H', 'relay'),
        ]
        roots = _build_tree_from_rows(rows)
        assert 'responses' in roots[0]
        resp = roots[0]['responses'][0]
        assert 'responses' in resp
        assert resp['responses'][0]['bid'] == '1H'

    def test_unresolved_node_created(self):
        rows = [('', '1C', 'mysterious opening')]
        roots = _build_tree_from_rows(rows)
        assert roots[0].get('is_unresolved') is True


# ---------------------------------------------------------------------------
# TestImportBboalert
# ---------------------------------------------------------------------------

class TestImportBboalert:
    def test_simple_precision_import(self, bboalert_samples_dir):
        path = bboalert_samples_dir / 'simple_precision.bboalert'
        doc, n_unresolved = import_bboalert(path, system_name='Precision')
        assert doc['bbdsl'] == '0.3'
        # Some rows have hand constraints (HCP) → resolved
        openings = doc['openings']
        assert len(openings) >= 6

    def test_unresolved_counted(self, bboalert_samples_dir):
        path = bboalert_samples_dir / 'simple_precision.bboalert'
        doc, n_unresolved = import_bboalert(path)
        # "Stayman" description has no HCP → unresolved
        assert n_unresolved >= 1

    def test_system_name_set(self, bboalert_samples_dir):
        path = bboalert_samples_dir / 'simple_precision.bboalert'
        doc, _ = import_bboalert(path, system_name='My System')
        assert doc['system']['name']['en'] == 'My System'

    def test_output_file_written(self, bboalert_samples_dir, tmp_path):
        path = bboalert_samples_dir / 'simple_precision.bboalert'
        out = tmp_path / 'out.bbdsl.yaml'
        import_bboalert(path, output_path=out)
        assert out.exists()
        content = out.read_text(encoding='utf-8')
        assert 'bbdsl' in content

    def test_unresolved_warning_in_file(self, bboalert_samples_dir, tmp_path):
        path = bboalert_samples_dir / 'simple_precision.bboalert'
        out = tmp_path / 'out.bbdsl.yaml'
        doc, n = import_bboalert(path, output_path=out)
        if n > 0:
            content = out.read_text(encoding='utf-8')
            assert 'WARNING' in content or 'unresolved' in content.lower()


# ---------------------------------------------------------------------------
# TestRoundTrip (export → import)
# ---------------------------------------------------------------------------

class TestRoundTrip:
    """Export precision.bbdsl.yaml to BBOalert, then import back."""

    def test_roundtrip_preserves_opening_count(self, examples_dir, tmp_path):
        from bbdsl.core.loader import load_document
        from bbdsl.exporters.bboalert_exporter import export_bboalert

        doc = load_document(examples_dir / 'precision.bbdsl.yaml')
        bboalert_path = tmp_path / 'precision.bboalert'
        export_bboalert(doc, output_path=bboalert_path, locale='en', include_comments=False)

        reimported, _ = import_bboalert(bboalert_path, system_name='Precision')
        # Should have same number of root openings
        assert len(reimported['openings']) == len(doc.openings)

    def test_roundtrip_preserves_bid_names(self, examples_dir, tmp_path):
        from bbdsl.core.loader import load_document
        from bbdsl.exporters.bboalert_exporter import export_bboalert

        doc = load_document(examples_dir / 'precision.bbdsl.yaml')
        bboalert_path = tmp_path / 'precision.bboalert'
        export_bboalert(doc, output_path=bboalert_path, locale='en', include_comments=False)

        reimported, _ = import_bboalert(bboalert_path)
        opening_bids = {o['bid'] for o in reimported['openings']}
        original_bids = {o.bid for o in doc.openings}
        assert opening_bids == original_bids

    def test_roundtrip_exported_file_is_valid_csv(self, examples_dir, tmp_path):
        import csv
        from bbdsl.core.loader import load_document
        from bbdsl.exporters.bboalert_exporter import export_bboalert

        doc = load_document(examples_dir / 'precision.bbdsl.yaml')
        bboalert_path = tmp_path / 'precision.bboalert'
        export_bboalert(doc, output_path=bboalert_path, include_comments=False)

        with open(bboalert_path, encoding='utf-8') as f:
            rows = list(csv.reader(f))
        assert all(len(r) >= 2 for r in rows)
