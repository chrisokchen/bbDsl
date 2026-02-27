"""BBDSL → Interactive HTML Quiz exporter.

Produces a single self-contained HTML file containing a multiple-choice
bridge bidding quiz with teaching mode.

Features:
  - Opening quiz: "What is your opening bid?"
  - Response quiz: "Partner opened 1C. What do you respond?"
  - Bridge hand display (♠♥♦♣ with suit colours)
  - 4 labelled choices (A / B / C / D)
  - Teaching mode: reveal correct answer + explanation after selection
  - Score counter and progress bar
  - Shuffle / restart functionality
  - Fully self-contained (no external deps beyond Tailwind CDN)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import BaseLoader, Environment

from bbdsl.core.quiz_generator import generate_quiz
from bbdsl.models.system import BBDSLDocument


# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------

def _t(value: Any, locale: str) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return value.get(locale) or value.get("en") or next(iter(value.values()), "")
    return str(value)


# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------

_QUIZ_TEMPLATE = r"""<!DOCTYPE html>
<html lang="{{ locale }}">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{{ page_title }}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { font-family: 'Segoe UI', system-ui, sans-serif; }
    .suit-s, .suit-c { color: #1f2937; }
    .suit-h, .suit-d { color: #dc2626; }
    .card-rank { font-family: monospace; font-size: 1rem; }
    .choice-btn {
      transition: background-color 0.15s, border-color 0.15s;
      cursor: pointer;
    }
    .choice-btn:disabled { cursor: default; }
    .choice-correct { background-color: #bbf7d0 !important; border-color: #16a34a !important; }
    .choice-wrong   { background-color: #fecaca !important; border-color: #dc2626 !important; }
    .choice-reveal  { background-color: #d1fae5 !important; border-color: #059669 !important; }
    .seq-badge {
      display: inline-block;
      font-family: monospace;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 1rem;
    }
    .progress-bar { transition: width 0.3s; }
    @keyframes pop { 0% { transform: scale(0.95); opacity: 0.5; }
                     100% { transform: scale(1); opacity: 1; } }
    .pop { animation: pop 0.2s ease-out; }
  </style>
</head>
<body class="bg-gray-100 min-h-screen py-8">

<main class="max-w-xl mx-auto">

  <!-- ── Header ── -->
  <header class="bg-white rounded-xl shadow p-4 mb-4 flex items-center justify-between">
    <div>
      <h1 class="text-lg font-bold text-gray-800">{{ system_name }}</h1>
      <p class="text-xs text-gray-500">{{ 'Bidding Quiz' if locale == 'en' else '叫牌練習' }}</p>
    </div>
    <div class="text-right">
      <div class="text-2xl font-bold text-blue-600" id="score-display">0 / 0</div>
      <div class="text-xs text-gray-500" id="progress-text">{{ 'Question 1' if locale == 'en' else '第 1 題' }}</div>
    </div>
  </header>

  <!-- ── Progress Bar ── -->
  <div class="bg-gray-200 rounded-full h-2 mb-4 overflow-hidden">
    <div id="progress-bar" class="progress-bar bg-blue-500 h-2 rounded-full" style="width:0%"></div>
  </div>

  <!-- ── Question Card ── -->
  <div id="question-card" class="bg-white rounded-xl shadow p-6 mb-4 pop">

    <!-- Context (for response questions) -->
    <div id="context-area" class="mb-3 hidden">
      <span class="text-xs text-gray-500 uppercase font-semibold tracking-wide">
        {{ 'Auction' if locale == 'en' else '叫牌序列' }}
      </span>
      <div id="sequence-display" class="mt-1 flex gap-2 flex-wrap"></div>
    </div>

    <!-- Question text -->
    <p id="question-text" class="text-base font-semibold text-gray-700 mb-4"></p>

    <!-- Hand display -->
    <div id="hand-display" class="bg-gray-50 border border-gray-200 rounded-lg p-4 mb-4 font-mono text-sm leading-7">
      <div><span class="suit-s font-bold mr-2">♠</span><span id="hand-s"></span></div>
      <div><span class="suit-h font-bold mr-2">♥</span><span id="hand-h"></span></div>
      <div><span class="suit-d font-bold mr-2">♦</span><span id="hand-d"></span></div>
      <div><span class="suit-c font-bold mr-2">♣</span><span id="hand-c"></span></div>
      <div class="mt-1 text-xs text-gray-400">
        HCP: <span id="hand-hcp"></span>
      </div>
    </div>

    <!-- Choices -->
    <div id="choices-area" class="grid grid-cols-2 gap-2"></div>

    <!-- Feedback -->
    <div id="feedback-area" class="mt-4 hidden rounded-lg p-3 text-sm">
      <div id="feedback-icon" class="text-xl mb-1"></div>
      <div id="feedback-text" class="font-semibold text-gray-800"></div>
      <div id="feedback-explain" class="text-gray-600 mt-1 text-xs"></div>
      <div id="feedback-hint" class="text-gray-400 mt-1 text-xs italic"></div>
    </div>
  </div>

  <!-- ── Navigation ── -->
  <div class="flex gap-3 justify-between">
    <button id="btn-restart"
            onclick="restartQuiz()"
            class="flex-1 py-2 rounded-lg border border-gray-300 text-gray-600 text-sm font-medium hover:bg-gray-50">
      {{ '↺ 重新開始' if locale == 'en' else '↺ 重新開始' }}
    </button>
    <button id="btn-next"
            onclick="nextQuestion()"
            disabled
            class="flex-2 flex-grow py-2 px-6 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:opacity-40 disabled:cursor-default">
      {{ 'Next →' if locale == 'en' else '下一題 →' }}
    </button>
  </div>

  <!-- ── Finish Screen (hidden initially) ── -->
  <div id="finish-screen" class="hidden bg-white rounded-xl shadow p-8 text-center mt-4">
    <div class="text-5xl mb-4">🎉</div>
    <h2 class="text-2xl font-bold text-gray-800 mb-2">
      {{ 'Quiz Complete!' if locale == 'en' else '練習完成！' }}
    </h2>
    <p class="text-gray-600 mb-4" id="final-score-text"></p>
    <button onclick="restartQuiz()"
            class="px-6 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700">
      {{ 'Play Again' if locale == 'en' else '再練一次' }}
    </button>
  </div>

</main>

<!-- ════ Quiz Data + JS ════ -->
<script>
const LOCALE = "{{ locale }}";
const quizData = {{ quiz_json }};
let questions = [];  // shuffled subset
let currentIdx = 0;
let score = 0;
let answered = false;

const LABELS = ["A", "B", "C", "D"];

// ── Utilities ──────────────────────────────────────────────
function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

// ── Initialise ─────────────────────────────────────────────
function startQuiz() {
  questions = shuffle([...quizData]);
  currentIdx = 0;
  score = 0;
  answered = false;
  document.getElementById('finish-screen').classList.add('hidden');
  document.getElementById('question-card').classList.remove('hidden');
  document.querySelector('.progress-bar').parentElement.classList.remove('hidden');
  showQuestion(currentIdx);
}

// ── Show a question ────────────────────────────────────────
function showQuestion(idx) {
  answered = false;
  const q = questions[idx];
  const total = questions.length;

  // Progress
  document.getElementById('progress-bar').style.width = `${(idx / total) * 100}%`;
  const ptLabel = LOCALE === 'en'
    ? `Question ${idx + 1} of ${total}`
    : `第 ${idx + 1} / ${total} 題`;
  document.getElementById('progress-text').textContent = ptLabel;

  // Score
  document.getElementById('score-display').textContent = `${score} / ${idx}`;

  // Context (auction sequence)
  const ctxArea = document.getElementById('context-area');
  const seqDisp = document.getElementById('sequence-display');
  if (q.sequence && q.sequence.length > 0) {
    ctxArea.classList.remove('hidden');
    seqDisp.innerHTML = q.sequence
      .map(b => `<span class="seq-badge bg-blue-100 text-blue-800">${b}</span>`)
      .join(' ');
  } else {
    ctxArea.classList.add('hidden');
    seqDisp.innerHTML = '';
  }

  // Question text
  document.getElementById('question-text').textContent = q.question;

  // Hand
  document.getElementById('hand-s').textContent = q.hand.spades.join(' ') || '—';
  document.getElementById('hand-h').textContent = q.hand.hearts.join(' ') || '—';
  document.getElementById('hand-d').textContent = q.hand.diamonds.join(' ') || '—';
  document.getElementById('hand-c').textContent = q.hand.clubs.join(' ') || '—';
  document.getElementById('hand-hcp').textContent = q.hand.hcp;

  // Choices
  const choicesArea = document.getElementById('choices-area');
  choicesArea.innerHTML = '';
  q.choices.forEach((bid, i) => {
    const btn = document.createElement('button');
    btn.className = 'choice-btn border-2 border-gray-200 rounded-lg p-3 text-left hover:border-blue-400 hover:bg-blue-50';
    btn.innerHTML = `<span class="font-bold text-gray-500 mr-2">${LABELS[i]}.</span>`
                  + `<span class="font-mono font-bold text-gray-800">${bid}</span>`;
    btn.setAttribute('data-bid', bid);
    btn.onclick = () => selectAnswer(bid);
    choicesArea.appendChild(btn);
  });

  // Feedback: hide
  const fb = document.getElementById('feedback-area');
  fb.classList.add('hidden');

  // Next: disable
  document.getElementById('btn-next').disabled = true;

  // Animate
  const card = document.getElementById('question-card');
  card.classList.remove('pop');
  void card.offsetWidth;
  card.classList.add('pop');
}

// ── Handle answer selection ────────────────────────────────
function selectAnswer(bid) {
  if (answered) return;
  answered = true;

  const q = questions[currentIdx];
  const correct = q.correct;
  const isCorrect = bid === correct;
  if (isCorrect) score++;

  // Colour the buttons
  const btns = document.querySelectorAll('.choice-btn');
  btns.forEach(btn => {
    const b = btn.getAttribute('data-bid');
    btn.disabled = true;
    if (b === correct) btn.classList.add('choice-correct');
    else if (b === bid && !isCorrect) btn.classList.add('choice-wrong');
  });

  // Show feedback
  const fb = document.getElementById('feedback-area');
  fb.classList.remove('hidden', 'bg-green-50', 'bg-red-50', 'border-green-200', 'border-red-200');
  fb.classList.add('border');
  if (isCorrect) {
    fb.classList.add('bg-green-50', 'border-green-200');
    document.getElementById('feedback-icon').textContent = '✅';
    document.getElementById('feedback-text').textContent =
      LOCALE === 'en' ? 'Correct!' : '答對了！';
  } else {
    fb.classList.add('bg-red-50', 'border-red-200');
    document.getElementById('feedback-icon').textContent = '❌';
    document.getElementById('feedback-text').textContent =
      LOCALE === 'en' ? `Wrong. Correct answer: ${correct}` : `答錯了。正確答案：${correct}`;
  }
  document.getElementById('feedback-explain').textContent = q.explanation || '';
  document.getElementById('feedback-hint').textContent = q.hint ? `(${q.hint})` : '';

  // Update score display
  document.getElementById('score-display').textContent = `${score} / ${currentIdx + 1}`;

  // Enable next
  document.getElementById('btn-next').disabled = false;
}

// ── Next question ──────────────────────────────────────────
function nextQuestion() {
  if (currentIdx + 1 >= questions.length) {
    showFinish();
    return;
  }
  currentIdx++;
  showQuestion(currentIdx);
}

// ── Finish screen ──────────────────────────────────────────
function showFinish() {
  document.getElementById('question-card').classList.add('hidden');
  const pct = Math.round(score / questions.length * 100);
  const msg = LOCALE === 'en'
    ? `You scored ${score} out of ${questions.length} (${pct}%)`
    : `您答對 ${score} / ${questions.length} 題（${pct}%）`;
  document.getElementById('final-score-text').textContent = msg;
  document.getElementById('finish-screen').classList.remove('hidden');
}

// ── Restart ────────────────────────────────────────────────
function restartQuiz() {
  startQuiz();
}

// ── Boot ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', startQuiz);
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_quiz(
    doc: BBDSLDocument,
    output_path: Path | None = None,
    n: int = 20,
    question_types: list[str] | None = None,
    locale: str = "en",
    title: str | None = None,
    seed: int | None = None,
) -> str:
    """Export a BBDSLDocument as an interactive HTML quiz.

    Args:
        doc: The BBDSL document.
        output_path: If given, write to this file.
        n: Maximum number of quiz questions.
        question_types: ["opening"], ["response"], or None for both.
        locale: 'en' or 'zh-TW'.
        title: Override page title.
        seed: Random seed for reproducibility.

    Returns:
        The HTML string.
    """
    system_name = _t(doc.system.name, locale)
    page_title = title or f"{system_name} — {'Bidding Quiz' if locale == 'en' else '叫牌練習'}"

    # Generate questions
    questions = generate_quiz(
        doc,
        n=n,
        question_types=question_types,
        locale=locale,
        seed=seed,
    )

    quiz_json = json.dumps(
        [q.to_dict() for q in questions],
        ensure_ascii=False,
        indent=None,
    )

    # Render
    env = Environment(loader=BaseLoader(), autoescape=False)  # JSON in <script>
    tmpl = env.from_string(_QUIZ_TEMPLATE)
    html = tmpl.render(
        page_title=page_title,
        system_name=system_name,
        locale=locale,
        quiz_json=quiz_json,
        n_questions=len(questions),
    )

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding="utf-8")

    return html
