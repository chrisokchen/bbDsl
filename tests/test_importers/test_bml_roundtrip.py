"""BBDSL → BML → BBDSL semantic round-trip fidelity (review finding F-5).

Structural round-trip (bid tree shape) was already covered elsewhere; what was
missing was a check that the *semantics* survive the trip. This is the test
that would have caught F-2 (natural heart bids imported as artificial).
"""

from pathlib import Path

import pytest

from bbdsl.core.loader import load_document
from bbdsl.exporters.bml_exporter import export_bml
from bbdsl.importers.bml_importer import import_bml

EXAMPLES = Path(__file__).parent.parent.parent / "examples"
EXAMPLE_FILES = ["precision.bbdsl.yaml", "sayc.bbdsl.yaml", "two_over_one.bbdsl.yaml"]


@pytest.fixture(params=EXAMPLE_FILES)
def round_tripped(request, tmp_path):
    """Export each example to BML, re-import it, return (original, reimported)."""
    doc = load_document(EXAMPLES / request.param)
    bml_path = tmp_path / "rt.bml"
    bml_path.write_text(export_bml(doc), encoding="utf-8")
    reimported, _ = import_bml(bml_path, system_name="RoundTrip")
    return doc, reimported


def _openings_by_bid(reimported: dict) -> dict:
    return {o.get("bid"): o for o in reimported.get("openings", [])}


class TestBmlRoundTripFidelity:

    def test_all_openings_survive(self, round_tripped):
        doc, reimported = round_tripped
        assert set(_openings_by_bid(reimported)) == {o.bid for o in doc.openings}

    def test_hcp_ranges_preserved(self, round_tripped):
        doc, reimported = round_tripped
        rt = _openings_by_bid(reimported)
        for opening in doc.openings:
            orig_hcp = opening.meaning.hand.hcp
            if orig_hcp is None:
                continue
            rt_hcp = ((rt[opening.bid].get("meaning") or {}).get("hand") or {}).get("hcp")
            assert rt_hcp is not None, f"{opening.bid}: HCP range lost"
            assert rt_hcp.get("min") == orig_hcp.min
            assert rt_hcp.get("max") == orig_hcp.max

    def test_artificial_flag_not_invented(self, round_tripped):
        """A natural bid must never come back artificial (regression: F-2)."""
        doc, reimported = round_tripped
        rt = _openings_by_bid(reimported)
        for opening in doc.openings:
            rt_meaning = rt[opening.bid].get("meaning") or {}
            assert bool(rt_meaning.get("artificial")) == opening.meaning.artificial, (
                f"{opening.bid}: artificial flag flipped in round-trip"
            )

    def test_alertable_flag_not_invented(self, round_tripped):
        doc, reimported = round_tripped
        rt = _openings_by_bid(reimported)
        for opening in doc.openings:
            rt_meaning = rt[opening.bid].get("meaning") or {}
            assert bool(rt_meaning.get("alertable")) == opening.meaning.alertable, (
                f"{opening.bid}: alertable flag flipped in round-trip"
            )

    def test_forcing_level_preserved(self, round_tripped):
        doc, reimported = round_tripped
        rt = _openings_by_bid(reimported)
        for opening in doc.openings:
            orig = opening.meaning.forcing
            rt_forcing = (rt[opening.bid].get("meaning") or {}).get("forcing")
            expected = orig.value if orig is not None else None
            assert rt_forcing == expected, f"{opening.bid}: forcing level changed"

    def test_response_counts_preserved(self, round_tripped):
        doc, reimported = round_tripped
        rt = _openings_by_bid(reimported)
        for opening in doc.openings:
            expected = len(opening.responses or [])
            actual = len(rt[opening.bid].get("responses") or [])
            assert actual == expected, f"{opening.bid}: {expected} responses → {actual}"
