import sys
import re
import threading
import urllib.parse
from collections import Counter

from PySide6 import QtWidgets, QtCore, QtGui

from app.ui.listening_widget import ListeningPracticeWidget
from app.ui.placement_test_dialog import PlacementTestDialog

# 🔤 Vocab features
from app.ui.vocab_browser import VocabBrowser
from app.ui.vocab_list_widget import VocabListWidget
from app.modules.vocab_utils import find_new_vocabulary
from app.modules.vocab_store import get_known_words_set, add_word

# ✨ Supabase chat persistence + profile + learning events
from app.services.db_supabase import (
    get_or_create_default_session,
    add_message,
    list_messages,
    list_user_sessions,
    create_session,
    rename_session,
    delete_session,
    current_user_id,
    get_current_profile,
    get_recent_learning_events,
)

# Azure STT
from app.engines.cloud_stt_azure import AzureSTTEngine as STTEngine

try:
    from app.engines.pron_eval import flag_tricky_words
except Exception:
    def flag_tricky_words(*args, **kwargs):
        return []

LANG_TAGS = ("[en-US]", "[tr-TR]", "[en-GB]", "[tr]", "[en]")


def strip_lang_tags(s: str) -> str:
    out = s
    for t in LANG_TAGS:
        out = out.replace(t, "")
    return out.strip()


def run_placement_test_if_needed(parent_widget: QtWidgets.QWidget) -> None:
    """
    If current user has no CEFR level, show the placement test dialog once.
    """
    try:
        profile = get_current_profile()
    except Exception:
        # no login / network / RLS error → silently ignore
        return

    if profile and profile.get("cefr_level"):
        return

    dlg = PlacementTestDialog(parent_widget)
    level = dlg.exec_and_get_level()
    if level:
        QtWidgets.QMessageBox.information(
            parent_widget,
            "Level set",
            f"Your level is set to <b>{level}</b>.\n"
            "We'll adapt practice to this level.",
        )


class MainWindow(QtWidgets.QMainWindow):
    bot_text_signal = QtCore.Signal(str)
    stt_text_signal = QtCore.Signal(str, bool, list)
    vocab_explained_signal = QtCore.Signal(str, str)  # word, explanation

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.user_id = current_user_id()

        self.setWindowTitle("AI Tutor – Chat + Voice (Azure + Gemini)")
        self.resize(1120, 680)

        # ---- Global stylesheet ----
        self.setStyleSheet("""
            QWidget {
                background-color: #3c3e30;
                color: #eceff1;
            }
            QLineEdit {
                background-color: #34495e;
                color: #ecf0f1;
                border: 1px solid #3c3e30;
                border-radius: 4px;
                padding: 6px 8px;
            }
            QPushButton {
                background-color: #2d4369;
                border: 1px solid #3c3e30;
                padding: 6px 10px;
            }
            QPushButton:checked {
                background-color: #6c5ce7;
            }
            QComboBox {
                background-color: #2d3436;
                color: #ecf0f1;
                border: 1px solid #7f8c8d;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QListWidget {
                background-color: #2b2b2b;
                color: #f5f5f5;
                border: 1px solid #7f8c8d;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background-color: #91AEC1;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #444;
                color: #ffffff;
            }
        """)

        # =========================================================
        #  CENTRAL WIDGET
        # =========================================================
        central = QtWidgets.QWidget(self)
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        # ---------------- TOPIC CATEGORIES + PERSONA ----------------
        self.topic_prompts = {
            "Daily Life": {
                "At the Restaurant": "You are a waiter talking to a customer in a restaurant.",
                "Shopping": "You are a shop assistant helping a customer buy something.",
                "Ordering Coffee": "You are a barista taking an order at a coffee shop.",
                "Making New Friends": "You are meeting someone new and having a casual conversation.",
                "Talking about Hobbies": "You are casually chatting about hobbies and free-time activities."
            },
            "Travel": {
                "At the Airport": "You are a flight attendant helping a traveler with their flight.",
                "Hotel Check-in": "You are a hotel receptionist checking in a guest.",
                "Traveling Abroad": "You are helping someone plan or enjoy their trip abroad.",
                "Planning a Trip": "You are discussing travel plans and destinations with a friend."
            },
            "Professional": {
                "Job Interview": "You are the interviewer asking questions in a job interview.",
                "Giving a Presentation": "You are a student presenting a project to classmates.",
                "Doctor Appointment": "You are a doctor having a check-up conversation with a patient.",
                "Workplace Chat": "You are having a friendly chat with a coworker."
            }
        }

        # ===== Left: sessions panel =====
        left = QtWidgets.QWidget()
        left_v = QtWidgets.QVBoxLayout(left)
        left_v.setContentsMargins(8, 8, 8, 8)
        left_v.setSpacing(8)

        header = QtWidgets.QLabel("Chats")
        header.setStyleSheet("font-weight:600;")

        self.session_list = QtWidgets.QListWidget()
        self.session_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.session_list.itemSelectionChanged.connect(self._on_session_selected)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_new = QtWidgets.QPushButton("New")
        self.btn_ren = QtWidgets.QPushButton("Rename")
        self.btn_del = QtWidgets.QPushButton("Delete")
        self.btn_export = QtWidgets.QPushButton("Save to TXT")
        self.btn_weak = QtWidgets.QPushButton("Weak Points")

        self.btn_new.clicked.connect(self._new_chat)
        self.btn_ren.clicked.connect(self._rename_chat)
        self.btn_del.clicked.connect(self._delete_chat)
        self.btn_export.clicked.connect(self._export_chat)
        self.btn_weak.clicked.connect(self._show_weak_points)

        btn_row.addWidget(self.btn_new)
        btn_row.addWidget(self.btn_ren)
        btn_row.addWidget(self.btn_del)
        btn_row.addWidget(self.btn_export)
        btn_row.addWidget(self.btn_weak)

        left_v.addWidget(header)
        left_v.addWidget(self.session_list, 1)
        left_v.addLayout(btn_row)

        # ===== Right: Chat + Listening tabs =====
        # Use VocabBrowser
        self.history = VocabBrowser()
        self.history.setStyleSheet(self.history_style_sheet())
        self.history.wordActivated.connect(self._on_vocab_word_activated)
        self.vocab_explained_signal.connect(self._show_vocab_explanation)

        # Grammar hover
        self.history.viewport().setMouseTracking(True)
        self.history.viewport().installEventFilter(self)

        self.input = QtWidgets.QLineEdit()
        self.input.setPlaceholderText("Type a message and press Enter…")

        # Vocab mode button
        self.vocab_mode_btn = QtWidgets.QPushButton("Vocab Mode")
        self.vocab_mode_btn.setCheckable(True)
        self.vocab_mode_btn.setToolTip("Toggle vocabulary highlighting mode")
        self.vocab_mode_btn.toggled.connect(self._on_vocab_mode_toggled)

        self.mic_btn = QtWidgets.QPushButton("🎤 Start")
        self.mic_btn.setCheckable(True)
        self.mic_btn.setToolTip("Toggle microphone for live STT")

        self.lang_combo = QtWidgets.QComboBox()
        self.lang_combo.addItems(["Auto (TR+EN)", "Türkçe (tr-TR)", "English (en-US)"])
        self.lang_combo.setCurrentIndex(2)
        self.lang_combo.setToolTip("Speech recognition language mode")

        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("color:#bdc3c7; font-size:12px;")

        chat_page = QtWidgets.QWidget()
        chat_v = QtWidgets.QVBoxLayout(chat_page)

        # ---------------- TOPIC DROPDOWN (Hierarchical) ----------------
        self.topic_combo = QtWidgets.QComboBox()
        self.topic_combo.setEditable(False)
        self.topic_combo.setMinimumWidth(220)

        # Hierarchical model
        self.topic_model = QtGui.QStandardItemModel(self.topic_combo)
        self.topic_combo.setModel(self.topic_model)

        icons = {"Daily Life": "🏠", "Travel": "✈️", "Professional": "💼"}

        # 0. row: Free Chat
        free_item = QtGui.QStandardItem("🌐 Free Chat")
        free_item.setData("__free__", QtCore.Qt.UserRole)
        free_item.setEditable(False)
        self.topic_model.appendRow(free_item)

        # Categories + sub topics
        for category, topics in self.topic_prompts.items():
            parent_item = QtGui.QStandardItem(f"{icons.get(category, '📘')}  {category}")
            parent_item.setFlags(QtCore.Qt.ItemIsEnabled)
            parent_item.setEditable(False)
            parent_item.setFont(QtGui.QFont("Segoe UI", 10, QtGui.QFont.Bold))
            parent_item.setForeground(QtGui.QColor("#f6e58d"))

            for topic_name in topics.keys():
                child = QtGui.QStandardItem(f"• {topic_name}")
                child.setEditable(False)
                child.setData(topic_name, QtCore.Qt.UserRole)
                child.setFont(QtGui.QFont("Segoe UI", 10))
                child.setForeground(QtGui.QColor("#ecf0f1"))
                parent_item.appendRow(child)

            self.topic_model.appendRow(parent_item)

        # View: QTreeView
        view = QtWidgets.QTreeView()
        view.setHeaderHidden(True)
        view.setRootIsDecorated(True)
        view.setExpandsOnDoubleClick(False)
        view.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        view.setStyleSheet("""
            QTreeView {
                background: #2d3436;
                color: #ecf0f1;
                border-radius: 8px;
                padding: 4px 6px;
                outline: none;
                font-size: 13px;
            }
            QTreeView::item {
                height: 24px;
                padding: 2px 6px;
            }
            QTreeView::item:selected {
                background: #6c5ce7;
                color: #ffffff;
            }
            QTreeView::branch {
                background: transparent;
            }
            QTreeView::branch:selected {
                background: transparent;
            }
        """)

        self.topic_combo.setView(view)
        self.topic_combo.setCurrentIndex(0)
        self.topic_combo.view().clicked.connect(self._on_topic_view_clicked)

        # state variables
        self.current_topic_key = None
        self.current_topic_prompt = None

        # Persona selection
        self.persona_combo = QtWidgets.QComboBox()
        self.persona_combo.addItems([
            "None (Default)",
            "Friendly 😊",
            "Formal 🎓",
            "Coach 💪",
            "Comedian 😂",
            "Romantic 💕",
        ])
        self.persona_combo.setCurrentIndex(0)
        self.persona_combo.setToolTip("Select AI's personality style")
        self.persona_combo.setStyleSheet("""
            QComboBox {
                background:#2c3e50; color:#f1f2f6; border:1px solid #7f8c8d;
                border-radius:8px; padding:6px 10px; font-size:14px; min-width:220px;
            }
            QComboBox:hover { border:1px solid #a29bfe; }
            QComboBox::drop-down { border:none; width:25px; }
        """)
        # Topic combo same style
        self.topic_combo.setStyleSheet(self.persona_combo.styleSheet())

        # Simple static avatar
        self.ai_avatar_label = QtWidgets.QLabel()
        avatar_pix = QtGui.QPixmap("app/resources/images/ai_tutor_logo.png")
        if not avatar_pix.isNull():
            size = 40
            rounded = make_round_pixmap(avatar_pix, size)
            self.ai_avatar_label.setFixedSize(size, size)
            self.ai_avatar_label.setPixmap(
                rounded.scaled(size, size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
            )
        else:
            self.ai_avatar_label.setText("AI")

        # Top bar: avatar + topic + persona
        top_bar = QtWidgets.QHBoxLayout()
        top_bar.addWidget(self.ai_avatar_label)
        top_bar.addSpacing(8)

        lbl_topic = QtWidgets.QLabel("🗣️ Topic:")
        lbl_topic.setStyleSheet("font-weight:bold; color:#ffbe76; font-size:14px;")
        lbl_persona = QtWidgets.QLabel("🎭 Persona:")
        lbl_persona.setStyleSheet("font-weight:bold; color:#74b9ff; font-size:14px;")

        top_bar.addWidget(lbl_topic)
        top_bar.addWidget(self.topic_combo, 1)
        top_bar.addSpacing(20)
        top_bar.addWidget(lbl_persona)
        top_bar.addWidget(self.persona_combo, 1)
        top_bar.addStretch(1)

        chat_v.addLayout(top_bar)
        chat_v.addWidget(self.history, 1)

        h1 = QtWidgets.QHBoxLayout()
        h1.addWidget(self.input, 1)
        h1.addWidget(self.vocab_mode_btn, 0)
        h1.addWidget(self.mic_btn, 0)
        h1.addWidget(self.lang_combo, 0)
        chat_v.addLayout(h1)
        chat_v.addWidget(self.status, 0)

        # ✨ Summary report button
        summary_row = QtWidgets.QHBoxLayout()
        summary_row.addStretch(1)
        self.summary_btn = QtWidgets.QPushButton("See summary report")
        self.summary_btn.setToolTip("Generate performance summary and next lesson topic")
        self.summary_btn.clicked.connect(self._on_summary_clicked)
        summary_row.addWidget(self.summary_btn)
        chat_v.addLayout(summary_row)

        listen_page = ListeningPracticeWidget()
        self.vocab_page = VocabListWidget(self.user_id)

        tabs = QtWidgets.QTabWidget()
        tabs.addTab(chat_page, "Chat")
        tabs.addTab(listen_page, "Listening Practice")
        tabs.addTab(self.vocab_page, "My Vocabulary")

        # ===== Split left/right =====
        splitter = QtWidgets.QSplitter()
        splitter.setHandleWidth(6)
        splitter.addWidget(left)
        splitter.addWidget(tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 820])

        root.addWidget(splitter)

        # ---------- Signals ----------
        self.input.returnPressed.connect(self._on_enter)
        self.bot_text_signal.connect(self._append_bot)
        self.stt_text_signal.connect(self._on_stt)

        # ---------- STT ----------
        try:
            self.stt = STTEngine()
            self.mic_btn.toggled.connect(self._toggle_mic)
            self.lang_combo.currentIndexChanged.connect(self._on_lang_change)
            self._on_lang_change(self.lang_combo.currentIndex())
        except Exception as e:
            self.stt = None
            self.mic_btn.setEnabled(False)
            self.lang_combo.setEnabled(False)
            self.status.setText(f"Azure STT init error: {e}")

        # STT / evaluation buffers
        self._stt_buffer = []
        self._last_partial = ""
        self._flushing = False
        self._last_pa = None

        # ✨ For reports
        self._grammar_events = []  # list of {original, corrected, errors}
        self._pa_scores = []       # list of pronunciation score dicts

        # ---------- Supabase: load sessions & pick default ----------
        self.session_id = None
        self._load_sessions_and_select_default()

        # After sessions are ready, run placement test if needed
        QtCore.QTimer.singleShot(800, lambda: run_placement_test_if_needed(self))

    # =============================================================
    #  Topic handling
    # =============================================================
    def _on_topic_view_clicked(self, index: QtCore.QModelIndex):
        """When clicking category, expand/collapse; when clicking sub-topic, start conversation."""
        item = self.topic_model.itemFromIndex(index)
        if item is None:
            return

        view: QtWidgets.QTreeView = self.topic_combo.view()  # type: ignore

        # 0. row: Free Chat
        first_item = self.topic_model.item(0)
        if item is first_item and not item.hasChildren():
            self.topic_combo.setCurrentIndex(0)
            self.topic_combo.setCurrentText(item.text())
            self.topic_combo.hidePopup()

            self.current_topic_key = None
            self.current_topic_prompt = None
            self._append_bot_simple("Switched to Free Chat. You can talk about anything you like 🙂")
            return

        # CATEGORY row (Daily Life, Travel, Professional) → expand/collapse
        if item.hasChildren():
            if view.isExpanded(index):
                view.collapse(index)
            else:
                view.expand(index)
            QtCore.QTimer.singleShot(0, self.topic_combo.showPopup)
            return

        # SUB TOPIC (At the Restaurant, Hotel Check-in, ...)
        topic_name = item.data(QtCore.Qt.UserRole) or item.text()
        topic_name = str(topic_name).lstrip("• ").strip()

        # Update combo text
        self.topic_combo.setCurrentText(f"• {topic_name}")
        self.topic_combo.hidePopup()

        # Save selected topic
        self.current_topic_key = topic_name

        # Find topic prompt
        topic_prompt = ""
        for category, topics in self.topic_prompts.items():
            if topic_name in topics:
                topic_prompt = topics[topic_name]
                break

        self.current_topic_prompt = topic_prompt

        # Tutor opening message
        opening = (
            f"Great, you chose the topic **{topic_name}**.\n\n"
            f"{topic_prompt}\n\n"
            f"Let's start! Say something and I'll reply in this scenario 😊"
        )
        self._append_bot_simple(opening)

    # =============================================================
    #  Sessions UI / Supabase
    # =============================================================
    def _load_sessions_and_select_default(self):
        self.session_list.clear()
        try:
            sessions = list_user_sessions(limit=100)
        except Exception as e:
            sessions = []
            self.history.append(f"<p><i>Failed to load sessions: {e}</i></p>")

        for s in sessions:
            item = QtWidgets.QListWidgetItem(s.get("title") or f"Chat {s['id']}")
            item.setData(QtCore.Qt.UserRole, s["id"])
            self.session_list.addItem(item)

        if sessions:
            self.session_list.setCurrentRow(0)
            self.session_id = sessions[0]["id"]
            self._load_session_messages(self.session_id)
        else:
            try:
                default_id = get_or_create_default_session()
                self.session_id = default_id
                item = QtWidgets.QListWidgetItem("My Chat")
                item.setData(QtCore.Qt.UserRole, default_id)
                self.session_list.addItem(item)
                self.session_list.setCurrentItem(item)
                self._load_session_messages(default_id)
            except Exception as e:
                self.history.append(f"<p><i>History load failed: {e}</i></p>")

    def _on_session_selected(self):
        items = self.session_list.selectedItems()
        if not items:
            return
        sid = items[0].data(QtCore.Qt.UserRole)
        if sid == self.session_id:
            return
        self.session_id = sid
        self._load_session_messages(sid)

    def _load_session_messages(self, session_id: int):
        self.history.clear()
        try:
            msgs = list_messages(session_id, limit=200)
            known = set()
            if self.user_id:
                try:
                    known = get_known_words_set(self.user_id)
                except Exception:
                    known = set()

            for m in msgs:
                role = m.get("role")
                content = (m.get("content") or "")
                if role == "user":
                    # Use VocabBrowser's append_user
                    self.history.append_user(content)
                else:
                    # Use VocabBrowser's append_bot with vocab
                    new_words = find_new_vocabulary(content, known_words=known)
                    self.history.append_bot(content, new_words)

            self.history.set_vocab_mode(self.vocab_mode_btn.isChecked())
        except Exception as e:
            self.history.append(f"<p><i>Failed to load messages: {e}</i></p>")

    def _new_chat(self):
        title, ok = QtWidgets.QInputDialog.getText(
            self, "New Chat", "Title:", text="New Chat"
        )
        if not ok:
            return
        try:
            row = create_session(title or "New Chat")
            item = QtWidgets.QListWidgetItem(row.get("title") or f"Chat {row['id']}")
            item.setData(QtCore.Qt.UserRole, row["id"])
            self.session_list.insertItem(0, item)
            self.session_list.setCurrentItem(item)
            self.session_id = row["id"]
            self.history.clear()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to create chat:\n{e}")

    def _rename_chat(self):
        items = self.session_list.selectedItems()
        if not items:
            return
        item = items[0]
        sid = item.data(QtCore.Qt.UserRole)
        current = item.text()
        title, ok = QtWidgets.QInputDialog.getText(
            self, "Rename Chat", "Title:", text=current
        )
        if not ok:
            return
        try:
            rename_session(sid, title or current)
            item.setText(title or current)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to rename chat:\n{e}")

    def _delete_chat(self):
        items = self.session_list.selectedItems()
        if not items:
            return

        item = items[0]
        sid = item.data(QtCore.Qt.UserRole)

        confirmation = QtWidgets.QMessageBox.question(
            self,
            "Delete Chat",
            "Delete this chat? This can't be undone.",
        )

        if confirmation != QtWidgets.QMessageBox.Yes:
            return

        try:
            delete_session(sid)
            row = self.session_list.row(item)
            self.session_list.takeItem(row)

            # Select next chat or clear UI
            if self.session_list.count() > 0:
                self.session_list.setCurrentRow(0)
            else:
                self.session_id = None
                self.history.clear()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to delete chat:\n{e}")

    # ---------- export chat (TXT) ----------
    def _export_chat(self):
        if not self.session_id:
            QtWidgets.QMessageBox.warning(self, "No Chat", "Please select a chat.")
            return

        current_item = self.session_list.currentItem()
        session_title = current_item.text() if current_item else f"Chat {self.session_id}"
        suggested = f"Chat - {session_title}.txt".replace("/", "_")

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Chat",
            suggested,
            "Text Files (*.txt);;All Files (*.*)"
        )
        if not path:
            return

        try:
            msgs = list_messages(self.session_id, limit=1000)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to load messages:\n{e}")
            return

        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = [
            f"Session: {session_title}",
            f"Exported at: {now}",
            "-" * 50,
            ""
        ]
        for m in msgs:
            who = "You" if m.get("role") == "user" else "Tutor"
            content = strip_lang_tags(m.get("content") or "")
            lines.append(f"{who}: {content}")
            lines.append("")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to save:\n{e}")
            return

        QtWidgets.QMessageBox.information(self, "Saved", "Chat exported successfully.")

    # ---------- Weak Points (global FR16/17) ----------
    def _show_weak_points(self):
        try:
            events = get_recent_learning_events(limit=300)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Error", f"Could not load learning history:\n{e}")
            return

        if not events:
            QtWidgets.QMessageBox.information(
                self,
                "No Data",
                "There is not enough learning history yet.\n"
                "Chat with the tutor a bit more, then try again."
            )
            return

        sentences: list[str] = []
        words: list[str] = []
        cat_counts: Counter[str] = Counter()
        dates: set[str] = set()
        last_ts: str | None = None

        STOPWORDS = {
            "the", "and", "for", "with", "this", "that", "you", "your", "have", "has", "had",
            "are", "was", "were", "but", "not", "just", "very", "really", "can", "could",
            "will", "would", "about", "from", "into", "over", "under", "they", "them",
            "their", "there", "here", "then", "than", "because", "when", "what", "how",
            "why", "who", "whom", "which", "also", "like", "some", "more", "most", "much",
            "many", "any", "all", "too", "use", "used", "using", "get", "got", "did",
            "do", "does", "is", "am", "be", "being", "been"
        }

        CATEGORY_LABELS = {
            "verb_tense": "Verb tense (past/present/future)",
            "subject_verb_agreement": "Subject–verb agreement",
            "articles": "Articles (a/an/the)",
            "prepositions": "Prepositions (in/on/at...)",
            "word_order": "Word order",
            "plural_singular": "Plural / singular forms",
            "pronouns": "Pronouns",
            "vocabulary_choice": "Vocabulary choice / collocation",
            "spelling": "Spelling",
            "punctuation": "Punctuation",
            "other": "Other / mixed issues",
        }

        for e in events:
            payload = e.get("payload") or {}

            created_at = e.get("created_at")
            if isinstance(created_at, str):
                day = created_at[:10]
                dates.add(day)
                if last_ts is None:
                    last_ts = created_at

            s = payload.get("last_input")
            if s:
                sentences.append(s)
                for w in re.findall(r"[A-Za-z']+", s.lower()):
                    if len(w) >= 3 and w not in STOPWORDS:
                        words.append(w)

            cats = payload.get("grammar_categories") or []
            if isinstance(cats, str):
                cats = [cats]
            for c in cats:
                c = c.strip().lower().replace(" ", "_")
                if c:
                    cat_counts[c] += 1

        if not sentences and not cat_counts:
            QtWidgets.QMessageBox.information(
                self,
                "No Data",
                "There is not enough learning history yet.\n"
                "Chat with the tutor a bit more, then try again."
            )
            return

        word_counts = Counter(words).most_common(15)

        def esc(t: str) -> str:
            return (
                (t or "")
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

        total_events = len(events)
        total_sentences = len(sentences)
        total_days = len(dates)

        last_time_str = ""
        if last_ts:
            import datetime as _dt
            try:
                dt = _dt.datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                last_time_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                last_time_str = last_ts

        top_cats = [c for c, _ in cat_counts.most_common(2)]
        top_words = [w for w, _ in word_counts[:5]]

        def words_str(ws):
            return ", ".join(ws) if ws else "everyday topics"

        suggestions: list[str] = []
        for c in top_cats:
            if c == "verb_tense":
                suggestions.append(
                    "Can you give me extra exercises to practice verb tenses using everyday life examples?"
                )
            elif c == "prepositions":
                suggestions.append(
                    f"Can you give me sentences to practice prepositions with these words: {words_str(top_words)}?"
                )
            elif c == "articles":
                suggestions.append(
                    "Please create a short exercise to practice a/an/the with my common vocabulary."
                )
            elif c == "subject_verb_agreement":
                suggestions.append(
                    "Can you give me a quiz to practice subject–verb agreement in present simple?"
                )
            elif c == "word_order":
                suggestions.append(
                    "Can you give me jumbled sentences so I can practice English word order?"
                )
            elif c == "vocabulary_choice":
                suggestions.append(
                    f"Can you give me collocation practice with these words: {words_str(top_words)}?"
                )
            else:
                suggestions.append(
                    "Using my recent mistakes, can you create a short mixed-grammar exercise?"
                )

        if not suggestions:
            suggestions.append(
                "Can you create a short quiz using my recent mistakes and frequently used words?"
            )

        focus_label = None
        if top_cats:
            focus_label = CATEGORY_LABELS.get(top_cats[0], top_cats[0])

        mini_plan_lines: list[str] = []
        if focus_label:
            mini_plan_lines.append(
                f"1) Focus today: {focus_label}. Rewrite 3 of your recent sentences correctly."
            )
        else:
            mini_plan_lines.append(
                "1) Rewrite 3 of your recent sentences, making them as accurate as possible."
            )

        if top_words:
            mini_plan_lines.append(
                f"2) Write 3 new sentences using these words: {', '.join(top_words[:5])}."
            )
        else:
            mini_plan_lines.append(
                "2) Write 3 new sentences about your daily routine."
            )

        mini_plan_lines.append(
            "3) Use one of the suggested prompts below to ask the tutor for a short quiz."
        )

        html_parts: list[str] = []
        html_parts.append("<h2>Weak Points Overview</h2>")
        if focus_label:
            html_parts.append(
                f"<p><b>Today's focus:</b> {esc(focus_label)} &mdash; based on your recent mistakes.</p>"
            )

        html_parts.append("<h3>Progress stats</h3><ul>")
        html_parts.append(f"<li>Total practice events: <b>{total_events}</b></li>")
        html_parts.append(f"<li>Distinct days with practice: <b>{total_days}</b></li>")
        html_parts.append(f"<li>Recorded sentences: <b>{total_sentences}</b></li>")
        if last_time_str:
            html_parts.append(f"<li>Last practice: <b>{esc(last_time_str)}</b></li>")
        html_parts.append("</ul>")

        html_parts.append(
            "<p>This panel summarizes your recent learning history across all chats. "
            "It is based on sentences you produced while practicing with the tutor.</p>"
        )

        if sentences:
            html_parts.append("<h3>Recent practice sentences</h3><ul>")
            for s in sentences[:12]:
                html_parts.append(f"<li>{esc(s)}</li>")
            html_parts.append("</ul>")

        if cat_counts:
            html_parts.append("<h3>Grammar focus areas</h3><ul>")
            for key, count in cat_counts.most_common():
                label = CATEGORY_LABELS.get(key, key)
                html_parts.append(f"<li><b>{esc(label)}</b> &times; {count}</li>")
            html_parts.append("</ul>")
            html_parts.append(
                "<p>These categories show which grammar areas appear most often in your sentences. "
                "You can ask the tutor for extra practice on any of them.</p>"
            )

        if word_counts:
            html_parts.append("<h3>Frequently repeated words/topics</h3><ul>")
            for w, c in word_counts:
                html_parts.append(f"<li>{esc(w)} × {c}</li>")
            html_parts.append("</ul>")

        html_parts.append("<h3>How to use this</h3><ul>")
        html_parts.append(
            "<li>Pick 1–2 grammar areas above and ask the tutor for targeted exercises.</li>"
        )
        html_parts.append(
            "<li>Rewrite some of the recent sentences, focusing on those grammar points.</li>"
        )
        html_parts.append(
            "<li>Use the suggested prompts below to quickly start a focused practice session.</li>"
        )
        html_parts.append("</ul>")

        html_parts.append("<h3>Mini study plan (today)</h3><ul>")
        for line in mini_plan_lines:
            html_parts.append(f"<li>{esc(line)}</li>")
        html_parts.append("</ul>")

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Weak Points (Global)")
        dlg.resize(720, 580)

        layout = QtWidgets.QVBoxLayout(dlg)

        browser = QtWidgets.QTextBrowser()
        browser.setReadOnly(True)
        browser.setHtml("".join(html_parts))
        layout.addWidget(browser, 1)

        layout.addWidget(QtWidgets.QLabel("Suggested practice prompts:"))
        list_widget = QtWidgets.QListWidget()
        for s in suggestions:
            list_widget.addItem(s)
        layout.addWidget(list_widget)

        helper = QtWidgets.QLabel("Double-click a prompt to send it to the chat box.")
        helper.setStyleSheet("color:#bdc3c7; font-size:11px;")
        layout.addWidget(helper)

        def on_item_activated(item: QtWidgets.QListWidgetItem):
            text = item.text()
            self.input.setText(text)
            self.input.setCursorPosition(len(text))
            self.input.setFocus()
            dlg.accept()

        list_widget.itemDoubleClicked.connect(on_item_activated)

        # TXT export of summary
        summary_lines: list[str] = []
        summary_lines.append("WEAK POINTS SUMMARY")
        summary_lines.append("=" * 40)
        summary_lines.append(f"Total events: {total_events}")
        summary_lines.append(f"Distinct days: {total_days}")
        summary_lines.append(f"Recorded sentences: {total_sentences}")
        if last_time_str:
            summary_lines.append(f"Last practice: {last_time_str}")
        summary_lines.append("")

        if cat_counts:
            summary_lines.append("Grammar focus areas:")
            for key, count in cat_counts.most_common():
                label = CATEGORY_LABELS.get(key, key)
                summary_lines.append(f"  - {label}: {count}")
            summary_lines.append("")

        if word_counts:
            summary_lines.append("Frequent words:")
            for w, c in word_counts:
                summary_lines.append(f"  - {w}: {c}")
            summary_lines.append("")

        summary_lines.append("Mini study plan (today):")
        for line in mini_plan_lines:
            summary_lines.append(f"  - {line}")
        summary_text = "\n".join(summary_lines)

        def export_txt():
            path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export Weak Points",
                "weak_points_summary.txt",
                "Text Files (*.txt);;All Files (*.*)",
            )
            if not path:
                return
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(summary_text)
            except Exception as e:
                QtWidgets.QMessageBox.warning(dlg, "Error", f"Failed to save file:\n{e}")
                return
            QtWidgets.QMessageBox.information(dlg, "Saved", "Weak points summary exported successfully.")

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch(1)
        btn_export = QtWidgets.QPushButton("Export as TXT")
        btn_close = QtWidgets.QPushButton("Close")
        btn_export.clicked.connect(export_txt)
        btn_close.clicked.connect(dlg.reject)
        btn_row.addWidget(btn_export)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

        dlg.exec()

    # =============================================================
    #  Styles
    # =============================================================
    def history_style_sheet(self):
        return """
            QTextBrowser {
                background-color: #34495e; color: #ecf0f1;
                border: 1px solid #7f8c8d; border-radius: 8px;
                padding: 10px; font-family: Segoe UI, Arial, sans-serif; font-size: 14px;
            }
            p { margin: 2px 0 4px 0; line-height: 1.3; }
            b { color: #f1c40f; }
            a { color: #74b9ff; text-decoration: none; }
            a.grammar-error {
                color: #f39c12;
                text-decoration: underline wavy;
                text-decoration-color: #e74c3c;
                text-underline-offset: 2px;
                cursor: help;
            }

            /* Summary report tweaks */
            .summary-report { margin-top: 4px; }
            .summary-report h3,
            .summary-report h3.neon-title {
                color: #39ff14;
                margin: 4px 0 2px 0;
            }
            .summary-report p {
                margin: 1px 0;
                line-height: 1.25;
            }
            .summary-report ul {
                margin: 2px 0 2px 18px;
            }
            .summary-report li {
                margin: 0 0 2px 0;
            }
            .summary-wrapper { margin: 4px 0; }
            .summary-subhead {
                color: #ffe45c;
            }
        """

    # =============================================================
    #  HTML helpers
    # =============================================================
    def _escape_html(self, s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _build_grammar_html(self, result: dict) -> str:
        """
        Build HTML with grammar error highlighting.
        """
        original = result.get("original", "")
        errors = result.get("errors", [])

        if not original:
            return ""

        if not errors:
            return self._escape_html(original)

        # Sort errors by start position
        try:
            sorted_errors = sorted(errors, key=lambda e: e.get("start", 0))
        except Exception:
            sorted_errors = errors

        html_parts = []
        pos = 0

        for err in sorted_errors:
            try:
                start = err.get("start", 0)
                end = err.get("end", start)
                suggestion = err.get("suggestion", "")

                # Validate indices
                if start < 0 or end > len(original) or start >= end or start < pos:
                    continue

                # Add text before error
                if pos < start:
                    normal_chunk = original[pos:start]
                    html_parts.append(self._escape_html(normal_chunk))

                # Add error with underline and link
                error_text = original[start:end]
                suggestion_escaped = self._escape_html(suggestion)
                error_escaped = self._escape_html(error_text)

                # Create grammar error link
                href = "grammar://" + urllib.parse.quote(suggestion)
                html_parts.append(
                    f'<a href="{href}" class="grammar-error" '
                    f'title="Suggestion: {suggestion_escaped}">'
                    f'{error_escaped}</a>'
                )

                pos = end

            except Exception:
                continue

        # Add remaining text
        if pos < len(original):
            html_parts.append(self._escape_html(original[pos:]))

        return "".join(html_parts)

    # =============================================================
    #  Chat - FIXED VERSION
    # =============================================================
    def _on_enter(self):
        if not self.session_id:
            QtWidgets.QMessageBox.warning(
                self, "No Chat", "Please create or select a chat first."
            )
            return

        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()

        # Show & persist user message (with grammar highlight)
        self._append_user_with_grammar(text)

        try:
            add_message(self.session_id, role="user", content=text)
        except Exception as e:
            self.history.append(f"<p><i>Save error (user): {e}</i></p>")

        # Show thinking indicator
        self.history.show_thinking("⏳ Thinking…")

        # ---- persona + topic prompt shaping ----
        topic = self.topic_combo.currentText().lstrip("• ").lstrip("🌐 ").strip()
        persona_label = self.persona_combo.currentText()
        persona_key = persona_label.split()[0].lower()
        if persona_key == "none":
            persona_key = "neutral"

        # Find topic context
        context = ""
        for cat, topics in self.topic_prompts.items():
            if topic in topics:
                context = topics[topic]
                break

        persona_styles = {
            "neutral": "Use a clear, helpful but neutral tone.",
            "friendly": "Be warm, encouraging and supportive. You can sometimes use emojis like 😊, but don't overuse them.",
            "formal": "Use polite, academic and professional language. Avoid slang and emojis.",
            "coach": "Act like a motivating language coach. Give short encouragement and small tips to improve.",
            "comedian": "Keep a light, humorous tone with small jokes, but still answer clearly and respectfully.",
            "romantic": "Use a soft, gentle and caring tone, but stay appropriate and focused on language learning.",
        }
        style_instr = persona_styles.get(persona_key, persona_styles["neutral"])

        # Instead of overwriting the whole system prompt, we prepend a short tag
        engine_input = (
            f"[TOPIC: {topic} | PERSONA: {persona_key}]\n"
            f"[STYLE_HINT: {style_instr}]\n\n"
            f"{text}"
        )

        def worker():
            # pass session_id for learning_events etc.
            reply = self.engine.ask(engine_input, session_id=self.session_id)
            try:
                add_message(self.session_id, role="assistant", content=reply)
            except Exception:
                pass
            self.bot_text_signal.emit(reply)

        threading.Thread(target=worker, daemon=True).start()

    def _append_user_with_grammar(self, text: str):
        """
        FIXED: Display user message with grammar checking.
        ALWAYS shows user message, even if grammar checking fails.
        """
        checker = getattr(self.engine, "check_grammar", None)

        # If no grammar checker, just show plain text using VocabBrowser
        if not callable(checker):
            self.history.append_user(text)
            return

        try:
            # Call grammar checker
            result = checker(text)

            # Validate result
            if not isinstance(result, dict) or not result:
                self.history.append_user(text)
                return

            # Check for errors in the result
            if "error" in result:
                # Grammar check had an error, show plain text
                self.history.append_user(text)
                return

        except Exception as e:
            # Grammar check failed, show plain text
            print(f"Grammar check error: {e}")
            self.history.append_user(text)
            return

        # Build HTML with error highlighting
        html = self._build_grammar_html(result)

        # If HTML building failed, fall back to plain text
        if not html or html == "":
            self.history.append_user(text)
            return

        # Display user message with grammar highlights
        self.history.append(f"<p><b>You:</b><br>{html}</p>")

        # Store for summary reports
        self._grammar_events.append({
            "original": result.get("original", text),
            "corrected": result.get("corrected", text),
            "errors": result.get("errors", []),
        })

        # Show corrected version if there are errors
        errors = result.get("errors", [])
        if errors and len(errors) > 0:
            corrected = result.get("corrected", "").strip()
            if corrected and corrected != text:
                safe = self._escape_html(corrected)
                self.history.append(
                    f"<p><i style='color:#2ecc71;'>✅ Correct version:</i> {safe}</p>"
                )

    # =============================================================
    #  STT
    # =============================================================
    def _toggle_mic(self, on: bool):
        if not self.stt:
            return
        if on:
            self._stt_buffer = []
            self._last_partial = ""
            self.mic_btn.setText("⏹ Stop")
            self.status.setText(
                "Listening… (I'll keep recording until you press Stop)"
            )
            self.stt.start(self._stt_cb)
        else:
            self.mic_btn.setText("🎤 Start")
            self.status.setText("Stopping mic…")
            self.stt.stop()
            if self._flushing:
                return
            self._flushing = True
            QtCore.QTimer.singleShot(900, self._flush_stt_to_input)

    def _flush_stt_to_input(self):
        self._flushing = False
        final_text = " ".join(self._stt_buffer).strip()
        if not final_text and self._last_partial:
            final_text = strip_lang_tags(self._last_partial)

        self._stt_buffer = []
        self._last_partial = ""
        self.status.setText("Mic off.")

        if final_text:
            self.input.setText(final_text)
            self.input.setCursorPosition(len(final_text))
            self.input.setFocus()

            safe = final_text.replace("<", "&lt;").replace(">", "&gt;")
            self.history.append(
                f"<p><i>Draft from mic:</i><br>{safe}</p>"
            )
            self.status.setText(
                "🎙️ Edit the text and press Enter to send."
            )
        else:
            self.status.setText("🎙️ No speech captured.")

        if getattr(self, "_last_pa", None):
            pa = self._last_pa
            rows = []
            if pa.get("pronunciation") is not None:
                rows.append(
                    f"<tr><td>Overall</td>"
                    f"<td><b>{pa['pronunciation']:.1f}</b></td></tr>"
                )
            if pa.get("accuracy") is not None:
                rows.append(
                    f"<tr><td>Accuracy</td><td>{pa['accuracy']:.1f}</td></tr>"
                )
            if pa.get("fluency") is not None:
                rows.append(
                    f"<tr><td>Fluency</td><td>{pa['fluency']:.1f}</td></tr>"
                )
            if pa.get("completeness") is not None:
                rows.append(
                    f"<tr><td>Completeness</td>"
                    f"<td>{pa['completeness']:.1f}</td></tr>"
                )
            if pa.get("prosody") is not None:
                rows.append(
                    f"<tr><td>Prosody</td><td>{pa['prosody']:.1f}</td></tr>"
                )
            table = "<table style='border-collapse:collapse'>"
            for r in rows:
                table += f"<tr style='border-bottom:1px solid #555'>{r}</tr>"
            table += "</table>"
            self.history.append(
                f"<p><b>Pronunciation (EN):</b><br>{table}</p>"
            )

            # ✨ store scores for later summary
            self._pa_scores.append(pa)
            self._last_pa = None

    def _on_lang_change(self, idx: int):
        if not self.stt:
            return
        label = self.lang_combo.currentText()
        if "Auto" in label:
            mode = "auto"
        elif "Türkçe" in label:
            mode = "tr-TR"
        else:
            mode = "en-US"
        self.stt.set_mode(mode)
        self.status.setText(f"STT mode → {mode}")

    # bg thread -> UI thread
    def _stt_cb(self, text, is_final, words):
        self.stt_text_signal.emit(text, is_final, words)

    def _on_stt(self, text: str, is_final: bool, words: list):
        if not text:
            return
        display_text = text
        if not is_final:
            self._last_partial = display_text
            short = (
                display_text
                if len(display_text) <= 100
                else (display_text[:100] + "…")
            )
            self.status.setText(f"(live) {short}")
            return

        self._stt_buffer.append(display_text)
        safe = display_text.replace("<", "&lt;").replace(">", "&gt;")
        self.history.append(f"<p><i>+ segment:</i> {safe}</p>")

        self._last_pa = None
        if (
                words
                and isinstance(words, list)
                and isinstance(words[0], dict)
                and "_pa_overall" in words[0]
        ):
            self._last_pa = words[0]["_pa_overall"]

    # =============================================================
    #  Summary report helpers
    # =============================================================
    def _aggregate_grammar_errors(self):
        total = 0
        counter = Counter()
        for ev in self._grammar_events:
            for err in ev.get("errors", []):
                word = (err.get("original") or "").strip()
                if not word:
                    continue
                total += 1
                counter[word] += 1
        if counter:
            top = ", ".join(f"{w} (x{c})" for w, c in counter.most_common(5))
        else:
            top = "—"
        return total, top

    def _aggregate_pronunciation_summary(self) -> str:
        if not self._pa_scores:
            return "No pronunciation scores recorded yet."

        keys = ["pronunciation", "accuracy", "fluency", "completeness", "prosody"]
        avgs = {}
        for key in keys:
            vals = [p[key] for p in self._pa_scores if p.get(key) is not None]
            if vals:
                avgs[key] = sum(vals) / len(vals)

        parts = [f"{k.capitalize()}: {v:.1f}" for k, v in avgs.items()]
        return "; ".join(parts) if parts else "Scores not available."

    def _build_summary_with_gemini(self) -> str:
        # Chat log from Supabase
        try:
            msgs = list_messages(self.session_id, limit=200)
        except Exception:
            msgs = []

        lines = []
        for m in msgs:
            role = m.get("role") or "assistant"
            content = m.get("content") or ""
            label = "Student" if role == "user" else "Tutor"
            lines.append(f"{label}: {content}")
        chat_log = "\n".join(lines[-40:])  # last ~40 lines

        total_errors, top_words = self._aggregate_grammar_errors()
        pron_summary = self._aggregate_pronunciation_summary()

        prompt = f"""
You are an experienced English tutor.

I will give you the student's recent chat conversation with you, some aggregate grammar mistakes and pronunciation scores.
From this data, create a concise performance report.

Requirements:
- Write the report in HTML (you can use <h3>, <p>, <ul>, <li>, <b>).
- Sections:
  <h3>Summary Report</h3>
  - 1–2 sentences describing the student's overall level and progress.
  - Give an overall score from 0 to 100.
  <h3>Detailed Feedback</h3>
  - Grammar: strengths and main problems.
  - Vocabulary: what the student uses well / needs to improve.
  - Fluency: comment on how smoothly the student speaks/writes.
  - Pronunciation: mention and interpret the pronunciation scores.
  <h3>NEXT LESSON TOPIC</h3>
  - Propose ONE concrete next lesson topic (for example "Past Simple vs Present Perfect").
  - Add 2–3 short practice ideas for that topic (bullet list).

- Base your comments on the data, especially repeated grammar errors and pronunciation scores.
- Talk directly to the student as "you".
- Do NOT include the raw chat log text inside the report.

DATA:
--- CHAT LOG ---
{chat_log}

--- GRAMMAR SUMMARY ---
Total errors: {total_errors}
Top problematic words/phrases: {top_words}

--- PRONUNCIATION SUMMARY ---
{pron_summary}
"""
        return self.engine.ask(prompt)

    def _wrap_summary_html(self, html: str) -> str:
        content = html or "<p>No summary generated.</p>"

        # Gemini sometimes wraps the HTML in Markdown code fences
        fenced = re.match(r"```(?:\w+)?\s*(.*?)\s*```", content, flags=re.DOTALL)
        if fenced:
            content = fenced.group(1).strip()

        # Ensure main titles get neon style (case-insensitive)
        def neon_title(match):
            inner = match.group(1)
            return f"<h3 class='neon-title'>{inner}</h3>"

        content = re.sub(
            r"<h3>(Summary Report|Detailed Feedback|NEXT LESSON TOPIC)</h3>",
            neon_title,
            content,
            flags=re.IGNORECASE,
        )

        # Highlight key subheadings (Grammar, Vocabulary, etc.)
        def highlight_subhead(match):
            label = match.group(1)
            tail = match.group(2) or ""
            return f"<b class='summary-subhead'>{label}{tail}</b>"

        content = re.sub(
            r"<b>(Grammar|Vocabulary|Fluency|Pronunciation)(:?)</b>",
            highlight_subhead,
            content,
            flags=re.IGNORECASE,
        )

        return f"<div class='summary-report'>{content}</div>"

    def _on_summary_clicked(self):
        if not self.session_id:
            QtWidgets.QMessageBox.warning(
                self, "No Chat", "Please create or select a chat first."
            )
            return

        # Show thinking indicator
        self.history.show_thinking("⏳ Thinking…")

        def worker():
            try:
                report = self._build_summary_with_gemini()
                report = self._wrap_summary_html(report)
            except Exception as e:
                report = f"[Summary error: {e}]"
            self.bot_text_signal.emit(report)

        threading.Thread(target=worker, daemon=True).start()

    # =============================================================
    #  UI helpers & vocab
    # =============================================================
    def _append_bot(self, text: str):
        """Append bot message with vocab highlighting support"""
        known = set()
        if self.user_id:
            try:
                known = get_known_words_set(self.user_id)
            except Exception:
                known = set()
        new_words = find_new_vocabulary(text, known_words=known)

        is_summary = "summary-report" in text
        if is_summary:
            formatted = text
        else:
            formatted = text  # VocabBrowser handles markdown conversion

        # Use VocabBrowser's append_bot method
        self.history.append_bot(formatted, new_words)

    def _append_bot_simple(self, text: str):
        """Simple bot message without vocab highlighting (used for system messages)"""
        # Use VocabBrowser's append_bot with empty new_words list
        self.history.append_bot(text, [])

    def _on_vocab_word_activated(self, word: str, context: str):
        def worker():
            prompt = (
                "You are an English tutor.\n\n"
                f"Explain the word '{word}' in simple, learner-friendly English.\n\n"
                "Context (the full message / dialogue):\n"
                f"{context}\n\n"
                "Format your answer as:\n"
                "- Definition: ...\n"
                "- Example: ...\n"
                "- Another example: ..."
            )
            explanation = self.engine.ask(prompt, session_id=self.session_id)
            self.vocab_explained_signal.emit(word, explanation)

        threading.Thread(target=worker, daemon=True).start()

    @QtCore.Slot(str, str)
    def _show_vocab_explanation(self, word: str, explanation: str):
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle(f"Word: {word}")
        msg.setText(explanation or "No explanation available.")
        if self.user_id:
            msg.setInformativeText("Save this word to your personal word list?")
            msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            res = msg.exec()
            if res == QtWidgets.QMessageBox.Yes:
                try:
                    add_word(self.user_id, word, explanation or "", examples=[])
                    if hasattr(self, "vocab_page") and self.vocab_page is not None:
                        self.vocab_page.refresh()
                except Exception as e:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Save error",
                        f"Could not save word:\n{e}",
                    )
        else:
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec()

    def _on_vocab_mode_toggled(self, on: bool):
        self.history.set_vocab_mode(on)

    # =============================================================
    #  Event filter (grammar hover tooltips)
    # =============================================================
    def eventFilter(self, obj, event):
        if obj is self.history.viewport() and event.type() == QtCore.QEvent.MouseMove:
            pos = event.pos()
            href = self.history.anchorAt(pos)
            if href and href.startswith("grammar://"):
                suggestion = urllib.parse.unquote(href[len("grammar://"):])
                if suggestion:
                    QtWidgets.QToolTip.showText(
                        event.globalPos(),
                        f"✅ Correct: {suggestion}",
                    )
            else:
                QtWidgets.QToolTip.hideText()
        return super().eventFilter(obj, event)


# =================================================================
#  Avatar helper
# =================================================================
def make_round_pixmap(original: QtGui.QPixmap, size: int) -> QtGui.QPixmap:
    rounded = QtGui.QPixmap(size, size)
    rounded.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(rounded)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)

    path = QtGui.QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)

    painter.drawPixmap(0, 0, size, size, original)
    painter.end()
    return rounded


# =================================================================
#  Stand-alone test
# =================================================================
if __name__ == "__main__":
    class MockEngine:
        def ask(self, prompt, session_id=None):
            import time
            time.sleep(0.6)
            return f"Hello! You asked about: {prompt[:80]} ..."

        def check_grammar(self, text: str):
            """Mock grammar checker for testing"""
            # Simulate finding "goed" error
            if "goed" in text.lower():
                idx = text.lower().index("goed")
                return {
                    "original": text,
                    "corrected": text[:idx] + "went" + text[idx+4:],
                    "errors": [
                        {
                            "original": text[idx:idx+4],
                            "suggestion": "went",
                            "start": idx,
                            "end": idx + 4,
                        }
                    ],
                }

            return {"original": text, "corrected": text, "errors": []}

    app = QtWidgets.QApplication(sys.argv)
    engine = MockEngine()
    w = MainWindow(engine)
    w.show()
    sys.exit(app.exec())