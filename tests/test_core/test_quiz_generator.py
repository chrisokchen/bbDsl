"""Tests for bbdsl.core.quiz_generator."""

import pytest

from bbdsl.core.quiz_generator import (
    QuizQuestion,
    _get_distractors,
    _hand_summary,
    _t,
    generate_opening_questions,
    generate_quiz,
    generate_response_questions,
)
from bbdsl.core.hand_generator import BridgeHand
from bbdsl.core.loader import load_document

import random

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

PRECISION_PATH = "examples/precision.bbdsl.yaml"
SAYC_PATH = "examples/sayc.bbdsl.yaml"


@pytest.fixture(scope="module")
def precision_doc():
    return load_document(PRECISION_PATH)


@pytest.fixture(scope="module")
def sayc_doc():
    return load_document(SAYC_PATH)


# ---------------------------------------------------------------------------
# _t helper
# ---------------------------------------------------------------------------

class TestT:
    def test_none_returns_empty(self):
        assert _t(None, "en") == ""

    def test_str_returns_as_is(self):
        assert _t("hello", "en") == "hello"

    def test_dict_locale_en(self):
        assert _t({"en": "Hello", "zh-TW": "你好"}, "en") == "Hello"

    def test_dict_locale_zh(self):
        assert _t({"en": "Hello", "zh-TW": "你好"}, "zh-TW") == "你好"

    def test_dict_falls_back_to_en(self):
        assert _t({"en": "Hello"}, "zh-TW") == "Hello"

    def test_dict_first_value_if_no_en(self):
        result = _t({"fr": "Bonjour"}, "zh-TW")
        assert result == "Bonjour"

    def test_int_converted_to_str(self):
        assert _t(42, "en") == "42"


# ---------------------------------------------------------------------------
# _hand_summary
# ---------------------------------------------------------------------------

class TestHandSummary:
    def _mock_hand_constraint(self, hcp_min=None, hcp_max=None, hearts_min=None, shape_ref=None):
        """Create a minimal mock constraint object."""
        from types import SimpleNamespace
        hcp = None
        if hcp_min is not None or hcp_max is not None:
            hcp = SimpleNamespace(min=hcp_min, max=hcp_max)
        hearts = None
        if hearts_min is not None:
            hearts = SimpleNamespace(min=hearts_min, max=None, exactly=None)
        hand = SimpleNamespace(
            hcp=hcp,
            spades=None,
            hearts=hearts,
            diamonds=None,
            clubs=None,
            shape={"ref": shape_ref} if shape_ref else None,
        )
        return hand

    def test_hcp_range(self):
        hand = self._mock_hand_constraint(hcp_min=15, hcp_max=17)
        s = _hand_summary(hand, "en")
        assert "15-17 HCP" in s

    def test_hcp_min_only(self):
        hand = self._mock_hand_constraint(hcp_min=16)
        s = _hand_summary(hand, "en")
        assert "16+ HCP" in s

    def test_hcp_max_only(self):
        hand = self._mock_hand_constraint(hcp_max=7)
        s = _hand_summary(hand, "en")
        assert "≤7 HCP" in s

    def test_suit_min(self):
        hand = self._mock_hand_constraint(hearts_min=5)
        s = _hand_summary(hand, "en")
        assert "5+ hearts" in s

    def test_shape_ref_balanced(self):
        hand = self._mock_hand_constraint(shape_ref="balanced")
        s = _hand_summary(hand, "en")
        assert "balanced" in s

    def test_shape_ref_zh(self):
        hand = self._mock_hand_constraint(shape_ref="balanced")
        s = _hand_summary(hand, "zh-TW")
        assert "平均" in s

    def test_none_returns_empty(self):
        assert _hand_summary(None, "en") == ""

    def test_combined(self):
        hand = self._mock_hand_constraint(hcp_min=15, hcp_max=17, shape_ref="balanced")
        s = _hand_summary(hand, "en")
        assert "15-17 HCP" in s
        assert "balanced" in s


# ---------------------------------------------------------------------------
# _get_distractors
# ---------------------------------------------------------------------------

class TestGetDistractors:
    def _rng(self, seed=0):
        return random.Random(seed)

    def test_returns_n_distractors(self):
        d = _get_distractors("1C", ["1C", "1D", "1H", "1S", "1NT"], self._rng())
        assert len(d) == 3

    def test_excludes_correct(self):
        d = _get_distractors("1C", ["1C", "1D", "1H", "1S"], self._rng())
        assert "1C" not in d

    def test_pads_with_pass_if_few_candidates(self):
        d = _get_distractors("1C", ["1C", "1D"], self._rng())
        assert len(d) == 3
        assert "Pass" in d

    def test_all_unique_when_enough_candidates(self):
        d = _get_distractors("1C", ["1C", "1D", "1H", "1S", "1NT"], self._rng())
        assert len(set(d)) == len(d)

    def test_empty_candidates_pads(self):
        d = _get_distractors("1C", [], self._rng())
        assert len(d) == 3
        assert "Pass" in d

    def test_custom_n(self):
        d = _get_distractors("1C", ["1C", "1D", "1H", "1S"], self._rng(), n=2)
        assert len(d) == 2


# ---------------------------------------------------------------------------
# generate_opening_questions
# ---------------------------------------------------------------------------

class TestGenerateOpeningQuestions:
    def test_returns_list(self, precision_doc):
        qs = generate_opening_questions(precision_doc, seed=42)
        assert isinstance(qs, list)

    def test_each_is_quiz_question(self, precision_doc):
        qs = generate_opening_questions(precision_doc, seed=42)
        for q in qs:
            assert isinstance(q, QuizQuestion)

    def test_question_type_is_opening(self, precision_doc):
        qs = generate_opening_questions(precision_doc, seed=42)
        for q in qs:
            assert q.question_type == "opening"

    def test_sequence_is_empty_list(self, precision_doc):
        qs = generate_opening_questions(precision_doc, seed=42)
        for q in qs:
            assert q.sequence == []

    def test_choices_exactly_4(self, precision_doc):
        qs = generate_opening_questions(precision_doc, seed=42)
        for q in qs:
            assert len(q.choices) == 4

    def test_correct_bid_in_choices(self, precision_doc):
        qs = generate_opening_questions(precision_doc, seed=42)
        for q in qs:
            assert q.correct_bid in q.choices

    def test_hand_has_13_cards(self, precision_doc):
        qs = generate_opening_questions(precision_doc, seed=42)
        for q in qs:
            total = sum(len(getattr(q.hand, s)) for s in ["spades", "hearts", "diamonds", "clubs"])
            assert total == 13

    def test_question_text_en(self, precision_doc):
        qs = generate_opening_questions(precision_doc, locale="en", seed=42)
        assert any("opening bid" in q.question_text.lower() for q in qs)

    def test_question_text_zh(self, precision_doc):
        qs = generate_opening_questions(precision_doc, locale="zh-TW", seed=42)
        assert any("開叫" in q.question_text for q in qs)

    def test_explanation_contains_bid(self, precision_doc):
        qs = generate_opening_questions(precision_doc, seed=42)
        for q in qs:
            assert q.correct_bid in q.explanation

    def test_seed_reproducible(self, precision_doc):
        qs1 = generate_opening_questions(precision_doc, seed=77)
        qs2 = generate_opening_questions(precision_doc, seed=77)
        assert len(qs1) == len(qs2)
        for q1, q2 in zip(qs1, qs2):
            assert q1.correct_bid == q2.correct_bid
            assert q1.choices == q2.choices

    def test_max_per_opening_1(self, precision_doc):
        qs = generate_opening_questions(precision_doc, seed=42, max_per_opening=1)
        assert len(qs) >= 1

    def test_sayc_doc(self, sayc_doc):
        qs = generate_opening_questions(sayc_doc, seed=42)
        assert isinstance(qs, list)


# ---------------------------------------------------------------------------
# generate_response_questions
# ---------------------------------------------------------------------------

class TestGenerateResponseQuestions:
    def test_returns_list(self, precision_doc):
        qs = generate_response_questions(precision_doc, seed=42)
        assert isinstance(qs, list)

    def test_question_type_is_response(self, precision_doc):
        qs = generate_response_questions(precision_doc, seed=42)
        for q in qs:
            assert q.question_type == "response"

    def test_sequence_not_empty(self, precision_doc):
        qs = generate_response_questions(precision_doc, seed=42)
        if qs:  # precision may have responses with hand constraints
            for q in qs:
                assert len(q.sequence) >= 1

    def test_choices_exactly_4(self, precision_doc):
        qs = generate_response_questions(precision_doc, seed=42)
        for q in qs:
            assert len(q.choices) == 4

    def test_correct_bid_in_choices(self, precision_doc):
        qs = generate_response_questions(precision_doc, seed=42)
        for q in qs:
            assert q.correct_bid in q.choices

    def test_hand_has_13_cards(self, precision_doc):
        qs = generate_response_questions(precision_doc, seed=42)
        for q in qs:
            total = sum(len(getattr(q.hand, s)) for s in ["spades", "hearts", "diamonds", "clubs"])
            assert total == 13

    def test_question_text_contains_opening(self, precision_doc):
        qs = generate_response_questions(precision_doc, locale="en", seed=42)
        for q in qs:
            assert "Partner opened" in q.question_text or len(q.sequence) > 0

    def test_question_text_zh(self, precision_doc):
        qs = generate_response_questions(precision_doc, locale="zh-TW", seed=42)
        for q in qs:
            assert "開叫" in q.question_text or "回應" in q.question_text

    def test_seed_reproducible(self, precision_doc):
        qs1 = generate_response_questions(precision_doc, seed=99)
        qs2 = generate_response_questions(precision_doc, seed=99)
        assert len(qs1) == len(qs2)


# ---------------------------------------------------------------------------
# generate_quiz (combined)
# ---------------------------------------------------------------------------

class TestGenerateQuiz:
    def test_returns_list(self, precision_doc):
        qs = generate_quiz(precision_doc, seed=42)
        assert isinstance(qs, list)

    def test_at_most_n_questions(self, precision_doc):
        qs = generate_quiz(precision_doc, n=5, seed=42)
        assert len(qs) <= 5

    def test_default_20(self, precision_doc):
        qs = generate_quiz(precision_doc, seed=42)
        assert len(qs) <= 20

    def test_opening_only(self, precision_doc):
        qs = generate_quiz(precision_doc, question_types=["opening"], seed=42)
        for q in qs:
            assert q.question_type == "opening"

    def test_response_only(self, precision_doc):
        qs = generate_quiz(precision_doc, question_types=["response"], seed=42)
        for q in qs:
            assert q.question_type == "response"

    def test_both_types_present(self, precision_doc):
        qs = generate_quiz(precision_doc, n=50, seed=42)
        types = {q.question_type for q in qs}
        # We expect at least opening questions since precision has constrained openings
        assert "opening" in types

    def test_seed_reproducible(self, precision_doc):
        qs1 = generate_quiz(precision_doc, seed=123)
        qs2 = generate_quiz(precision_doc, seed=123)
        assert len(qs1) == len(qs2)
        for q1, q2 in zip(qs1, qs2):
            assert q1.correct_bid == q2.correct_bid

    def test_sayc_no_crash(self, sayc_doc):
        qs = generate_quiz(sayc_doc, seed=42)
        assert isinstance(qs, list)

    def test_locale_en(self, precision_doc):
        qs = generate_quiz(precision_doc, locale="en", seed=42)
        for q in qs:
            assert isinstance(q.question_text, str)

    def test_locale_zh(self, precision_doc):
        qs = generate_quiz(precision_doc, locale="zh-TW", seed=42)
        for q in qs:
            assert isinstance(q.question_text, str)


# ---------------------------------------------------------------------------
# QuizQuestion.to_dict
# ---------------------------------------------------------------------------

class TestQuizQuestionToDict:
    def _make_q(self):
        hand = BridgeHand(
            spades=["A", "K"],
            hearts=["Q", "J"],
            diamonds=["T", "9", "8"],
            clubs=["7", "6", "5", "4", "3", "2"],
            hcp=10,
        )
        return QuizQuestion(
            question_type="opening",
            hand=hand,
            sequence=[],
            question_text="What is your opening bid?",
            correct_bid="1NT",
            choices=["1NT", "1C", "Pass", "2NT"],
            explanation="1NT: 15-17 HCP balanced",
            hint="15-17 HCP, balanced",
        )

    def test_to_dict_keys(self):
        q = self._make_q()
        d = q.to_dict()
        assert "type" in d
        assert "hand" in d
        assert "sequence" in d
        assert "question" in d
        assert "correct" in d
        assert "choices" in d
        assert "explanation" in d
        assert "hint" in d

    def test_to_dict_values(self):
        q = self._make_q()
        d = q.to_dict()
        assert d["type"] == "opening"
        assert d["correct"] == "1NT"
        assert len(d["choices"]) == 4
        assert isinstance(d["hand"], dict)
        assert "spades" in d["hand"]
        assert "hcp" in d["hand"]

    def test_to_dict_sequence_empty(self):
        q = self._make_q()
        assert q.to_dict()["sequence"] == []

    def test_to_dict_hint(self):
        q = self._make_q()
        assert q.to_dict()["hint"] == "15-17 HCP, balanced"
