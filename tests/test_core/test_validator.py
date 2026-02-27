"""Tests for bbdsl.core.validator."""

import pytest

from bbdsl.core.loader import load_document
from bbdsl.core.validator import Validator


class TestStubRules:
    """val-001 and val-003 are now fully implemented (Phase 2)."""

    def test_val_001_is_warning_severity(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_001()
        assert r.rule_id == "val-001"
        assert r.severity == "warning"

    def test_val_003_is_warning_severity(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_003()
        assert r.rule_id == "val-003"
        assert r.severity == "warning"


class TestVal002NoOverlap:
    def test_precision_no_overlap(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_002()
        assert r.passed is True

    def test_overlap_detected(self, fixtures_dir):
        doc = load_document(fixtures_dir / "invalid" / "overlap-hcp.yaml")
        v = Validator(doc)
        r = v._check_val_002()
        assert r.passed is False
        assert r.severity == "error"
        assert len(r.details) >= 1

    def test_no_overlap_different_suits(self, fixtures_dir):
        """1H (hearts>=5) and 1S (spades>=5) with overlapping HCP should NOT overlap."""
        doc = load_document(fixtures_dir / "valid" / "minimal.yaml")
        v = Validator(doc)
        r = v._check_val_002()
        assert r.passed is True


class TestVal004ConventionRefExists:
    def test_precision_refs_ok(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_004()
        assert r.passed is True

    def test_missing_ref(self, fixtures_dir):
        doc = load_document(fixtures_dir / "invalid" / "missing-convention-ref.yaml")
        v = Validator(doc)
        r = v._check_val_004()
        assert r.passed is False
        assert len(r.details) >= 1


class TestVal005ConventionConflicts:
    def test_precision_no_conflicts(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_005()
        assert r.passed is True


class TestVal006PatternRefExists:
    def test_precision_patterns_ok(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_006()
        assert r.passed is True

    def test_missing_pattern(self, fixtures_dir):
        doc = load_document(fixtures_dir / "invalid" / "missing-pattern-ref.yaml")
        v = Validator(doc)
        r = v._check_val_006()
        assert r.passed is False
        assert any("nonexistent_pattern" in str(d) for d in r.details)


class TestVal007ForcingConsistency:
    def test_precision_forcing_ok(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_007()
        assert r.passed is True

    def test_forcing_violation(self, fixtures_dir):
        doc = load_document(fixtures_dir / "invalid" / "forcing-violation.yaml")
        v = Validator(doc)
        r = v._check_val_007()
        assert r.passed is False
        assert r.severity == "error"
        assert any("signoff" in str(d) for d in r.details)


class TestVal008AlertableCheck:
    def test_precision_alertable_ok(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_008()
        assert r.passed is True

    def test_artificial_not_alertable(self, fixtures_dir):
        doc = load_document(fixtures_dir / "invalid" / "artificial-not-alertable.yaml")
        v = Validator(doc)
        r = v._check_val_008()
        assert r.passed is False
        assert r.severity == "warning"


class TestVal011ConventionIdFormat:
    def test_precision_ids_ok(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_011()
        assert r.passed is True


class TestVal012ShapeFormat:
    def test_precision_shapes_ok(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_012()
        assert r.passed is True

    def test_bad_shape_format(self, fixtures_dir):
        doc = load_document(fixtures_dir / "invalid" / "bad-shape-format.yaml")
        v = Validator(doc)
        r = v._check_val_012()
        assert r.passed is False
        assert len(r.details) >= 2  # both wrong_generic and wrong_exact


class TestValidateAll:
    def test_precision_full_validation(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        report = v.validate_all()
        assert report.error_count == 0
        assert len(report.results) == 14  # 14 rules total

    def test_validate_with_filter(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        report = v.validate_all(rule_ids=["val-002", "val-008"])
        assert len(report.results) == 2

    def test_report_document_name(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        report = v.validate_all()
        assert "Precision" in report.document_name


class TestVal013PriorityUnique:
    def test_precision_no_duplicate_priorities(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_013()
        assert r.rule_id == "val-013"
        assert r.passed is True

    def test_duplicate_priority_detected(self, fixtures_dir):
        doc = load_document(fixtures_dir / "invalid" / "priority-duplicate.yaml")
        v = Validator(doc)
        r = v._check_val_013()
        assert r.passed is False
        assert r.severity == "error"
        assert len(r.details) >= 1
        assert r.details[0]["priority"] == 10

    def test_valid_with_selection_rules_no_duplicate(self, fixtures_dir):
        doc = load_document(fixtures_dir / "valid" / "with-selection-rules.yaml")
        v = Validator(doc)
        r = v._check_val_013()
        assert r.passed is True

    def test_no_priority_fields_passes(self, fixtures_dir):
        doc = load_document(fixtures_dir / "valid" / "minimal.yaml")
        v = Validator(doc)
        r = v._check_val_013()
        assert r.passed is True


class TestVal014SelectionRulesExhaustive:
    def test_no_selection_rules_passes(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_014()
        assert r.rule_id == "val-014"
        assert r.passed is True
        assert "skipped" in r.message

    def test_with_catchall_passes(self, fixtures_dir):
        doc = load_document(fixtures_dir / "valid" / "with-selection-rules.yaml")
        v = Validator(doc)
        r = v._check_val_014()
        assert r.passed is True

    def test_missing_catchall_fails(self, fixtures_dir):
        doc = load_document(fixtures_dir / "invalid" / "no-catchall-rules.yaml")
        v = Validator(doc)
        r = v._check_val_014()
        assert r.passed is False
        assert r.severity == "error"
        assert "catch-all" in r.message


# ---------------------------------------------------------------------------
# TestVal001HcpCoverage (upgraded from stub)
# ---------------------------------------------------------------------------

class TestVal001HcpCoverage:
    def test_precision_passes(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_001()
        assert r.rule_id == "val-001"
        assert r.severity == "warning"
        # Precision covers 5-37 (weak hands 0-4 are pass, expected gap)
        assert r.passed is True

    def test_sayc_passes(self, examples_dir):
        doc = load_document(examples_dir / "sayc.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_001()
        assert r.passed is True

    def test_two_over_one_passes(self, examples_dir):
        doc = load_document(examples_dir / "two_over_one.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_001()
        assert r.passed is True

    def test_single_hcp_constrained_opening_warns_on_gap(self, fixtures_dir):
        """minimal.yaml has 1C with hcp {min:16}, so 10-15 are uncovered → warning."""
        doc = load_document(fixtures_dir / "valid" / "minimal.yaml")
        v = Validator(doc)
        r = v._check_val_001()
        # minimal has only 1C (16+ HCP), so 10-15 are uncovered → warning
        assert r.severity == "warning"
        assert r.passed is False  # gap detected above 9 HCP


# ---------------------------------------------------------------------------
# TestVal003ResponseComplete (upgraded from stub)
# ---------------------------------------------------------------------------

class TestVal003ResponseComplete:
    def test_precision_passes(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_003()
        assert r.rule_id == "val-003"
        assert r.passed is True

    def test_sayc_passes(self, examples_dir):
        doc = load_document(examples_dir / "sayc.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_003()
        assert r.passed is True

    def test_minimal_no_responses_warns(self, fixtures_dir):
        """minimal.yaml only has 1C with no responses → warning."""
        doc = load_document(fixtures_dir / "valid" / "minimal.yaml")
        v = Validator(doc)
        r = v._check_val_003()
        assert r.rule_id == "val-003"
        assert r.severity == "warning"
        assert r.passed is False
        assert len(r.details) >= 1
        assert r.details[0]["bid"] == "1C"

    def test_message_mentions_count(self, fixtures_dir):
        doc = load_document(fixtures_dir / "valid" / "minimal.yaml")
        v = Validator(doc)
        r = v._check_val_003()
        assert "1" in r.message  # at least 1 opening without responses


# ---------------------------------------------------------------------------
# TestVal009SeatVulNoConflict
# ---------------------------------------------------------------------------

class TestVal009SeatVulNoConflict:
    def test_precision_passes(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_009()
        assert r.rule_id == "val-009"
        assert r.passed is True

    def test_sayc_passes(self, examples_dir):
        doc = load_document(examples_dir / "sayc.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_009()
        assert r.passed is True

    def test_no_overrides_passes(self, fixtures_dir):
        doc = load_document(fixtures_dir / "valid" / "minimal.yaml")
        v = Validator(doc)
        r = v._check_val_009()
        assert r.passed is True

    def test_duplicate_context_override_detected(self, fixtures_dir):
        doc = load_document(fixtures_dir / "invalid" / "seat-vul-conflict.yaml")
        v = Validator(doc)
        r = v._check_val_009()
        assert r.passed is False
        assert r.severity == "error"
        assert len(r.details) >= 1


# ---------------------------------------------------------------------------
# TestVal010ForeachExpansionConflict
# ---------------------------------------------------------------------------

class TestVal010ForeachExpansionConflict:
    def test_precision_passes(self, examples_dir):
        doc = load_document(examples_dir / "precision.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_010()
        assert r.rule_id == "val-010"
        assert r.passed is True

    def test_sayc_passes(self, examples_dir):
        doc = load_document(examples_dir / "sayc.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_010()
        assert r.passed is True

    def test_two_over_one_passes(self, examples_dir):
        doc = load_document(examples_dir / "two_over_one.bbdsl.yaml")
        v = Validator(doc)
        r = v._check_val_010()
        assert r.passed is True

    def test_foreach_expander_no_conflicts(self, fixtures_dir):
        doc = load_document(fixtures_dir / "valid" / "with-foreach.yaml")
        v = Validator(doc)
        r = v._check_val_010()
        assert r.passed is True

    def test_foreach_expansion_conflict_detected(self, fixtures_dir):
        doc = load_document(fixtures_dir / "invalid" / "foreach-conflict.yaml")
        v = Validator(doc)
        r = v._check_val_010()
        assert r.passed is False
        assert r.severity == "error"
        assert len(r.details) >= 1


# ---------------------------------------------------------------------------
# Integration tests: all 3 systems × 14 rules
# ---------------------------------------------------------------------------

class TestIntegrationAllSystems:
    @pytest.mark.parametrize("system_yaml", [
        "precision.bbdsl.yaml",
        "sayc.bbdsl.yaml",
        "two_over_one.bbdsl.yaml",
    ])
    def test_all_14_rules_pass(self, examples_dir, system_yaml):
        doc = load_document(examples_dir / system_yaml)
        v = Validator(doc)
        report = v.validate_all()
        assert len(report.results) == 14
        assert report.error_count == 0, (
            f"{system_yaml} has {report.error_count} error(s): "
            + str([r for r in report.results if not r.passed and r.severity == 'error'])
        )

    @pytest.mark.parametrize("system_yaml", [
        "precision.bbdsl.yaml",
        "sayc.bbdsl.yaml",
        "two_over_one.bbdsl.yaml",
    ])
    def test_validate_filter_works(self, examples_dir, system_yaml):
        doc = load_document(examples_dir / system_yaml)
        v = Validator(doc)
        report = v.validate_all(rule_ids=["val-002", "val-004", "val-009", "val-010"])
        assert len(report.results) == 4
        assert report.error_count == 0
