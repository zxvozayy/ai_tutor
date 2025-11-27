# app/ui/placement_test_dialog.py

from __future__ import annotations

from typing import List, Dict, Any, Optional

from PySide6 import QtWidgets, QtCore

from app.services.db_supabase import save_placement_result


Question = Dict[str, Any]
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


# ---------------------------------------------------------------------
# Question bank (24 items: 4 per level, grammar + vocab + light reading)
# You can later move this to Supabase / JSON if needed.
# ---------------------------------------------------------------------
QUESTIONS: List[Question] = [
    # ----- A1 -----
    {
        "id": 1,
        "text": "I ___ a student.",
        "options": ["am", "is", "are"],
        "correct_index": 0,
        "level": "A1",
        "section": "grammar",
    },
    {
        "id": 2,
        "text": "She ___ from Turkey.",
        "options": ["is", "are", "be"],
        "correct_index": 0,
        "level": "A1",
        "section": "grammar",
    },
    {
        "id": 3,
        "text": "Choose the best option: \"What is your name?\" – \"___ name is Berkay.\"",
        "options": ["My", "I", "Me"],
        "correct_index": 0,
        "level": "A1",
        "section": "vocab",
    },
    {
        "id": 4,
        "text": "We have English class ___ Monday and Wednesday.",
        "options": ["on", "in", "at"],
        "correct_index": 0,
        "level": "A1",
        "section": "grammar",
    },

    # ----- A2 -----
    {
        "id": 5,
        "text": "I usually go to school ___ bus.",
        "options": ["on", "by", "with"],
        "correct_index": 1,
        "level": "A2",
        "section": "grammar",
    },
    {
        "id": 6,
        "text": "We didn't ___ any homework yesterday.",
        "options": ["have", "had", "having"],
        "correct_index": 0,
        "level": "A2",
        "section": "grammar",
    },
    {
        "id": 7,
        "text": "Choose the best option: \"I’m tired. Let’s ___ a break.\"",
        "options": ["make", "do", "take"],
        "correct_index": 2,
        "level": "A2",
        "section": "vocab",
    },
    {
        "id": 8,
        "text": "I have lived in this city ___ three years.",
        "options": ["since", "for", "during"],
        "correct_index": 1,
        "level": "A2",
        "section": "grammar",
    },

    # ----- B1 -----
    {
        "id": 9,
        "text": "If it ___ tomorrow, we will stay at home.",
        "options": ["rains", "rained", "is raining"],
        "correct_index": 0,
        "level": "B1",
        "section": "grammar",
    },
    {
        "id": 10,
        "text": "She has been working here ___ 2019.",
        "options": ["since", "for", "from"],
        "correct_index": 0,
        "level": "B1",
        "section": "grammar",
    },
    {
        "id": 11,
        "text": "Choose the best option: \"The exam was not as difficult as I ___.\"",
        "options": ["expected", "expect", "was expecting"],
        "correct_index": 0,
        "level": "B1",
        "section": "grammar",
    },
    {
        "id": 12,
        "text": "Which sentence is the most natural?",
        "options": [
            "I am agree with you.",
            "I agree with you.",
            "I am agreeing with you."
        ],
        "correct_index": 1,
        "level": "B1",
        "section": "vocab",
    },

    # ----- B2 -----
    {
        "id": 13,
        "text": "If he ___ earlier, he would have caught the train.",
        "options": ["left", "had left", "has left"],
        "correct_index": 1,
        "level": "B2",
        "section": "grammar",
    },
    {
        "id": 14,
        "text": "The results were not as good as we had ___.",
        "options": ["expected", "expect", "expecting"],
        "correct_index": 0,
        "level": "B2",
        "section": "grammar",
    },
    {
        "id": 15,
        "text": "Choose the best option: \"The company is trying to ___ its costs.\"",
        "options": ["decrease", "low", "down"],
        "correct_index": 0,
        "level": "B2",
        "section": "vocab",
    },
    {
        "id": 16,
        "text": "Choose the best option: \"He was ___ for the position because of his experience.\"",
        "options": ["qualified", "quality", "qualifying"],
        "correct_index": 0,
        "level": "B2",
        "section": "vocab",
    },

    # ----- C1 -----
    {
        "id": 17,
        "text": "Her argument was so ___ that nobody could refute it.",
        "options": ["compelling", "compelled", "compulsion"],
        "correct_index": 0,
        "level": "C1",
        "section": "vocab",
    },
    {
        "id": 18,
        "text": "The company needs to ___ its strategy to stay competitive.",
        "options": ["revise", "reviewed", "revision"],
        "correct_index": 0,
        "level": "C1",
        "section": "vocab",
    },
    {
        "id": 19,
        "text": "Choose the best option: \"Although the task was challenging, she managed to complete it ___ time.\"",
        "options": ["on", "in", "with"],
        "correct_index": 0,
        "level": "C1",
        "section": "grammar",
    },
    {
        "id": 20,
        "text": "Choose the best option: \"The lecture was so ___ that many students lost interest.\"",
        "options": ["tedious", "tiring", "bored"],
        "correct_index": 0,
        "level": "C1",
        "section": "vocab",
    },

    # ----- C2 -----
    {
        "id": 21,
        "text": "His explanation was so ___ that even experts were impressed.",
        "options": ["lucid", "lucidity", "lucidly"],
        "correct_index": 0,
        "level": "C2",
        "section": "vocab",
    },
    {
        "id": 22,
        "text": "She spoke with such ___ that the audience remained silent.",
        "options": ["gravitas", "gravity", "grave"],
        "correct_index": 0,
        "level": "C2",
        "section": "vocab",
    },
    {
        "id": 23,
        "text": "Choose the best option: \"The policy had a number of unintended ___ on small businesses.\"",
        "options": ["repercussions", "repeats", "replacements"],
        "correct_index": 0,
        "level": "C2",
        "section": "vocab",
    },
    {
        "id": 24,
        "text": "Choose the best option: \"His research offers a highly ___ perspective on the issue.\"",
        "options": ["nuanced", "normal", "narrow"],
        "correct_index": 0,
        "level": "C2",
        "section": "vocab",
    },
]


# ---------------------------------------------------------------------
# CEFR estimation logic (simple, similar spirit to many online tests)
# ---------------------------------------------------------------------
def estimate_level(per_level: Dict[str, Dict[str, int]]) -> str:
    """
    per_level = {
      'A1': {'correct': x, 'total': y},
      ...
    }

    Logic:
      - compute accuracy per band
      - find highest level where:
           accuracy(level) >= 0.6
        and all lower levels >= 0.5
      - if none, fall back stepwise.
    """
    ratio = {
        lvl: (
                per_level.get(lvl, {}).get("correct", 0)
                / max(1, per_level.get(lvl, {}).get("total", 0))
        )
        for lvl in LEVELS
    }

    def ok(l: str, thr: float) -> bool:
        return ratio[l] >= thr

    # climb ladder cautiously
    # 1) if A2 is weak -> A1
    if not ok("A2", 0.5):
        return "A1"

    # 2) A1+A2 okay but B1 weak -> A2
    if ok("A1", 0.5) and ok("A2", 0.6) and not ok("B1", 0.5):
        return "A2"

    # 3) up to B1 strong, B2 weak
    if ok("B1", 0.6) and not ok("B2", 0.5):
        return "B1"

    # 4) up to B2 strong, C1 weak
    if ok("B2", 0.6) and not ok("C1", 0.5):
        return "B2"

    # 5) up to C1 strong, C2 weak
    if ok("C1", 0.6) and not ok("C2", 0.5):
        return "C1"

    # 6) otherwise C2 (strong everywhere)
    return "C2"


# ---------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------
class PlacementTestDialog(QtWidgets.QDialog):
    """
    CEFR placement test dialog (A1–C2, ~5–8 minutes).
    Usage:
        dlg = PlacementTestDialog(parent)
        level = dlg.exec_and_get_level()
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Placement Test – English Level (A1–C2)")
        self.resize(720, 440)
        self.setModal(True)

        self._questions: List[Question] = QUESTIONS
        self._index: int = 0
        self._answers: Dict[int, int] = {}  # question_id -> chosen option index
        self._estimated_level: Optional[str] = None

        self._build_ui()
        self._refresh_ui()

    # ---------- public helper ----------

    def exec_and_get_level(self) -> Optional[str]:
        """Run dialog; return CEFR level string or None if cancelled."""
        if self.exec() == QtWidgets.QDialog.Accepted:
            return self._estimated_level
        return None

    # ---------- UI build ----------

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        title = QtWidgets.QLabel("Let’s quickly estimate your English level.")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-size:18px; font-weight:600;")
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "You will answer 24 multiple-choice questions.\n"
            "There is no time limit. Just choose the best option."
        )
        subtitle.setAlignment(QtCore.Qt.AlignCenter)
        subtitle.setStyleSheet("color:#bdc3c7;")
        layout.addWidget(subtitle)

        self.progress_label = QtWidgets.QLabel()
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, len(self._questions))

        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        self.question_label = QtWidgets.QLabel()
        self.question_label.setWordWrap(True)
        self.question_label.setStyleSheet("font-size:15px; margin-top:8px;")
        layout.addWidget(self.question_label)

        self.options_group = QtWidgets.QButtonGroup(self)
        self.options_group.setExclusive(True)
        self.options_layout = QtWidgets.QVBoxLayout()

        options_box = QtWidgets.QGroupBox("Choose the best answer")
        options_box.setLayout(self.options_layout)
        layout.addWidget(options_box)

        btn_row = QtWidgets.QHBoxLayout()
        self.back_btn = QtWidgets.QPushButton("Back")
        self.next_btn = QtWidgets.QPushButton("Next")
        self.finish_btn = QtWidgets.QPushButton("Finish")
        self.finish_btn.setEnabled(False)

        btn_row.addWidget(self.back_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.next_btn)
        btn_row.addWidget(self.finish_btn)
        layout.addLayout(btn_row)

        self.back_btn.clicked.connect(self._go_back)
        self.next_btn.clicked.connect(self._go_next)
        self.finish_btn.clicked.connect(self._finish)

    # ---------- navigation ----------

    def _refresh_ui(self):
        q = self._questions[self._index]
        total = len(self._questions)
        self.progress_label.setText(f"Question {self._index + 1} of {total}")
        self.progress_bar.setValue(self._index + 1)
        self.question_label.setText(q["text"])

        # clear old options
        for btn in self.options_group.buttons():
            self.options_group.removeButton(btn)
            btn.setParent(None)
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        chosen = self._answers.get(q["id"])

        for i, opt in enumerate(q["options"]):
            rb = QtWidgets.QRadioButton(opt)
            self.options_group.addButton(rb, i)
            self.options_layout.addWidget(rb)
            if chosen is not None and chosen == i:
                rb.setChecked(True)

        self.back_btn.setEnabled(self._index > 0)
        self.next_btn.setEnabled(self._index < total - 1)
        self.finish_btn.setEnabled(self._index == total - 1)

    def _save_current_answer(self):
        q = self._questions[self._index]
        checked_id = self.options_group.checkedId()
        if checked_id != -1:
            self._answers[q["id"]] = checked_id

    def _go_back(self):
        self._save_current_answer()
        if self._index > 0:
            self._index -= 1
            self._refresh_ui()

    def _go_next(self):
        self._save_current_answer()
        if self.options_group.checkedId() == -1:
            QtWidgets.QMessageBox.warning(
                self, "Answer required", "Please choose an option before continuing."
            )
            return
        if self._index < len(self._questions) - 1:
            self._index += 1
            self._refresh_ui()

    def _finish(self):
        self._save_current_answer()

        # compute per-level stats
        per_level: Dict[str, Dict[str, int]] = {}
        total_correct = 0
        for q in self._questions:
            lvl = q["level"]
            st = per_level.setdefault(lvl, {"correct": 0, "total": 0})
            st["total"] += 1
            chosen = self._answers.get(q["id"])
            if chosen is not None and chosen == q["correct_index"]:
                st["correct"] += 1
                total_correct += 1

        level = estimate_level(per_level)
        self._estimated_level = level

        # pack answers for analytics
        answers_blob: Dict[str, Any] = {}
        for q in self._questions:
            answers_blob[str(q["id"])] = {
                "question": q["text"],
                "level": q["level"],
                "chosen": self._answers.get(q["id"]),
                "correct_index": q["correct_index"],
            }

        try:
            save_placement_result(
                estimated_level=level,
                total_correct=total_correct,
                total_questions=len(self._questions),
                per_level=per_level,
                answers=answers_blob,
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Save error", f"Could not save result to server:\n{e}"
            )

        QtWidgets.QMessageBox.information(
            self,
            "Your level",
            f"We estimate your English level as <b>{level}</b>.\n"
            "You can update it later if it feels inaccurate.",
        )
        self.accept()


# Optional: local test run
if __name__ == "__main__":
    import sys
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication(sys.argv)
    dlg = PlacementTestDialog()
    lvl = dlg.exec_and_get_level()
    print("Selected level:", lvl)
