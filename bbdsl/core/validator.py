"""Validation engine: 14 rules (all real, Phase 2 complete)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from bbdsl.models.convention import CONVENTION_ID_RE
from bbdsl.models.system import BBDSLDocument


class ValidationResult(BaseModel):
    """Single validation rule result."""

    rule_id: str
    rule_name: str
    severity: str  # "error" | "warning" | "info"
    passed: bool
    message: str
    details: list[dict[str, Any]] = []


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

    def has_errors(self) -> bool:
        return self.error_count > 0


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
                    message="HCP coverage: at least one opening has no HCP limit (covers all).",
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
        if violations:
            return ValidationResult(
                rule_id="val-002",
                rule_name="no-overlap",
                severity="error",
                passed=False,
                message=f"{len(violations)} HCP/shape overlap(s) detected.",
                details=violations,
            )
        return ValidationResult(
            rule_id="val-002",
            rule_name="no-overlap",
            severity="error",
            passed=True,
            message="No HCP/shape overlaps found.",
        )

    def _check_siblings_overlap(
        self, nodes: list | None, path: list[str], violations: list[dict]
    ) -> None:
        if not nodes:
            return
        # Check pairwise overlap among siblings
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                if self._bids_overlap(a, b):
                    violations.append({
                        "path": "/".join(path),
                        "bid_a": a.bid,
                        "bid_b": b.bid,
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
        """Check if two sibling bids have overlapping HCP ranges AND
        overlapping suit constraints, indicating the same hand could
        satisfy both bids.

        Conservative in Phase 1: only flags when both bids require
        the SAME suit(s) with overlapping length ranges and overlapping
        HCP. Skips pairs involving shape refs or artificial bids.
        """
        ma = getattr(a, "meaning", None)
        mb = getattr(b, "meaning", None)
        if not ma or not mb:
            return False
        ha, hb = ma.hand, mb.hand
        if not ha or not hb:
            return False
        # Skip if either bid is artificial (priority-based, not constraint-based)
        if ma.artificial or mb.artificial:
            return False
        # Both must define HCP ranges
        if not ha.hcp or not hb.hcp:
            return False
        # Check HCP overlap
        a_min = ha.hcp.min if ha.hcp.min is not None else 0
        a_max = ha.hcp.max if ha.hcp.max is not None else 37
        b_min = hb.hcp.min if hb.hcp.min is not None else 0
        b_max = hb.hcp.max if hb.hcp.max is not None else 37
        if max(a_min, b_min) > min(a_max, b_max):
            return False  # No HCP overlap
        # If either has a shape ref, can't resolve exclusivity in Phase 1
        if ha.shape or hb.shape:
            return False
        # Both must have suit constraints, and at least one common suit
        # with overlapping length ranges
        suits = ("clubs", "diamonds", "hearts", "spades")
        a_has_suit = any(
            getattr(ha, s, None) and (getattr(ha, s).min is not None or getattr(ha, s).max is not None)
            for s in suits
        )
        b_has_suit = any(
            getattr(hb, s, None) and (getattr(hb, s).min is not None or getattr(hb, s).max is not None)
            for s in suits
        )
        if not a_has_suit or not b_has_suit:
            return False
        # Check for at least one common suit with overlapping ranges
        for suit in suits:
            ra = getattr(ha, suit, None)
            rb = getattr(hb, suit, None)
            if not ra or not rb:
                continue
            sa_min = ra.min if ra.min is not None else 0
            sa_max = ra.max if ra.max is not None else 13
            sb_min = rb.min if rb.min is not None else 0
            sb_max = rb.max if rb.max is not None else 13
            if max(sa_min, sb_min) <= min(sa_max, sb_max):
                return True  # Same suit, overlapping lengths + overlapping HCP
        return False

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
                message="No conventions defined.",
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

        def walk(nodes: list[Any], parent: str) -> None:
            for node in nodes:
                bid = getattr(node, "bid", None) or "?"
                path = f"{parent}/{bid}" if parent else bid
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
        return ValidationResult(
            rule_id="val-009",
            rule_name="seat-vul-no-conflict",
            severity="error",
            passed=True,
            message="No duplicate seat/vulnerability context overrides found.",
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
                message="No conventions defined.",
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
                message="No patterns defined.",
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
                message="No selection_rules defined (skipped).",
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
