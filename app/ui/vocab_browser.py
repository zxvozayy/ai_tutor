# app/ui/vocab_browser.py
from __future__ import annotations

import html
import re
from typing import Iterable, Set
from pathlib import Path

from PySide6 import QtWidgets, QtGui, QtCore


# --- Visual tokens (easy to tweak) ---
BG = "#f8fdf8"
BORDER = "#b5e48c"
USER_BG = "#d9ed92"
USER_BORDER = "#b5e48c"
TUTOR_BG = "#ffffff"
TUTOR_BORDER = "#52b69a"
TEXT = "#184e77"
TEAL = "#168aad"
SCROLL_BG = "#e8f5e8"
SCROLL_HANDLE = "#99d98c"
SCROLL_HANDLE_HOVER = "#76c893"


def _add_shadow(widget: QtWidgets.QWidget, blur: int = 18, dy: int = 4, alpha: int = 22) -> None:
    eff = QtWidgets.QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, dy)
    eff.setColor(QtGui.QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(eff)


def _round_pixmap(icon_path: str, size: int = 20) -> QtGui.QPixmap | None:
    pm = QtGui.QPixmap(icon_path)
    if pm.isNull():
        return None

    pm = pm.scaled(size, size, QtCore.Qt.KeepAspectRatioByExpanding, QtCore.Qt.SmoothTransformation)
    rounded = QtGui.QPixmap(size, size)
    rounded.fill(QtCore.Qt.transparent)

    painter = QtGui.QPainter(rounded)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    path = QtGui.QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pm)
    painter.end()

    return rounded


class MessageBubble(QtWidgets.QFrame):
    """A single chat message bubble with rounded corners (no inner scrolling)."""

    def __init__(self, text: str, is_user: bool, icon_path: str = "", parent=None):
        super().__init__(parent)
        self.is_user = is_user
        self._setup_ui(text, icon_path)

    def _setup_ui(self, text: str, icon_path: str):
        self.setObjectName("MessageBubble")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        if self.is_user:
            self.setStyleSheet(f"""
                #MessageBubble {{
                    background-color: {USER_BG};
                    border: 1px solid {USER_BORDER};
                    border-radius: 16px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                #MessageBubble {{
                    background-color: {TUTOR_BG};
                    border: 1px solid {TUTOR_BORDER};
                    border-radius: 16px;
                }}
            """)

        _add_shadow(self)

        # IMPORTANT: allow bubble to expand horizontally
        if self.is_user:
            self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        else:
            self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Maximum)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        # Header row (icon + name)
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(8)

        if (not self.is_user) and icon_path:
            pm = _round_pixmap(icon_path, size=20)
            if pm is not None:
                icon_label = QtWidgets.QLabel()
                icon_label.setPixmap(pm)
                icon_label.setFixedSize(20, 20)
                header_layout.addWidget(icon_label)

        name_label = QtWidgets.QLabel("You:" if self.is_user else "Tutor:")
        name_label.setStyleSheet(f"""
            font-weight: 800;
            font-size: 12px;
            color: {TEXT if self.is_user else TEAL};
            background: transparent;
        """)
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Content (QTextBrowser for links/anchors)
        content = QtWidgets.QTextBrowser()
        content.setReadOnly(True)
        content.setOpenExternalLinks(False)
        content.setOpenLinks(False)
        content.setHtml(text)

        content.setStyleSheet(f"""
            QTextBrowser {{
                color: {TEXT};
                font-size: 14px;
                background: transparent;
                border: none;
                padding: 0px;
            }}
            a {{
                color: {TEAL};
                text-decoration: underline;
                font-weight: 700;
            }}
            a:hover {{
                color: #0f6d92;
            }}
        """)

        # assign before event filter (prevents your old crash)
        self.content_label = content

        # NO inner scrollbars
        self.content_label.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.content_label.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        # hover tooltips for grammar:// links
        self.content_label.viewport().setMouseTracking(True)
        self.content_label.viewport().installEventFilter(self)

        layout.addWidget(self.content_label)

        # initial sizing
        self._sync_doc_height()

    def set_text_width(self, px: int) -> None:
        """Set document width and resize height to fit content (no inner scroll)."""
        self.content_label.document().setTextWidth(max(200, px))
        self._sync_doc_height()

    def _sync_doc_height(self) -> None:
        doc_h = self.content_label.document().size().height()
        self.content_label.setFixedHeight(max(24, int(doc_h) + 10))

    def eventFilter(self, obj, event):
        if obj is self.content_label.viewport() and event.type() == QtCore.QEvent.MouseMove:
            anchor = self.content_label.anchorAt(event.pos())
            if anchor and anchor.startswith("grammar://"):
                import urllib.parse
                suggestion = urllib.parse.unquote(anchor[10:])
                if suggestion:
                    QtWidgets.QToolTip.showText(event.globalPos(), f"✅ Correct: {suggestion}", self)
                else:
                    QtWidgets.QToolTip.hideText()
            else:
                QtWidgets.QToolTip.hideText()
        return super().eventFilter(obj, event)

    def _plain_text_for_measure(self) -> str:
        """Best-effort plain text for measuring bubble width."""
        doc = self.content_label.document()
        t = doc.toPlainText()
        t = t.replace("\u2029", "\n")
        return t.strip()

    def set_compact_width(self, max_bubble_w: int) -> None:
        """
        Make bubble width depend on message length.
        - Short msg => small bubble
        - Long msg => up to max_bubble_w, wraps nicely
        """
        # bubble internal paddings: roughly left+right (layout margins) + some safety
        side_padding = 40  # tweak if needed
        max_bubble_w = max(260, int(max_bubble_w))

        # Measure "ideal" width: QTextDocument can tell us
        doc = self.content_label.document()

        # Temporarily allow very wide to compute idealWidth (single-line ideal)
        doc.setTextWidth(10_000)
        ideal = doc.idealWidth()  # px

        # Convert ideal text width into bubble width (add padding)
        target = int(ideal) + side_padding

        # Clamp bubble width
        bubble_w = max(220, min(max_bubble_w, target))

        # Now set doc width to bubble inner width so it wraps correctly
        inner_w = max(200, bubble_w - side_padding)
        self.setFixedWidth(bubble_w)
        self.set_text_width(inner_w)


class ThinkingBubble(QtWidgets.QFrame):
    def __init__(self, text: str = "⏳ Thinking…", icon_path: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("ThinkingBubble")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)

        self.setStyleSheet(f"""
            #ThinkingBubble {{
                background-color: #f0f7f4;
                border: 2px dashed {SCROLL_HANDLE};
                border-radius: 16px;
            }}
        """)
        _add_shadow(self, blur=14, dy=3, alpha=16)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        if icon_path:
            pm = _round_pixmap(icon_path, size=20)
            if pm is not None:
                icon_label = QtWidgets.QLabel()
                icon_label.setPixmap(pm)
                icon_label.setFixedSize(20, 20)
                layout.addWidget(icon_label)

        text_label = QtWidgets.QLabel(text)
        text_label.setStyleSheet(f"""
            color: {TUTOR_BORDER};
            font-style: italic;
            font-size: 14px;
            background: transparent;
        """)
        layout.addWidget(text_label)
        layout.addStretch()


class VocabBrowser(QtWidgets.QScrollArea):
    """
    - User messages: LEFT aligned
    - Tutor messages: RIGHT aligned
    - Vocab mode highlighting: vocab://
    - Grammar highlighting: grammar://
    """

    wordActivated = QtCore.Signal(str, str)  # word, full context

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._new_words: Set[str] = set()
        self._vocab_mode_enabled = False
        self._messages: list[dict] = []
        self._bubbles: list[QtWidgets.QWidget] = []

        self._tutor_icon_path = "app/resources/images/ai_tutor_icon.png"
        if not Path(self._tutor_icon_path).exists():
            self._tutor_icon_path = ""

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: {BG};
                border: 1px solid {BORDER};
                border-radius: 18px;
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                background: {SCROLL_BG};
                width: 10px;
                border-radius: 5px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {SCROLL_HANDLE};
                border-radius: 4px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {SCROLL_HANDLE_HOVER};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self._container = QtWidgets.QWidget()
        self._container.setStyleSheet("background-color: transparent;")
        self._layout = QtWidgets.QVBoxLayout(self._container)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(10)
        self._layout.addStretch()

        self.setWidget(self._container)

    # -------- sizing logic (this is what you wanted) --------
    def _bubble_max_width(self) -> int:
        vw = self.viewport().width()
        if vw <= 0:
            return 1100
        return max(720, int(vw * 0.94))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        # When chat area width changes, rebuild so widths + heights update
        QtCore.QTimer.singleShot(0, self._rebuild_all)

    # -------- formatting --------
    @staticmethod
    def _escape_html(text: str) -> str:
        return html.escape(text, quote=False)

    def _scroll_to_bottom(self):
        QtCore.QTimer.singleShot(
            35,
            lambda: self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
        )

    def _format_text(self, text: str, apply_vocab: bool = False) -> str:
        safe = self._escape_html(text)
        safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
        safe = safe.replace("\n", "<br>")

        if apply_vocab and self._vocab_mode_enabled and self._new_words:
            for word in sorted(self._new_words, key=len, reverse=True):
                if not word:
                    continue
                pattern = re.compile(rf"\b({re.escape(word)})\b", re.IGNORECASE)
                safe = pattern.sub(
                    r'<a href="vocab://\1" style="color: #168aad; text-decoration: underline;">\1</a>',
                    safe
                )
        return safe

    def _format_with_grammar_errors(self, text: str, errors: list) -> str:
        """
        Format text with grammar error highlights.

        CRITICAL FIX: Instead of trusting backend's start/end indices (which may be
        byte offsets or just wrong), we find each error token in the text ourselves.
        """
        if not errors:
            return self._format_text(text, apply_vocab=False)

        import urllib.parse

        n = len(text)
        text_lower = text.lower()

        # Build a list of (start, end, suggestion) tuples by finding tokens ourselves
        highlights = []
        cursor = 0  # Track where we've already matched (handles repeated words)

        for err in errors:
            if not isinstance(err, dict):
                continue

            # Get the original token that has the error
            token = (err.get("original") or "").strip()
            suggestion = err.get("suggestion") or ""

            if not token:
                # If no token provided, try to use start/end as fallback
                try:
                    start = int(err.get("start", -1))
                    end = int(err.get("end", -1))
                    if 0 <= start < end <= n:
                        token = text[start:end]
                except (TypeError, ValueError):
                    continue

            if not token:
                continue

            # Find this token in the text (case-insensitive), starting from cursor
            token_lower = token.lower()
            idx = text_lower.find(token_lower, cursor)

            if idx == -1:
                # Try from beginning if not found after cursor
                idx = text_lower.find(token_lower)

            if idx != -1:
                # Use actual text (preserves original case)
                actual_token = text[idx:idx + len(token)]
                highlights.append({
                    "start": idx,
                    "end": idx + len(token),
                    "token": actual_token,
                    "suggestion": suggestion
                })
                cursor = idx + len(token)

        if not highlights:
            return self._format_text(text, apply_vocab=False)

        # Sort by start position and remove overlaps
        highlights.sort(key=lambda x: x["start"])

        # Remove overlapping highlights (keep first one)
        filtered = []
        last_end = 0
        for h in highlights:
            if h["start"] >= last_end:
                filtered.append(h)
                last_end = h["end"]

        # Build HTML
        parts = []
        pos = 0

        for h in filtered:
            start = h["start"]
            end = h["end"]
            token = h["token"]
            suggestion = h["suggestion"]

            # Add text before this highlight
            if pos < start:
                parts.append(self._escape_html(text[pos:start]))

            # Add highlighted token
            href = "grammar://" + urllib.parse.quote(suggestion or "")
            escaped_token = self._escape_html(token)

            parts.append(
                f'<a href="{href}" style="color: #c9a227; text-decoration: underline; '
                f'text-decoration-color: #c9a227; text-decoration-style: wavy;">{escaped_token}</a>'
            )
            pos = end

        # Add remaining text
        if pos < n:
            parts.append(self._escape_html(text[pos:]))

        result = "".join(parts)
        result = result.replace("\n", "<br>")
        return result

    # -------- building bubbles --------
    def _create_bubble(self, msg: dict) -> QtWidgets.QWidget:
        msg_type = msg.get("type", "user")
        content = msg.get("content", "")

        wrapper = QtWidgets.QWidget()
        wrapper.setStyleSheet("background: transparent;")
        hl = QtWidgets.QHBoxLayout(wrapper)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)

        max_w = self._bubble_max_width()

        if msg_type == "user":
            grammar_errors = msg.get("grammar_errors", [])
            formatted = (
                self._format_with_grammar_errors(content, grammar_errors)
                if grammar_errors else
                self._format_text(content, False)
            )

            bubble = MessageBubble(formatted, is_user=True)
            bubble.setMaximumWidth(max_w)
            bubble.content_label.anchorClicked.connect(self._on_grammar_link_clicked)

            # LEFT
            hl.addWidget(bubble, 0, QtCore.Qt.AlignLeft)
            hl.addStretch(1)

            # Compact width for short user messages
            QtCore.QTimer.singleShot(0, lambda b=bubble, mw=max_w: b.set_compact_width(mw))

        elif msg_type == "tutor":
            formatted = self._format_text(content, apply_vocab=True)
            bubble = MessageBubble(formatted, is_user=False, icon_path=self._tutor_icon_path)
            bubble.setMaximumWidth(max_w)
            bubble.content_label.anchorClicked.connect(self._on_vocab_link_clicked)

            # RIGHT: space on left, bubble grows on right
            hl.addStretch(1)
            hl.addWidget(bubble, 3)

            QtCore.QTimer.singleShot(0, lambda b=bubble: b.set_text_width(max(260, b.width() - 40)))

        elif msg_type == "thinking":
            bubble = ThinkingBubble(content, self._tutor_icon_path)
            hl.addStretch(1)
            hl.addWidget(bubble)

        return wrapper

    def _rebuild_all(self):
        # remove old
        for b in self._bubbles:
            self._layout.removeWidget(b)
            b.deleteLater()
        self._bubbles.clear()

        # clear layout items
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        # add new
        for msg in self._messages:
            bubble_wrap = self._create_bubble(msg)
            self._bubbles.append(bubble_wrap)
            self._layout.addWidget(bubble_wrap)

        self._layout.addStretch()
        self._scroll_to_bottom()

    # -------- link handlers --------
    def _on_vocab_link_clicked(self, url):
        url_str = url.toString() if hasattr(url, "toString") else str(url)
        if url_str.startswith("vocab://"):
            word = url_str[8:].lower()
            self.wordActivated.emit(word, self.toPlainText())

    def _on_grammar_link_clicked(self, url):
        url_str = url.toString() if hasattr(url, "toString") else str(url)
        if url_str.startswith("grammar://"):
            import urllib.parse
            suggestion = urllib.parse.unquote(url_str[10:])
            if suggestion:
                QtWidgets.QMessageBox.information(self, "Grammar Correction", f"✅ Correct: {suggestion}")

    def toPlainText(self) -> str:
        lines = []
        for msg in self._messages:
            prefix = "You: " if msg.get("type") == "user" else "Tutor: "
            content = msg.get("content", "")
            content = re.sub(r"<[^>]+>", "", content)
            lines.append(prefix + content)
        return "\n\n".join(lines)

    # -------- public API --------
    def clear(self) -> None:
        self._messages.clear()
        self._new_words.clear()
        self._rebuild_all()

    def set_vocab_mode(self, enabled: bool) -> None:
        self._vocab_mode_enabled = enabled
        self._rebuild_all()

    def set_new_words(self, new_words: Iterable[str]) -> None:
        self._new_words = {str(w).strip().lower() for w in new_words if w and str(w).strip()}
        self._rebuild_all()

    def add_new_words(self, new_words: Iterable[str]) -> None:
        for w in new_words:
            if w and str(w).strip():
                self._new_words.add(str(w).strip().lower())
        self._rebuild_all()

    def append(self, html_text: str) -> None:
        plain = re.sub(r"<[^>]+>", "", html_text)
        if plain.strip():
            self._messages.append({"type": "tutor", "content": plain})
            self._rebuild_all()

    def append_user(self, text: str, grammar_errors: list | None = None) -> None:
        self._messages.append({"type": "user", "content": text, "grammar_errors": grammar_errors or []})
        self._rebuild_all()

    def show_thinking(self, text: str = "⏳ Thinking…") -> None:
        self._messages.append({"type": "thinking", "content": text})
        self._rebuild_all()

    def append_bot(self, text: str, new_words: Iterable[str] = ()) -> None:
        for w in new_words:
            if w and str(w).strip():
                self._new_words.add(str(w).strip().lower())

        if self._messages and self._messages[-1].get("type") == "thinking":
            self._messages.pop()

        self._messages.append({"type": "tutor", "content": text})
        self._rebuild_all()

    # compatibility
    def anchorAt(self, pos) -> str:
        return ""

    def viewport(self):
        return self._container