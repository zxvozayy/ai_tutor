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
            self.set_cb.addItem("(No sets found)", "")
            return

        # UI'da "Test 1 / Test 2 ..." göster, data'da gerçek path kalsın
        for i, p in enumerate(paths, start=1):
            self.set_cb.addItem(f"Test {i}", str(p))

    def _clear_questions(self):
        while self.questions_layout.count():
            item = self.questions_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.button_groups.clear()
        self.question_boxes.clear()

    def _load_selected_set(self):
        path = self.set_cb.currentData()

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

        self.current_data = data

        self.passage.setPlainText(data.get("passage", ""))

        self._clear_questions()

        for q in data.get("questions", []):
            qid = q.get("id", "")

            box = QGroupBox(q.get("question", ""))
            box.setStyleSheet("")  # reset
            self.question_boxes[qid] = box

            v = QVBoxLayout(box)

            group = QButtonGroup(box)
            group.setExclusive(True)

            for idx, opt in enumerate(q.get("options", [])):
                rb = QRadioButton(opt)
                rb.setProperty("answer_index", idx)
                group.addButton(rb)
                v.addWidget(rb)

            self.questions_layout.addWidget(box)
            self.button_groups.append((qid, group))

        self.questions_layout.addStretch(1)

    def _check_answers(self):
        if not self.current_data:
            QMessageBox.information(self, "Reading", "Please load a set first.")
            return

        qmap = {q.get("id", ""): q for q in self.current_data.get("questions", [])}

        correct = 0
        total = 0
        unanswered = 0

        STYLE_OK = """
            QGroupBox {
                border: 2px solid #2ecc71;
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
                border: 2px solid #95a5a6;
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
            ans = q.get("answer_index", -1)

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