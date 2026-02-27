"""Tests for bbdsl.exporters.quiz_exporter."""

import json
import re
from pathlib import Path

import pytest

from bbdsl.core.loader import load_document
from bbdsl.exporters.quiz_exporter import export_quiz

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PRECISION_PATH = "examples/precision.bbdsl.yaml"
SAYC_PATH = "examples/sayc.bbdsl.yaml"


@pytest.fixture(scope="module")
def precision_doc():
    return load_document(PRECISION_PATH)


@pytest.fixture(scope="module")
def sayc_doc():
    return load_document(SAYC_PATH)


@pytest.fixture(scope="module")
def precision_html(precision_doc):
    """HTML string for precision doc, n=10, seed=42."""
    return export_quiz(precision_doc, n=10, seed=42)


# ---------------------------------------------------------------------------
# Basic structure
# ---------------------------------------------------------------------------

class TestExportQuizStructure:
    def test_returns_str(self, precision_doc):
        result = export_quiz(precision_doc, n=5, seed=1)
        assert isinstance(result, str)

    def test_has_doctype(self, precision_html):
        assert "<!DOCTYPE html>" in precision_html

    def test_has_html_tag(self, precision_html):
        assert "<html" in precision_html

    def test_has_head(self, precision_html):
        assert "<head>" in precision_html or "<head " in precision_html

    def test_has_body(self, precision_html):
        assert "<body" in precision_html

    def test_has_script_tag(self, precision_html):
        assert "<script>" in precision_html

    def test_has_tailwind(self, precision_html):
        assert "tailwindcss" in precision_html.lower() or "cdn.tailwindcss.com" in precision_html

    def test_closes_html(self, precision_html):
        assert "</html>" in precision_html


# ---------------------------------------------------------------------------
# Quiz data (JSON embedded)
# ---------------------------------------------------------------------------

class TestQuizDataEmbedded:
    def _extract_quiz_data(self, html: str) -> list:
        """Extract the quizData JSON array from the HTML."""
        m = re.search(r"const quizData = (\[.*?\]);", html, re.DOTALL)
        assert m is not None, "quizData not found in HTML"
        return json.loads(m.group(1))

    def test_quiz_data_present(self, precision_html):
        assert "const quizData" in precision_html

    def test_quiz_data_is_valid_json(self, precision_html):
        data = self._extract_quiz_data(precision_html)
        assert isinstance(data, list)

    def test_quiz_data_has_questions(self, precision_html):
        data = self._extract_quiz_data(precision_html)
        assert len(data) > 0

    def test_quiz_data_at_most_n(self, precision_doc):
        html = export_quiz(precision_doc, n=3, seed=42)
        m = re.search(r"const quizData = (\[.*?\]);", html, re.DOTALL)
        data = json.loads(m.group(1))
        assert len(data) <= 3

    def test_question_has_required_fields(self, precision_html):
        data = self._extract_quiz_data(precision_html)
        for q in data:
            assert "type" in q
            assert "hand" in q
            assert "sequence" in q
            assert "question" in q
            assert "correct" in q
            assert "choices" in q
            assert "explanation" in q

    def test_choices_count_4(self, precision_html):
        data = self._extract_quiz_data(precision_html)
        for q in data:
            assert len(q["choices"]) == 4

    def test_correct_in_choices(self, precision_html):
        data = self._extract_quiz_data(precision_html)
        for q in data:
            assert q["correct"] in q["choices"]

    def test_hand_fields(self, precision_html):
        data = self._extract_quiz_data(precision_html)
        for q in data:
            hand = q["hand"]
            assert "spades" in hand
            assert "hearts" in hand
            assert "diamonds" in hand
            assert "clubs" in hand
            assert "hcp" in hand

    def test_hand_13_cards(self, precision_html):
        data = self._extract_quiz_data(precision_html)
        for q in data:
            hand = q["hand"]
            total = (len(hand["spades"]) + len(hand["hearts"]) +
                     len(hand["diamonds"]) + len(hand["clubs"]))
            assert total == 13

    def test_hcp_is_int(self, precision_html):
        data = self._extract_quiz_data(precision_html)
        for q in data:
            assert isinstance(q["hand"]["hcp"], int)


# ---------------------------------------------------------------------------
# JavaScript functions
# ---------------------------------------------------------------------------

class TestJavaScriptFunctions:
    def test_start_quiz_function(self, precision_html):
        assert "function startQuiz()" in precision_html

    def test_show_question_function(self, precision_html):
        assert "function showQuestion(" in precision_html

    def test_select_answer_function(self, precision_html):
        assert "function selectAnswer(" in precision_html

    def test_next_question_function(self, precision_html):
        assert "function nextQuestion()" in precision_html

    def test_show_finish_function(self, precision_html):
        assert "function showFinish()" in precision_html

    def test_restart_quiz_function(self, precision_html):
        assert "function restartQuiz()" in precision_html

    def test_shuffle_function(self, precision_html):
        assert "function shuffle(" in precision_html


# ---------------------------------------------------------------------------
# UI elements
# ---------------------------------------------------------------------------

class TestUiElements:
    def test_score_display(self, precision_html):
        assert "score-display" in precision_html

    def test_progress_bar(self, precision_html):
        assert "progress-bar" in precision_html

    def test_hand_display(self, precision_html):
        assert "hand-display" in precision_html

    def test_spade_symbol(self, precision_html):
        assert "♠" in precision_html

    def test_heart_symbol(self, precision_html):
        assert "♥" in precision_html

    def test_diamond_symbol(self, precision_html):
        assert "♦" in precision_html

    def test_club_symbol(self, precision_html):
        assert "♣" in precision_html

    def test_choice_buttons_area(self, precision_html):
        assert "choices-area" in precision_html

    def test_feedback_area(self, precision_html):
        assert "feedback-area" in precision_html

    def test_next_button(self, precision_html):
        assert "btn-next" in precision_html

    def test_restart_button(self, precision_html):
        assert "btn-restart" in precision_html

    def test_finish_screen(self, precision_html):
        assert "finish-screen" in precision_html

    def test_question_labels_abcd(self, precision_html):
        # LABELS = ["A", "B", "C", "D"]
        assert 'LABELS' in precision_html


# ---------------------------------------------------------------------------
# Locale
# ---------------------------------------------------------------------------

class TestLocale:
    def test_locale_en_set(self, precision_doc):
        html = export_quiz(precision_doc, locale="en", n=5, seed=1)
        assert 'const LOCALE = "en"' in html

    def test_locale_zh_set(self, precision_doc):
        html = export_quiz(precision_doc, locale="zh-TW", n=5, seed=1)
        assert 'const LOCALE = "zh-TW"' in html

    def test_lang_attribute_en(self, precision_doc):
        html = export_quiz(precision_doc, locale="en", n=5, seed=1)
        assert 'lang="en"' in html

    def test_lang_attribute_zh(self, precision_doc):
        html = export_quiz(precision_doc, locale="zh-TW", n=5, seed=1)
        assert 'lang="zh-TW"' in html

    def test_zh_contains_chinese(self, precision_doc):
        html = export_quiz(precision_doc, locale="zh-TW", n=5, seed=1)
        assert "叫牌" in html or "練習" in html


# ---------------------------------------------------------------------------
# Title / system name
# ---------------------------------------------------------------------------

class TestTitleAndName:
    def test_system_name_in_html(self, precision_doc, precision_html):
        system_name = precision_doc.system.name
        if isinstance(system_name, dict):
            name = system_name.get("en") or next(iter(system_name.values()))
        else:
            name = str(system_name)
        assert name in precision_html

    def test_default_title_contains_quiz(self, precision_html):
        assert "Quiz" in precision_html or "練習" in precision_html

    def test_custom_title(self, precision_doc):
        html = export_quiz(precision_doc, title="My Custom Quiz", n=5, seed=1)
        assert "My Custom Quiz" in html


# ---------------------------------------------------------------------------
# File output
# ---------------------------------------------------------------------------

class TestFileOutput:
    def test_writes_to_file(self, precision_doc, tmp_path):
        out = tmp_path / "quiz.html"
        result = export_quiz(precision_doc, output_path=out, n=5, seed=1)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert content == result

    def test_creates_parent_dir(self, precision_doc, tmp_path):
        out = tmp_path / "nested" / "dir" / "quiz.html"
        export_quiz(precision_doc, output_path=out, n=5, seed=1)
        assert out.exists()

    def test_no_file_if_no_path(self, precision_doc, tmp_path):
        result = export_quiz(precision_doc, n=5, seed=1)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Seed reproducibility
# ---------------------------------------------------------------------------

class TestSeedReproducibility:
    def test_same_seed_same_html(self, precision_doc):
        html1 = export_quiz(precision_doc, n=5, seed=42)
        html2 = export_quiz(precision_doc, n=5, seed=42)
        assert html1 == html2

    def test_different_seeds_differ(self, precision_doc):
        html1 = export_quiz(precision_doc, n=5, seed=1)
        html2 = export_quiz(precision_doc, n=5, seed=2)
        # Very likely to differ
        assert html1 != html2


# ---------------------------------------------------------------------------
# Question types filtering
# ---------------------------------------------------------------------------

class TestQuestionTypes:
    def _extract_types(self, html: str) -> list:
        m = re.search(r"const quizData = (\[.*?\]);", html, re.DOTALL)
        if not m:
            return []
        data = json.loads(m.group(1))
        return [q.get("type") for q in data]

    def test_opening_only(self, precision_doc):
        html = export_quiz(precision_doc, question_types=["opening"], n=10, seed=42)
        types = self._extract_types(html)
        if types:
            assert all(t == "opening" for t in types)

    def test_response_only(self, precision_doc):
        html = export_quiz(precision_doc, question_types=["response"], n=10, seed=42)
        types = self._extract_types(html)
        if types:
            assert all(t == "response" for t in types)


# ---------------------------------------------------------------------------
# Multiple examples: no crash
# ---------------------------------------------------------------------------

class TestMultipleExamples:
    def test_precision_no_crash(self, precision_doc):
        html = export_quiz(precision_doc, seed=1)
        assert len(html) > 100

    def test_sayc_no_crash(self, sayc_doc):
        html = export_quiz(sayc_doc, seed=1)
        assert len(html) > 100

    def test_precision_n_0(self, precision_doc):
        """n=0 → empty quiz data, still valid HTML."""
        html = export_quiz(precision_doc, n=0, seed=1)
        assert "<!DOCTYPE html>" in html
        assert "const quizData" in html
