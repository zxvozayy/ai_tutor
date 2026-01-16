from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QGroupBox, QRadioButton, QButtonGroup,
    QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt

from app.modules.reading_repo import list_reading_sets, load_reading_set


class ReadingPracticeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.level_cb = QComboBox()
        self.set_cb = QComboBox()
        self.load_btn = QPushButton("Load")
        self.check_btn = QPushButton("Check Answers")

        # Title line (optional)
        self.title_lbl = QLabel("")
        self.title_lbl.setStyleSheet("font-weight:600; color:#184e77;")

        self.passage = QTextEdit()
        self.passage.setReadOnly(True)

        self.questions_container = QWidget()
        self.questions_layout = QVBoxLayout(self.questions_container)
        self.questions_layout.setAlignment(Qt.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.questions_container)

        top = QHBoxLayout()
        top.addWidget(QLabel("Level:"))
        top.addWidget(self.level_cb)
        top.addWidget(QLabel("Set:"))
        top.addWidget(self.set_cb)
        top.addWidget(self.load_btn)
        top.addStretch(1)
        top.addWidget(self.check_btn)

        layout = QVBoxLayout(self)
        layout.addLayout(top)

        layout.addWidget(self.title_lbl)
        layout.addWidget(QLabel("Passage:"))
        layout.addWidget(self.passage, 2)
        layout.addWidget(QLabel("Questions:"))
        layout.addWidget(scroll, 3)

        self.current_data = None
        self.button_groups = []          # list[(qid, QButtonGroup)]
        self.question_boxes = {}         # qid -> QGroupBox

        self._init_levels()

        self.level_cb.currentTextChanged.connect(self._reload_sets)
        self.load_btn.clicked.connect(self._load_selected_set)
        self.check_btn.clicked.connect(self._check_answers)

        # ✅ garanti başlangıç
        self.level_cb.setCurrentText("A1")
        self._reload_sets("A1")

    def _init_levels(self):
        for lvl in ["A1", "A2", "B1", "B2", "C1", "C2"]:
            self.level_cb.addItem(lvl)

    def _reload_sets(self, level: str):
        self.set_cb.clear()
        paths = list_reading_sets(level) or []

        if not paths:
            self.set_cb.addItem("(No sets found)")
            self.set_cb.setItemData(0, "", Qt.UserRole)
            return

        for i, p in enumerate(paths, start=1):
            self.set_cb.addItem(f"Test {i}")
            self.set_cb.setItemData(self.set_cb.count() - 1, str(p), Qt.UserRole)

    def _clear_questions(self):
        while self.questions_layout.count():
            item = self.questions_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.button_groups.clear()
        self.question_boxes.clear()

    # ---------- Schema helpers ----------
    def _get_passage(self, data: dict) -> str:
        return (data.get("passage") or data.get("passage_text") or "").strip()

    def _get_title(self, data: dict) -> str:
        t = (data.get("title") or "").strip()
        lvl = (data.get("level") or "").strip()
        if t and lvl:
            return f"{lvl} — {t}"
        if t:
            return t
        return ""

    def _get_options(self, q: dict) -> list:
        opts = q.get("options")
        if opts is None:
            opts = q.get("choices")
        if not isinstance(opts, list):
            return []
        return opts

    def _get_answer_index(self, q: dict) -> int:
        # supports: answer_index, answer, correct_index
        ans = q.get("answer_index")
        if ans is None:
            ans = q.get("answer")
        if ans is None:
            ans = q.get("correct_index")
        try:
            return int(ans)
        except Exception:
            return -1

    def _get_qid(self, q: dict, fallback_i: int) -> str:
        qid = q.get("id")
        if qid is None or str(qid).strip() == "":
            return f"q{fallback_i}"
        return str(qid)

    def _load_selected_set(self):
        print("DEBUG set data(path):", self.set_cb.currentData(Qt.UserRole))
        print("DEBUG level:", self.level_cb.currentText())
        print("DEBUG set text:", self.set_cb.currentText())
        print("DEBUG set data(path):", self.set_cb.currentData())

        path = self.set_cb.currentData(Qt.UserRole)

        if not path:
            QMessageBox.warning(
                self,
                "Reading",
                "No set selected / no set found.\n"
                "Expected: app/reading/<LEVEL>/*.json"
            )
            return

        try:
            data = load_reading_set(path)
        except Exception as e:
            QMessageBox.critical(self, "Reading", f"Failed to load JSON:\n{e}")
            return

        if not isinstance(data, dict):
            QMessageBox.critical(self, "Reading", "Invalid JSON format (expected object).")
            return

        print("Loaded keys:", list(data.keys()))
        print("questions len:", len((data.get("questions") or [])))
        self.current_data = data

        # Title + passage
        self.title_lbl.setText(self._get_title(data))
        self.passage.setPlainText(self._get_passage(data))

        self._clear_questions()

        questions = data.get("questions", [])
        if not isinstance(questions, list):
            questions = []

        # Build UI
        for i, q in enumerate(questions, start=1):
            if not isinstance(q, dict):
                continue

            qid = self._get_qid(q, i)
            qtext = (q.get("question") or "").strip()
            if not qtext:
                qtext = f"Question {i}"

            box = QGroupBox(qtext)
            box.setStyleSheet("")  # reset
            self.question_boxes[qid] = box

            v = QVBoxLayout(box)

            group = QButtonGroup(box)
            group.setExclusive(True)

            opts = self._get_options(q)
            for idx, opt in enumerate(opts):
                rb = QRadioButton(str(opt))
                rb.setProperty("answer_index", idx)
                group.addButton(rb)
                v.addWidget(rb)

            # If no options, show a warning line inside the box
            if not opts:
                warn = QLabel("No options found for this question (check JSON keys: options/choices).")
                warn.setStyleSheet("color:#34a0a4; font-size:11px;")
                v.addWidget(warn)

            self.questions_layout.addWidget(box)
            self.button_groups.append((qid, group))

        self.questions_layout.addStretch(1)

        # Extra safety: if everything ended up empty
        if not questions:
            QMessageBox.information(self, "Reading", "This set has no questions.")

    def _check_answers(self):
        if not self.current_data:
            QMessageBox.information(self, "Reading", "Please load a set first.")
            return

        questions = self.current_data.get("questions", [])
        if not isinstance(questions, list):
            questions = []

        # Map by qid (with fallback generation)
        qmap = {}
        for i, q in enumerate(questions, start=1):
            if isinstance(q, dict):
                qmap[self._get_qid(q, i)] = q

        correct = 0
        total = 0
        unanswered = 0

        STYLE_OK = """
            QGroupBox {
                border: 2px solid #99d98c;
                border-radius: 10px;
                margin-top: 8px;
                padding: 8px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        """
        STYLE_BAD = """
            QGroupBox {
                border: 2px solid #e74c3c;
                border-radius: 10px;
                margin-top: 8px;
                padding: 8px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        """
        STYLE_EMPTY = """
            QGroupBox {
                border: 2px solid #34a0a4;
                border-radius: 10px;
                margin-top: 8px;
                padding: 8px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
        """

        for qid, group in self.button_groups:
            q = qmap.get(qid)
            if not q:
                continue

            total += 1
            ans = self._get_answer_index(q)

            box = self.question_boxes.get(qid)

            chosen = group.checkedButton()
            if chosen is None:
                unanswered += 1
                if box:
                    box.setStyleSheet(STYLE_EMPTY)
                continue

            chosen_idx = chosen.property("answer_index")

            if chosen_idx == ans:
                correct += 1
                if box:
                    box.setStyleSheet(STYLE_OK)
            else:
                if box:
                    box.setStyleSheet(STYLE_BAD)

        QMessageBox.information(
            self,
            "Result",
            f"Score: {correct}/{total} | Unanswered: {unanswered}"
        )