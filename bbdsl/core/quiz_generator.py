"""Bridge bidding quiz generator.

Produces multiple-choice quiz questions from a BBDSL document.

Two question types:
  ``opening``  — Show a hand; ask "What is your opening bid?"
  ``response`` — Show a hand + partner's opening; ask "What do you respond?"

Each question has 4 choices (correct + 3 distractors) and an explanation.

Example::

    from bbdsl.core.loader import load_document
    from bbdsl.core.quiz_generator import generate_quiz

    doc = load_document("examples/precision.bbdsl.yaml")
    questions = generate_quiz(doc, n=10, seed=42)
    for q in questions:
        print(q.question_text, "→", q.correct_bid)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from bbdsl.core.hand_generator import BridgeHand, generate_hand
from bbdsl.models.system import BBDSLDocument


# ---------------------------------------------------------------------------
# i18n helper (same pattern as other modules)
# ---------------------------------------------------------------------------

def _t(value: Any, locale: str) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get(locale) or value.get("en") or next(iter(value.values()), "")
    return str(value)


# ---------------------------------------------------------------------------
# Hand summary helper (for explanations)
# ---------------------------------------------------------------------------

_SUIT_EN = {"spades": "spades", "hearts": "hearts",
            "diamonds": "diamonds", "clubs": "clubs"}
_SUIT_ZH = {"spades": "黑桃", "hearts": "紅心",
            "diamonds": "方塊", "clubs": "梅花"}
_FORCING_EN = {"game": "GF", "invitational": "INV", "one_round": "F1",
               "signoff": "S/O", "none": "NF"}
_FORCING_ZH = {"game": "成局強迫", "invitational": "邀請",
               "one_round": "一輪強迫", "signoff": "到叫", "none": "非強迫"}


def _hand_summary(hand: Any, locale: str) -> str:
    """Return a compact hand constraint summary, e.g. '15-17 HCP, balanced'."""
    if hand is None:
        return ""
    parts: list[str] = []
    if hand.hcp:
        h = hand.hcp
        if h.min is not None and h.max is not None:
            parts.append(f"{h.min}-{h.max} HCP")
        elif h.min is not None:
            parts.append(f"{h.min}+ HCP")
        elif h.max is not None:
            parts.append(f"≤{h.max} HCP")
    suit_labels = _SUIT_ZH if locale == "zh-TW" else _SUIT_EN
    for suit in ("spades", "hearts", "diamonds", "clubs"):
        r = getattr(hand, suit, None)
        if r is None:
            continue
        label = suit_labels[suit]
        if r.min is not None:
            parts.append(f"{r.min}+ {label}")
    if hand.shape and isinstance(hand.shape, dict) and "ref" in hand.shape:
        ref = hand.shape["ref"]
        if locale == "zh-TW":
            parts.append({"balanced": "平均", "semi_balanced": "半平均"}.get(ref, ref))
        else:
            parts.append(ref.replace("_", "-"))
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# QuizQuestion
# ---------------------------------------------------------------------------

@dataclass
class QuizQuestion:
    """A single multiple-choice bridge bidding quiz question."""

    question_type: str        # "opening" | "response"
    hand: BridgeHand
    sequence: list[str]       # [] for opening; ["1C"] for response questions
    question_text: str
    correct_bid: str
    choices: list[str]        # exactly 4, shuffled, includes correct_bid
    explanation: str
    hint: str = ""            # optional hint (bid name/description)

    def to_dict(self) -> dict:
        return {
            "type":         self.question_type,
            "hand":         self.hand.to_dict(),
            "sequence":     self.sequence,
            "question":     self.question_text,
            "correct":      self.correct_bid,
            "choices":      self.choices,
            "explanation":  self.explanation,
            "hint":         self.hint,
        }


# ---------------------------------------------------------------------------
# Distractor selection
# ---------------------------------------------------------------------------

def _get_distractors(
    correct_bid: str,
    candidates: list[str],
    rng: random.Random,
    n: int = 3,
) -> list[str]:
    """Return *n* distractor bids from *candidates* (excluding *correct_bid*)."""
    pool = [b for b in candidates if b != correct_bid]
    rng.shuffle(pool)
    distractors = pool[:n]
    # Pad with "Pass" if not enough candidates
    while len(distractors) < n:
        if "Pass" not in distractors:
            distractors.append("Pass")
        else:
            distractors.append(f"?{len(distractors)}")
    return distractors[:n]


# ---------------------------------------------------------------------------
# Opening quiz
# ---------------------------------------------------------------------------

def generate_opening_questions(
    doc: BBDSLDocument,
    locale: str = "en",
    seed: int | None = None,
    max_per_opening: int = 1,
    max_attempts_per_q: int = 3000,
) -> list[QuizQuestion]:
    """Generate opening-quiz questions from *doc*.

    For each opening that has a hand constraint, generate *max_per_opening*
    hand(s) matching that constraint and create a multiple-choice question.

    Args:
        doc: The BBDSL document.
        locale: 'en' or 'zh-TW'.
        seed: Random seed for reproducibility.
        max_per_opening: Number of questions to try per opening.
        max_attempts_per_q: Max rejection-sampling attempts per question.

    Returns:
        List of :class:`QuizQuestion` instances.
    """
    rng = random.Random(seed)
    questions: list[QuizQuestion] = []
    openings = doc.openings or []
    all_opening_bids = [o.bid for o in openings if o.bid]

    for opening in openings:
        bid = getattr(opening, "bid", None)
        meaning = getattr(opening, "meaning", None)
        if not bid or not meaning or not meaning.hand:
            continue

        # Try to generate max_per_opening hands
        for _ in range(max_per_opening):
            try:
                hand = generate_hand(
                    meaning.hand,
                    seed=rng.randint(0, 999_999),
                    max_attempts=max_attempts_per_q,
                )
            except ValueError:
                continue  # skip this opening if hand generation fails

            # Build question
            desc = _t(meaning.description, locale)
            summary = _hand_summary(meaning.hand, locale)
            explanation = f"{bid}: {desc or summary}"

            # Hint: opening name from description
            hint = desc[:50] if desc else summary[:50]

            distractors = _get_distractors(bid, all_opening_bids, rng, n=3)
            choices = [bid] + distractors
            rng.shuffle(choices)

            q_text = (
                "您的開叫是什麼？" if locale == "zh-TW"
                else "What is your opening bid?"
            )
            questions.append(QuizQuestion(
                question_type="opening",
                hand=hand,
                sequence=[],
                question_text=q_text,
                correct_bid=bid,
                choices=choices,
                explanation=explanation,
                hint=hint,
            ))

    rng.shuffle(questions)
    return questions


# ---------------------------------------------------------------------------
# Response quiz
# ---------------------------------------------------------------------------

def generate_response_questions(
    doc: BBDSLDocument,
    locale: str = "en",
    seed: int | None = None,
    max_per_response: int = 1,
    max_attempts_per_q: int = 3000,
) -> list[QuizQuestion]:
    """Generate response-quiz questions from *doc*.

    For each opening that has responses with hand constraints, generate
    a question asking what to respond.

    Args:
        doc: The BBDSL document.
        locale: 'en' or 'zh-TW'.
        seed: Random seed.
        max_per_response: Number of questions per response node.
        max_attempts_per_q: Max rejection-sampling attempts per question.

    Returns:
        List of :class:`QuizQuestion` instances.
    """
    rng = random.Random(seed)
    questions: list[QuizQuestion] = []
    openings = doc.openings or []

    for opening in openings:
        opening_bid = getattr(opening, "bid", None)
        if not opening_bid:
            continue
        responses = getattr(opening, "responses", None) or []
        if not responses:
            continue

        all_resp_bids = [r.bid for r in responses if getattr(r, "bid", None)]
        if len(all_resp_bids) < 2:
            continue  # need at least 2 choices

        for resp in responses:
            resp_bid = getattr(resp, "bid", None)
            meaning = getattr(resp, "meaning", None)
            if not resp_bid or not meaning or not meaning.hand:
                continue

            for _ in range(max_per_response):
                try:
                    hand = generate_hand(
                        meaning.hand,
                        seed=rng.randint(0, 999_999),
                        max_attempts=max_attempts_per_q,
                    )
                except ValueError:
                    continue

                desc = _t(meaning.description, locale)
                summary = _hand_summary(meaning.hand, locale)
                explanation = f"{resp_bid}: {desc or summary}"
                hint = desc[:50] if desc else summary[:50]

                distractors = _get_distractors(resp_bid, all_resp_bids, rng, n=3)
                choices = [resp_bid] + distractors
                rng.shuffle(choices)

                if locale == "zh-TW":
                    q_text = f"同伴開叫 {opening_bid}，您的回應是？"
                else:
                    q_text = f"Partner opened {opening_bid}. What do you respond?"

                # Opening hint for context
                opener_meaning = getattr(opening, "meaning", None)
                opener_desc = _t(
                    getattr(opener_meaning, "description", None), locale
                ) if opener_meaning else ""

                questions.append(QuizQuestion(
                    question_type="response",
                    hand=hand,
                    sequence=[opening_bid],
                    question_text=q_text,
                    correct_bid=resp_bid,
                    choices=choices,
                    explanation=explanation,
                    hint=f"{opening_bid}: {opener_desc}" if opener_desc else opening_bid,
                ))

    rng.shuffle(questions)
    return questions


# ---------------------------------------------------------------------------
# Combined generator
# ---------------------------------------------------------------------------

def generate_quiz(
    doc: BBDSLDocument,
    n: int = 20,
    question_types: list[str] | None = None,
    locale: str = "en",
    seed: int | None = None,
) -> list[QuizQuestion]:
    """Generate up to *n* quiz questions from *doc*.

    Args:
        doc: The BBDSL document.
        n: Maximum number of questions to return.
        question_types: Subset of ["opening", "response"]. Defaults to both.
        locale: 'en' or 'zh-TW'.
        seed: Random seed.

    Returns:
        List of shuffled :class:`QuizQuestion` instances (at most *n*).
    """
    if question_types is None:
        question_types = ["opening", "response"]

    rng = random.Random(seed)
    questions: list[QuizQuestion] = []

    seed_a = rng.randint(0, 999_999)
    seed_b = rng.randint(0, 999_999)

    if "opening" in question_types:
        questions.extend(
            generate_opening_questions(doc, locale=locale, seed=seed_a,
                                       max_per_opening=2)
        )
    if "response" in question_types:
        questions.extend(
            generate_response_questions(doc, locale=locale, seed=seed_b,
                                        max_per_response=1)
        )

    rng.shuffle(questions)
    return questions[:n]
