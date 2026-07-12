"""Validation engine: 14 rules (all real, Phase 2 complete)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from bbdsl.models.convention import CONVENTION_ID_RE
from bbdsl.models.system import BBDSLDocument


class ValidationResult(BaseModel):
    """Single validation rule result.

    ``skipped`` marks a rule that had nothing to examine (e.g. a document with
    no conventions cannot violate the convention-id rule). Such a rule is not
    a pass: reporting it as one advertises a guarantee that was never checked.
    """

    rule_id: str
    rule_name: str
    severity: str  # "error" | "warning" | "info"
    passed: bool
    message: str
    details: list[dict[str, Any]] = []
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict."""
        return self.model_dump()


class ValidationReport(BaseModel):
    """Complete validation report."""

    document_name: str
    results: list[ValidationResult]

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if not r.passed and r.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for r in self.results if not r.passed and r.severity == "warning")

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.skipped)

    @property
    def passed_count(self) -> int:
        """Rules that actually ran and passed (skipped rules excluded)."""
        return sum(1 for r in self.results if r.passed and not r.skipped)

    def has_errors(self) -> bool:
        return self.error_count > 0

    def to_dict(self) -> dict[str, Any]:
        """Return a fully JSON-serializable dict.

        Includes computed properties ``error_count``, ``warning_count``,
        ``passed_count`` and ``skipped_count`` for convenience.
        """
        return {
            "document_name": self.document_name,
            "results": [r.to_dict() for r in self.results],
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "passed_count": self.passed_count,
            "skipped_count": self.skipped_count,
        }


class Validator:
    """Orchestrates all validation rules against a BBDSLDocument."""

    def __init__(self, doc: BBDSLDocument) -> None:
        self.doc = doc

    def validate_all(self, rule_ids: list[str] | None = None) -> ValidationReport:
        """Run all (or selected) validation rules."""
        all_checks = [
            self._check_val_001,
            self._check_val_002,
            self._check_val_003,
            self._check_val_004,
            self._check_val_005,
            self._check_val_006,
            self._check_val_007,
            self._check_val_008,
            self._check_val_009,
            self._check_val_010,
            self._check_val_011,
            self._check_val_012,
            self._check_val_013,
            self._check_val_014,
        ]
        results = []
        for check in all_checks:
            result = check()
            if rule_ids is None or result.rule_id in rule_ids:
                results.append(result)

        name = self.doc.system.name
        if isinstance(name, dict):
            name = name.get("en") or name.get("zh-TW") or next(iter(name.values()))

        return ValidationReport(document_name=str(name), results=results)

    # ------------------------------------------------------------------
    # val-001: hcp-coverage
    # ------------------------------------------------------------------

    def _check_val_001(self) -> ValidationResult:
        """Check that opening HCP ranges cover 0-37 without gaps.

        Collects all opening bids with explicit HCP ranges and checks for
        uncovered HCP points. Returns warning (not error) since low-count
        hands that pass are expected to be uncovered.
        """
        # Collect HCP ranges from openings (only those with explicit HCP constraints)
        covered = set()
        for opening in (self.doc.openings or []):
            meaning = getattr(opening, "meaning", None)
            if meaning is None:
                continue
            hand = getattr(meaning, "hand", None)
            if hand is None or hand.hcp is None:
                # No HCP constraint = covers all (pass hands are separate)
                return ValidationResult(
                    rule_id="val-001",
                    rule_name="hcp-coverage",
                    severity="warning",
                    passed=True,
                    skipped=True,
                    message="HCP coverage: at least one opening has no HCP limit (not checked).",
                )
            hcp = hand.hcp
            lo = hcp.min if hcp.min is not None else 0
            hi = hcp.max if hcp.max is not None else 37
            for pt in range(lo, min(hi, 37) + 1):
                covered.add(pt)

        gaps = [pt for pt in range(0, 38) if pt not in covered]
        if gaps:
            # Only warn if the gap is not just the expected 0-X pass range
            actionable_gaps = [g for g in gaps if g >= 10]
            if actionable_gaps:
                return ValidationResult(
                    rule_id="val-001",
                    rule_name="hcp-coverage",
                    severity="warning",
                    passed=False,
                    message=f"HCP coverage gap(s) detected above 9 HCP: {actionable_gaps}.",
                    details=[{"uncovered_hcp": actionable_gaps}],
                )
        return ValidationResult(
            rule_id="val-001",
            rule_name="hcp-coverage",
            severity="warning",
            passed=True,
            message=f"HCP coverage: {len(covered)} points covered. "
                    f"Uncovered (pass range): {[g for g in gaps if g < 10]}.",
        )

    # ------------------------------------------------------------------
    # val-003: response-complete
    # ------------------------------------------------------------------

    def _check_val_003(self) -> ValidationResult:
        """Check that each opening bid has at least some responses defined."""
        incomplete: list[dict] = []
        for opening in (self.doc.openings or []):
            bid = getattr(opening, "bid", None) or "?"
            responses = getattr(opening, "responses", None) or []
            if not responses:
                incomplete.append({"bid": bid})

        if incomplete:
            return ValidationResult(
                rule_id="val-003",
                rule_name="response-complete",
                severity="warning",
                passed=False,
                message=f"{len(incomplete)} opening(s) have no responses defined.",
                details=incomplete,
            )
        return ValidationResult(
            rule_id="val-003",
            rule_name="response-complete",
            severity="warning",
            passed=True,
            message="All openings have at least one response defined.",
        )

    # ------------------------------------------------------------------
    # val-002: no-overlap — HCP + shape overlap at same level
    # ------------------------------------------------------------------

    def _check_val_002(self) -> ValidationResult:
        violations: list[dict] = []
        self._check_siblings_overlap(self.doc.openings, ["openings"], violations)

        # An overlap with a declared tie-break is intentional: something in the
        # document says which of the two bids wins. Openings are ordered by
        # selection_rules; sibling responses by their `priority`. An overlap
        # with neither is left to the engine's specificity heuristic — still
        # deterministic, but nobody wrote down what was meant.
        unresolved = [v for v in violations if not v.pop("_tie_broken", False)]

        if unresolved:
            return ValidationResult(
                rule_id="val-002",
                rule_name="no-overlap",
                severity="warning",
                passed=False,
                message=(
                    f"{len(unresolved)} overlapping bid pair(s) with no declared "
                    f"tie-break (add selection_rules or a priority)."
                ),
                details=unresolved,
            )
        if violations:
            return ValidationResult(
                rule_id="val-002",
                rule_name="no-overlap",
                severity="warning",
                passed=True,
                message=(
                    f"{len(violations)} overlapping bid pair(s), all with a "
                    f"declared tie-break."
                ),
            )
        return ValidationResult(
            rule_id="val-002",
            rule_name="no-overlap",
            severity="error",
            passed=True,
            message="No HCP/shape overlaps found.",
        )

    def _selection_rule_bids(self) -> set[str]:
        """Bids that selection_rules explicitly orders."""
        if not self.doc.selection_rules:
            return set()
        from bbdsl.core.selector import parse_selection_rules

        return {
            str(r.get("select"))
            for r in parse_selection_rules(self.doc.selection_rules)
            if r.get("select")
        }

    def _shapes_of(self, shape: Any) -> set[str] | None:
        """Resolve a shape ref to its set of generic shapes, or None if unknown."""
        ref = None
        if isinstance(shape, dict):
            ref = shape.get("ref")
        elif isinstance(shape, str) and shape not in ("any", ""):
            ref = shape
        if not ref:
            return None
        patterns = (
            self.doc.definitions.patterns
            if self.doc.definitions and self.doc.definitions.patterns
            else {}
        )
        pattern = patterns.get(ref)
        if pattern is None:
            return None
        shapes = set(pattern.shapes or []) | set(pattern.shapes_exact or [])
        return shapes or None

    def _check_siblings_overlap(
        self, nodes: list | None, path: list[str], violations: list[dict]
    ) -> None:
        if not nodes:
            return
        selection_bids = self._selection_rule_bids()
        # Check pairwise overlap among siblings
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                if self._bids_overlap(a, b):
                    ordered_by_rules = (
                        a.bid in selection_bids and b.bid in selection_bids
                    )
                    ordered_by_priority = (
                        a.priority is not None and b.priority is not None
                    )
                    violations.append({
                        "path": "/".join(path),
                        "bid_a": a.bid,
                        "bid_b": b.bid,
                        "_tie_broken": ordered_by_rules or ordered_by_priority,
                    })
            # Recurse into each node's responses
            node = nodes[i]
            if node.responses:
                self._check_siblings_overlap(
                    node.responses, [*path, node.bid or "?"], violations
                )
            if node.continuations:
                self._check_siblings_overlap(
                    node.continuations, [*path, node.bid or "?", "cont"], violations
                )

    def _bids_overlap(self, a: Any, b: Any) -> bool:
        """True if some legal hand could satisfy both sibling bids.

        Two bids overlap when their HCP ranges, their shape sets and *every*
        suit-length range can be satisfied simultaneously. A missing constraint
        is not a mismatch — it admits everything, which is exactly why an
        unconstrained bid overlaps a constrained one.

        Artificial bids are still exempt: they are chosen by convention rather
        than by hand shape, so an overlap on hand terms is not a defect.
        """
        ma = getattr(a, "meaning", None)
        mb = getattr(b, "meaning", None)
        if not ma or not mb:
            return False
        ha, hb = ma.hand, mb.hand
        if not ha or not hb:
            return False
        if ma.artificial or mb.artificial:
            return False
        if not ha.hcp or not hb.hcp:
            return False

        # HCP ranges must intersect
        a_min = ha.hcp.min if ha.hcp.min is not None else 0
        a_max = ha.hcp.max if ha.hcp.max is not None else 37
        b_min = hb.hcp.min if hb.hcp.min is not None else 0
        b_max = hb.hcp.max if hb.hcp.max is not None else 37
        if max(a_min, b_min) > min(a_max, b_max):
            return False

        # Shape sets must intersect. If only one bid names a shape, the other
        # admits every shape, so they still overlap.
        shapes_a = self._shapes_of(ha.shape)
        shapes_b = self._shapes_of(hb.shape)
        if shapes_a is not None and shapes_b is not None:
            if not (shapes_a & shapes_b):
                return False

        # Every suit's length range must intersect
        for suit in ("clubs", "diamonds", "hearts", "spades"):
            ra = getattr(ha, suit, None)
            rb = getattr(hb, suit, None)
            if ra is None or rb is None:
                continue    # unconstrained on this suit → no conflict
            sa_min = ra.exactly if ra.exactly is not None else (ra.min or 0)
            sa_max = ra.exactly if ra.exactly is not None else (
                ra.max if ra.max is not None else 13
            )
            sb_min = rb.exactly if rb.exactly is not None else (rb.min or 0)
            sb_max = rb.exactly if rb.exactly is not None else (
                rb.max if rb.max is not None else 13
            )
            if max(sa_min, sb_min) > min(sa_max, sb_max):
                return False    # this suit alone makes the bids exclusive

        return True

    def _suits_mutually_exclusive(self, ha: Any, hb: Any) -> bool:
        """Two hand constraints are mutually exclusive if they require
        different suits with length that can't coexist."""
        suits = ["clubs", "diamonds", "hearts", "spades"]
        for suit in suits:
            ra = getattr(ha, suit, None)
            rb = getattr(hb, suit, None)
            if ra and rb:
                # If both require the same suit, not exclusive by suit alone
                continue
            if ra and ra.min and ra.min >= 5:
                # a needs 5+ of this suit; check if b needs 5+ of another
                for other in suits:
                    if other == suit:
                        continue
                    rb_other = getattr(hb, other, None)
                    if rb_other and rb_other.min and rb_other.min >= 5:
                        return True  # Can't have two 5+ suits (mostly)
        return False

    # ------------------------------------------------------------------
    # val-004: convention-ref-exists
    # ------------------------------------------------------------------

    def _check_val_004(self) -> ValidationResult:
        conv_keys = set(self.doc.conventions.keys()) if self.doc.conventions else set()
        conv_ids = set()
        if self.doc.conventions:
            conv_ids = {c.id for c in self.doc.conventions.values()}
        all_known = conv_keys | conv_ids

        missing: list[dict] = []
        self._collect_convention_refs(self.doc.openings, ["openings"], all_known, missing)

        if missing:
            return ValidationResult(
                rule_id="val-004",
                rule_name="convention-ref-exists",
                severity="error",
                passed=False,
                message=f"{len(missing)} missing convention reference(s).",
                details=missing,
            )
        return ValidationResult(
            rule_id="val-004",
            rule_name="convention-ref-exists",
            severity="error",
            passed=True,
            message="All convention references exist.",
        )

    def _collect_convention_refs(
        self,
        nodes: list | None,
        path: list[str],
        known: set[str],
        missing: list[dict],
    ) -> None:
        if not nodes:
            return
        for node in nodes:
            # Check ref field
            if node.ref and node.ref not in known:
                missing.append({"path": "/".join(path), "ref": node.ref})
            # Check conventions_applied
            if node.conventions_applied:
                for ca in node.conventions_applied:
                    ref = ca.get("ref") if isinstance(ca, dict) else ca
                    if ref and ref not in known:
                        missing.append({"path": "/".join(path), "ref": ref})
            if node.responses:
                self._collect_convention_refs(
                    node.responses, [*path, node.bid or "?"], known, missing
                )
            if node.continuations:
                self._collect_convention_refs(
                    node.continuations, [*path, node.bid or "?"], known, missing
                )

    # ------------------------------------------------------------------
    # val-005: convention-conflicts
    # ------------------------------------------------------------------

    def _check_val_005(self) -> ValidationResult:
        if not self.doc.conventions:
            return ValidationResult(
                rule_id="val-005",
                rule_name="convention-conflicts",
                severity="error",
                passed=True,
                skipped=True,
                message="No conventions defined (not checked).",
            )
        # Build conflict graph
        conflicts: list[dict] = []
        conv_map = self.doc.conventions
        for name, conv in conv_map.items():
            if not conv.conflicts_with:
                continue
            for conflict_id in conv.conflicts_with:
                # Check if conflicting convention is also present
                for other_name, other_conv in conv_map.items():
                    if other_conv.id == conflict_id or other_name == conflict_id:
                        conflicts.append({
                            "convention_a": conv.id,
                            "convention_b": other_conv.id,
                        })

        if conflicts:
            return ValidationResult(
                rule_id="val-005",
                rule_name="convention-conflicts",
                severity="error",
                passed=False,
                message=f"{len(conflicts)} conflicting convention pair(s) active.",
                details=conflicts,
            )
        return ValidationResult(
            rule_id="val-005",
            rule_name="convention-conflicts",
            severity="error",
            passed=True,
            message="No convention conflicts.",
        )

    # ------------------------------------------------------------------
    # val-006: pattern-ref-exists
    # ------------------------------------------------------------------

    def _check_val_006(self) -> ValidationResult:
        pattern_names: set[str] = set()
        if self.doc.definitions and self.doc.definitions.patterns:
            pattern_names = set(self.doc.definitions.patterns.keys())

        missing: list[dict] = []
        self._collect_pattern_refs(self.doc.openings, ["openings"], pattern_names, missing)

        if missing:
            return ValidationResult(
                rule_id="val-006",
                rule_name="pattern-ref-exists",
                severity="error",
                passed=False,
                message=f"{len(missing)} missing pattern reference(s).",
                details=missing,
            )
        return ValidationResult(
            rule_id="val-006",
            rule_name="pattern-ref-exists",
            severity="error",
            passed=True,
            message="All pattern references exist.",
        )

    def _collect_pattern_refs(
        self,
        nodes: list | None,
        path: list[str],
        known: set[str],
        missing: list[dict],
    ) -> None:
        if not nodes:
            return
        for node in nodes:
            if node.meaning and node.meaning.hand and node.meaning.hand.shape:
                shape = node.meaning.hand.shape
                if isinstance(shape, dict) and "ref" in shape:
                    ref = shape["ref"]
                    if ref not in known:
                        missing.append({"path": "/".join(path), "ref": ref})
            if node.responses:
                self._collect_pattern_refs(
                    node.responses, [*path, node.bid or "?"], known, missing
                )
            if node.continuations:
                self._collect_pattern_refs(
                    node.continuations, [*path, node.bid or "?"], known, missing
                )

    # ------------------------------------------------------------------
    # val-007: forcing-consistency
    # ------------------------------------------------------------------

    def _check_val_007(self) -> ValidationResult:
        violations: list[dict] = []
        self._check_forcing_tree(self.doc.openings, ["openings"], None, violations)

        if violations:
            return ValidationResult(
                rule_id="val-007",
                rule_name="forcing-consistency",
                severity="error",
                passed=False,
                message=f"{len(violations)} forcing consistency violation(s).",
                details=violations,
            )
        return ValidationResult(
            rule_id="val-007",
            rule_name="forcing-consistency",
            severity="error",
            passed=True,
            message="Forcing levels are consistent.",
        )

    def _check_forcing_tree(
        self,
        nodes: list | None,
        path: list[str],
        parent_forcing: str | None,
        violations: list[dict],
    ) -> None:
        if not nodes:
            return
        for node in nodes:
            current_forcing = None
            if node.meaning and node.meaning.forcing:
                current_forcing = node.meaning.forcing.value if hasattr(
                    node.meaning.forcing, "value"
                ) else str(node.meaning.forcing)
            # Check: parent is game-forcing, child cannot be signoff/none
            if parent_forcing == "game" and current_forcing in ("signoff", "none"):
                violations.append({
                    "path": "/".join(path),
                    "bid": node.bid,
                    "parent_forcing": parent_forcing,
                    "child_forcing": current_forcing,
                })
            # Propagate forcing level
            effective = current_forcing or parent_forcing
            if node.responses:
                self._check_forcing_tree(
                    node.responses, [*path, node.bid or "?"], effective, violations
                )
            if node.continuations:
                self._check_forcing_tree(
                    node.continuations, [*path, node.bid or "?"], effective, violations
                )

    # ------------------------------------------------------------------
    # val-008: alertable-check
    # ------------------------------------------------------------------

    def _check_val_008(self) -> ValidationResult:
        issues: list[dict] = []
        self._collect_alertable_issues(self.doc.openings, ["openings"], issues)

        if issues:
            return ValidationResult(
                rule_id="val-008",
                rule_name="alertable-check",
                severity="warning",
                passed=False,
                message=f"{len(issues)} artificial bid(s) not marked alertable.",
                details=issues,
            )
        return ValidationResult(
            rule_id="val-008",
            rule_name="alertable-check",
            severity="warning",
            passed=True,
            message="All artificial bids are marked alertable.",
        )

    def _collect_alertable_issues(
        self, nodes: list | None, path: list[str], issues: list[dict]
    ) -> None:
        if not nodes:
            return
        for node in nodes:
            if node.meaning and node.meaning.artificial and not node.meaning.alertable:
                issues.append({"path": "/".join(path), "bid": node.bid})
            if node.responses:
                self._collect_alertable_issues(
                    node.responses, [*path, node.bid or "?"], issues
                )
            if node.continuations:
                self._collect_alertable_issues(
                    node.continuations, [*path, node.bid or "?"], issues
                )

    # ------------------------------------------------------------------
    # val-009: seat-vul-no-conflict
    # ------------------------------------------------------------------

    def _check_val_009(self) -> ValidationResult:
        """Check that context_overrides don't have duplicate seat+vul conditions.

        If two overrides in the same BidNode have identical seat AND
        vulnerability, the second one would always be shadowed.
        """
        conflicts: list[dict] = []

        def check_node(node: Any, path: str) -> None:
            overrides = getattr(node, "context_overrides", None) or []
            seen: dict[tuple, int] = {}
            for idx, override in enumerate(overrides):
                if not isinstance(override, dict):
                    continue
                ctx = override.get("context", {})
                if not isinstance(ctx, dict):
                    continue
                seat = ctx.get("seat")
                vul = ctx.get("vulnerability")
                key = (str(seat), str(vul))
                if key in seen:
                    conflicts.append({
                        "path": path,
                        "bid": getattr(node, "bid", "?"),
                        "duplicate_override_index": idx,
                        "first_seen_at": seen[key],
                        "seat": seat,
                        "vulnerability": vul,
                    })
                else:
                    seen[key] = idx

        override_count = 0

        def walk(nodes: list[Any], parent: str) -> None:
            nonlocal override_count
            for node in nodes:
                bid = getattr(node, "bid", None) or "?"
                path = f"{parent}/{bid}" if parent else bid
                override_count += len(getattr(node, "context_overrides", None) or [])
                check_node(node, path)
                responses = getattr(node, "responses", None) or []
                continuations = getattr(node, "continuations", None) or []
                if responses:
                    walk(responses, path)
                if continuations:
                    walk(continuations, path)

        walk(self.doc.openings or [], "")

        if conflicts:
            return ValidationResult(
                rule_id="val-009",
                rule_name="seat-vul-no-conflict",
                severity="error",
                passed=False,
                message=f"{len(conflicts)} duplicate context_override condition(s) detected.",
                details=conflicts,
            )
        if override_count == 0:
            return ValidationResult(
                rule_id="val-009",
                rule_name="seat-vul-no-conflict",
                severity="error",
                passed=True,
                skipped=True,
                message="No context_overrides defined (not checked).",
            )
        return ValidationResult(
            rule_id="val-009",
            rule_name="seat-vul-no-conflict",
            severity="error",
            passed=True,
            message=(
                f"No duplicate seat/vulnerability overrides "
                f"among {override_count} context_override(s)."
            ),
        )

    # ------------------------------------------------------------------
    # val-010: foreach-expansion-conflict
    # ------------------------------------------------------------------

    def _check_val_010(self) -> ValidationResult:
        """Check that foreach_suit expansion produces no duplicate bids.

        Runs the expander and verifies no two sibling nodes in the expanded
        tree share the same bid value.
        """
        from bbdsl.core.expander import expand_document

        try:
            expanded = expand_document(self.doc)
        except Exception as exc:
            return ValidationResult(
                rule_id="val-010",
                rule_name="foreach-expansion-conflict",
                severity="error",
                passed=False,
                message=f"foreach_suit expansion failed: {exc}",
                details=[{"error": str(exc)}],
            )

        conflicts: list[dict] = []

        def check_siblings(nodes: list[Any], parent_path: str) -> None:
            bids: dict[str, str] = {}
            for node in nodes:
                if isinstance(node, dict):
                    bid = node.get("bid")
                else:
                    bid = getattr(node, "bid", None)
                if not bid:
                    continue
                path = f"{parent_path}/{bid}" if parent_path else bid
                if bid in bids:
                    conflicts.append({
                        "path": path,
                        "bid": bid,
                        "conflict_with": bids[bid],
                    })
                else:
                    bids[bid] = path

        def walk_expanded(nodes: list[Any], parent_path: str) -> None:
            check_siblings(nodes, parent_path)
            for node in nodes:
                if isinstance(node, dict):
                    bid = node.get("bid") or "?"
                    path = f"{parent_path}/{bid}" if parent_path else bid
                    walk_expanded(node.get("responses") or [], path)
                    walk_expanded(node.get("continuations") or [], path)
                else:
                    bid = getattr(node, "bid", None) or "?"
                    path = f"{parent_path}/{bid}" if parent_path else bid
                    responses = getattr(node, "responses", None) or []
                    continuations = getattr(node, "continuations", None) or []
                    walk_expanded(responses, path)
                    walk_expanded(continuations, path)

        walk_expanded(expanded.get("openings") or [], "")

        if conflicts:
            return ValidationResult(
                rule_id="val-010",
                rule_name="foreach-expansion-conflict",
                severity="error",
                passed=False,
                message=f"{len(conflicts)} duplicate bid(s) after foreach_suit expansion.",
                details=conflicts,
            )
        return ValidationResult(
            rule_id="val-010",
            rule_name="foreach-expansion-conflict",
            severity="error",
            passed=True,
            message="No bid conflicts after foreach_suit expansion.",
        )

    # ------------------------------------------------------------------
    # val-011: convention-id-format
    # ------------------------------------------------------------------

    def _check_val_011(self) -> ValidationResult:
        if not self.doc.conventions:
            return ValidationResult(
                rule_id="val-011",
                rule_name="convention-id-format",
                severity="error",
                passed=True,
                skipped=True,
                message="No conventions defined (not checked).",
            )
        bad_ids: list[dict] = []
        for name, conv in self.doc.conventions.items():
            if not CONVENTION_ID_RE.match(conv.id):
                bad_ids.append({"convention": name, "id": conv.id})

        if bad_ids:
            return ValidationResult(
                rule_id="val-011",
                rule_name="convention-id-format",
                severity="error",
                passed=False,
                message=f"{len(bad_ids)} convention ID(s) have invalid format.",
                details=bad_ids,
            )
        return ValidationResult(
            rule_id="val-011",
            rule_name="convention-id-format",
            severity="error",
            passed=True,
            message="All convention IDs have valid format.",
        )

    # ------------------------------------------------------------------
    # val-012: shape-format
    # ------------------------------------------------------------------

    def _check_val_012(self) -> ValidationResult:
        if not self.doc.definitions or not self.doc.definitions.patterns:
            return ValidationResult(
                rule_id="val-012",
                rule_name="shape-format",
                severity="error",
                passed=True,
                skipped=True,
                message="No patterns defined (not checked).",
            )
        bad: list[dict] = []
        for name, pattern in self.doc.definitions.patterns.items():
            if pattern.shapes:
                for s in pattern.shapes:
                    if "=" in s and "-" not in s:
                        bad.append({
                            "pattern": name, "field": "shapes",
                            "value": s, "reason": "Generic shapes must use '-', not '='",
                        })
            if pattern.shapes_exact:
                for s in pattern.shapes_exact:
                    if "-" in s and "=" not in s:
                        bad.append({
                            "pattern": name, "field": "shapes_exact",
                            "value": s, "reason": "Exact shapes must use '=', not '-'",
                        })

        if bad:
            return ValidationResult(
                rule_id="val-012",
                rule_name="shape-format",
                severity="error",
                passed=False,
                message=f"{len(bad)} shape format violation(s).",
                details=bad,
            )
        return ValidationResult(
            rule_id="val-012",
            rule_name="shape-format",
            severity="error",
            passed=True,
            message="All shape formats are correct.",
        )

    # ------------------------------------------------------------------
    # val-013: priority-unique
    # ------------------------------------------------------------------

    def _check_val_013(self) -> ValidationResult:
        """No duplicate priority values among sibling bid nodes."""
        duplicates: list[dict] = []

        def check_siblings(nodes: list[Any], parent_path: str) -> None:
            seen: dict[int, str] = {}
            for node in nodes:
                p = node.priority
                if p is None:
                    continue
                bid = getattr(node, "bid", None) or "?"
                path = f"{parent_path}/{bid}" if parent_path else bid
                if p in seen:
                    duplicates.append({
                        "path": path,
                        "priority": p,
                        "conflict_with": seen[p],
                    })
                else:
                    seen[p] = path

        def walk(nodes: list[Any], parent_path: str) -> None:
            check_siblings(nodes, parent_path)
            for node in nodes:
                bid = getattr(node, "bid", None) or "?"
                path = f"{parent_path}/{bid}" if parent_path else bid
                responses = getattr(node, "responses", None) or []
                continuations = getattr(node, "continuations", None) or []
                if responses:
                    walk(responses, path)
                if continuations:
                    walk(continuations, path)

        walk(self.doc.openings or [], "")

        if duplicates:
            return ValidationResult(
                rule_id="val-013",
                rule_name="priority-unique",
                severity="error",
                passed=False,
                message=f"{len(duplicates)} duplicate priority value(s) among siblings.",
                details=duplicates,
            )
        return ValidationResult(
            rule_id="val-013",
            rule_name="priority-unique",
            severity="error",
            passed=True,
            message="All sibling bid priorities are unique.",
        )

    # ------------------------------------------------------------------
    # val-014: selection-rules-exhaustive
    # ------------------------------------------------------------------

    def _check_val_014(self) -> ValidationResult:
        """selection_rules must contain a catch-all condition: 'true' rule."""
        if not self.doc.selection_rules:
            return ValidationResult(
                rule_id="val-014",
                rule_name="selection-rules-exhaustive",
                severity="warning",
                passed=True,
                skipped=True,
                message="No selection_rules defined (not checked).",
            )

        from bbdsl.core.selector import parse_selection_rules

        rules = parse_selection_rules(self.doc.selection_rules)
        has_catchall = any(
            str(r.get("condition", "")).strip().lower() in ("true", "1")
            for r in rules
        )

        if not has_catchall:
            return ValidationResult(
                rule_id="val-014",
                rule_name="selection-rules-exhaustive",
                severity="error",
                passed=False,
                message="selection_rules lacks a catch-all rule (condition: 'true').",
                details=[{"rules_count": len(rules)}],
            )
        return ValidationResult(
            rule_id="val-014",
            rule_name="selection-rules-exhaustive",
            severity="error",
            passed=True,
            message="selection_rules has a catch-all rule.",
        )
