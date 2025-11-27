# app/ui/listening_widget.py

import os
from PySide6 import QtWidgets, QtCore, QtMultimedia
from app.listening_quiz_data import LISTENING_QUIZZES
from app.services.user_profile import get_user_level

# Disable ffmpeg spam
os.environ["QT_LOGGING_RULES"] = "qt.multimedia.ffmpeg.debug=false;qt.multimedia.ffmpeg.info=false"

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
AUDIO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "listening_audio"))


def normalize_level(raw: str, default="B1") -> str:
    if not raw:
        return default
    s = raw.upper().strip()
    for lvl in LEVELS:
        if s.startswith(lvl):
            return lvl
    return default


class ListeningPracticeWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # -------- LEVEL + QUIZ --------
        raw_level = get_user_level(default="B1")
        self.level = normalize_level(raw_level)
        self.quiz = self._pick_quiz(self.level)

        layout = QtWidgets.QVBoxLayout(self)

        # -------- HEADER --------
        header = QtWidgets.QHBoxLayout()
        self.level_label = QtWidgets.QLabel(f"Level: {self.level}")
        self.title_label = QtWidgets.QLabel(self.quiz["title"] if self.quiz else "No quiz available")
        header.addWidget(self.level_label)
        header.addStretch(1)
        header.addWidget(self.title_label)
        layout.addLayout(header)

        # -------- AUDIO CONTROLS --------
        audio_row = QtWidgets.QHBoxLayout()

        self.play_btn = QtWidgets.QPushButton("▶ Play")
        self.pause_btn = QtWidgets.QPushButton("⏸ Pause")
        self.stop_btn = QtWidgets.QPushButton("⏹ Stop")

        self.play_btn.clicked.connect(self._play_audio)
        self.pause_btn.clicked.connect(self._pause_audio)
        self.stop_btn.clicked.connect(self._stop_audio)

        audio_row.addWidget(self.play_btn)
        audio_row.addWidget(self.pause_btn)
        audio_row.addWidget(self.stop_btn)

        # Progress slider
        self.progress = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.progress.setRange(0, 0)
        self.progress.sliderMoved.connect(self._seek_audio)
        audio_row.addWidget(self.progress, 1)

        # Time label
        self.time_label = QtWidgets.QLabel("00:00 / 00:00")
        audio_row.addWidget(self.time_label)

        self.status_label = QtWidgets.QLabel("")
        audio_row.addWidget(self.status_label)

        layout.addLayout(audio_row)

        # -------- SCROLL AREA FOR QUESTIONS --------
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll, 1)

        self.q_container = QtWidgets.QWidget()
        self.q_layout = QtWidgets.QVBoxLayout(self.q_container)
        scroll.setWidget(self.q_container)

        self._question_widgets = []
        self._build_questions_ui()

        # -------- SUBMIT ROW --------
        row = QtWidgets.QHBoxLayout()
        self.submit_btn = QtWidgets.QPushButton("Check Answers")
        self.submit_btn.clicked.connect(self._grade)
        self.result_label = QtWidgets.QLabel("")

        row.addWidget(self.submit_btn)
        row.addWidget(self.result_label)
        layout.addLayout(row)

        # -------- AUDIO PLAYER --------
        device = QtMultimedia.QMediaDevices.defaultAudioOutput()
        self.audio_out = QtMultimedia.QAudioOutput(device)
        self.audio_out.setVolume(1.0)

        self.player = QtMultimedia.QMediaPlayer()
        self.player.setAudioOutput(self.audio_out)

        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)

    # ----------------------------------------------------
    # Formatting helper
    # ----------------------------------------------------
    def _fmt(self, ms: int):
        if ms < 0:
            return "00:00"
        s = ms // 1000
        m = s // 60
        s %= 60
        return f"{m:02d}:{s:02d}"

    # ----------------------------------------------------
    # Quiz picker
    # ----------------------------------------------------
    def _pick_quiz(self, level):
        if level in LISTENING_QUIZZES and LISTENING_QUIZZES[level]:
            return LISTENING_QUIZZES[level][0]
        for lvl in LEVELS:
            if LISTENING_QUIZZES.get(lvl):
                return LISTENING_QUIZZES[lvl][0]
        return None

    # ----------------------------------------------------
    # Build questions
    # ----------------------------------------------------
    def _build_questions_ui(self):
        # Remove old items
        while self.q_layout.count():
            item = self.q_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._question_widgets.clear()

        if not self.quiz:
            self.q_layout.addWidget(QtWidgets.QLabel("No quiz available."))
            return

        for idx, q in enumerate(self.quiz["questions"]):

            # --- Outer wrapper (NO styling touches this) ---
            wrapper = QtWidgets.QFrame()
            wrapper_layout = QtWidgets.QVBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)

            # --- Inner frame (THIS gets green/red border) ---
            frame = QtWidgets.QFrame()
            frame.setObjectName("highlightFrame")
            frame.setStyleSheet("#highlightFrame { border: none; }")

            frame_layout = QtWidgets.QVBoxLayout(frame)
            frame_layout.setContentsMargins(10, 10, 10, 10)

            # --- Question title ---
            label = QtWidgets.QLabel(f"Q{idx+1}. {q['text']}")
            label.setStyleSheet("font-size: 15px; padding-bottom: 4px;")
            frame_layout.addWidget(label)

            # --- Radio buttons ---
            group = QtWidgets.QButtonGroup(frame)
            group.setExclusive(True)

            for opt_i, opt_text in enumerate(q["options"]):
                rb = QtWidgets.QRadioButton(opt_text)
                group.addButton(rb, opt_i)
                frame_layout.addWidget(rb)

            wrapper_layout.addWidget(frame)
            self.q_layout.addWidget(wrapper)

            self._question_widgets.append((frame, group, q["correct_index"]))

        self.q_layout.addStretch(1)

    # ----------------------------------------------------
    # Audio
    # ----------------------------------------------------
    def _resolve_audio(self):
        file = self.quiz.get("audio_file")
        if not file:
            return None

        p = os.path.join(AUDIO_ROOT, self.level, file)
        if os.path.exists(p):
            return p

        for lvl in LEVELS:
            cand = os.path.join(AUDIO_ROOT, lvl, file)
            if os.path.exists(cand):
                return cand

        return None

    def _play_audio(self):
        path = self._resolve_audio()
        if not path:
            self.status_label.setText("Audio missing.")
            return

        url = QtCore.QUrl.fromLocalFile(path)
        self.player.setSource(url)
        self.player.play()
        self.status_label.setText("Playing...")

    def _pause_audio(self):
        if self.player.playbackState() == QtMultimedia.QMediaPlayer.PlayingState:
            self.player.pause()
            self.status_label.setText("Paused")
        else:
            self.player.play()
            self.status_label.setText("Resumed")

    def _stop_audio(self):
        self.player.stop()
        self.status_label.setText("Stopped")

    def _seek_audio(self, pos):
        self.player.setPosition(pos)

    def _on_position(self, pos):
        self.progress.blockSignals(True)
        self.progress.setValue(pos)
        self.progress.blockSignals(False)

        total = self.player.duration()
        self.time_label.setText(f"{self._fmt(pos)} / {self._fmt(total)}")

    def _on_duration(self, dur):
        self.progress.setRange(0, dur)
        self.time_label.setText(f"{self._fmt(self.player.position())} / {self._fmt(dur)}")

    # ----------------------------------------------------
    # Answer grading (with perfect outline borders)
    # ----------------------------------------------------
    def _grade(self):
        correct = 0
        unanswered = 0

        for frame, group, correct_index in self._question_widgets:
            # reset
            frame.setStyleSheet("#highlightFrame { border: none; }")

            chosen = group.checkedId()
            if chosen == -1:
                unanswered += 1
                continue

            if chosen == correct_index:
                correct += 1
                frame.setStyleSheet("""
                    #highlightFrame {
                        border: 2px solid #27ae60;
                        border-radius: 8px;
                    }
                """)
            else:
                frame.setStyleSheet("""
                    #highlightFrame {
                        border: 2px solid #c0392b;
                        border-radius: 8px;
                    }
                """)

        total = len(self._question_widgets)
        self.result_label.setText(f"Score: {correct}/{total} | Unanswered: {unanswered}")

