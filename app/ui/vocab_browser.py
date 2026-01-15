# app/ui/vocab_browser.py
from __future__ import annotations

import html
import re
from typing import Iterable, Set
from pathlib import Path

from PySide6 import QtWidgets, QtGui, QtCore


class VocabBrowser(QtWidgets.QTextBrowser):
    """
    QTextBrowser that:
    - displays chat messages
    - can underline 'new vocabulary' words when vocab mode is enabled
    - underlines ONLY in tutor (AI) messages, not user messages
    - emits wordActivated(word, full_context) when a new word is double-clicked
      BUT ONLY when vocab mode is enabled
    """

    wordActivated = QtCore.Signal(str, str)  # word, full context

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self._new_words: Set[str] = set()
        self._has_thinking = False
        self._vocab_mode_enabled = False

        # Cache icon URI once (UI only)
        self._tutor_icon_uri = self._make_file_uri("app/resources/images/ai_tutor_icon.png")

        # Make paragraphs look clean (fix "yamuk" feeling)
        self.document().setDefaultStyleSheet("""
            p { margin: 6px 0 10px 0; line-height: 1.45; }
            b { font-weight: 700; }
        """)

    # ---------- helpers ----------
    @staticmethod
    def _escape_html(text: str) -> str:
        return html.escape(text, quote=False)

    @staticmethod
    def _make_file_uri(rel_path: str) -> str:
        """
        Convert a relative path to a file URI that QTextBrowser can load.
        If the file doesn't exist, returns empty string (icon just won't render).
        """
        try:
            p = Path(rel_path).resolve()
            if p.exists():
                return p.as_uri()
        except Exception:
            pass
        return ""

    def _tutor_header_html(self) -> str:
        """
        IMPORTANT: keeps literal 'Tutor:' text visible so underline logic still works.
        Also pushes icon a bit down so it doesn't "float".
        """
        if self._tutor_icon_uri:
            return (
                "<span style='display:inline-flex; align-items:baseline; gap:8px;'>"
                f"  <img src='{self._tutor_icon_uri}' width='20' height='20' "
                "       style='margin-top:6px; border-radius:50%; "
                "              border:1px solid #E9EAF2; padding:2px; background:#FFFFFF;' />"
                "  <span style='font-weight:800; color:#3B2FEA;'>Tutor:</span>"
                "</span>"
            )
        return "<span style='font-weight:800; color:#3B2FEA;'>Tutor:</span>"

    # ---------- underline logic ----------
    def _apply_underlines(self) -> None:
        """
        Apply underline formatting to all known 'new words'
        BUT ONLY in blocks that belong to the tutor (AI).
        """
        if not self._vocab_mode_enabled or not self._new_words:
            return

        doc = self.document()
        fmt = QtGui.QTextCharFormat()
        fmt.setFontUnderline(True)
        fmt.setUnderlineStyle(QtGui.QTextCharFormat.SingleUnderline)

        cursor = self.textCursor()
        cursor.beginEditBlock()

        for word in self._new_words:
            if not word:
                continue

            regex = QtCore.QRegularExpression(
                rf"\b{QtCore.QRegularExpression.escape(word)}\b",
                QtCore.QRegularExpression.CaseInsensitiveOption,
            )

            search_cursor = QtGui.QTextCursor(doc)
            match_cursor = doc.find(regex, search_cursor)
            while not match_cursor.isNull():
                block_text = match_cursor.block().text()
                # 🔥 only underline inside tutor messages
                if "Tutor:" in block_text and "You:" not in block_text:
                    match_cursor.mergeCharFormat(fmt)

                match_cursor = doc.find(regex, match_cursor)

        cursor.endEditBlock()

    def _clear_vocab_formatting(self) -> None:
        """
        Remove underline formatting from the entire document
        (without touching bold/color etc.).
        """
        cursor = self.textCursor()
        cursor.beginEditBlock()

        cursor.select(QtGui.QTextCursor.Document)
        fmt = QtGui.QTextCharFormat()
        fmt.setFontUnderline(False)
        fmt.setUnderlineStyle(QtGui.QTextCharFormat.NoUnderline)
        cursor.mergeCharFormat(fmt)

        cursor.endEditBlock()

    def _remove_thinking_if_any(self) -> None:
        """Remove the last 'Thinking…' line if present."""
        if not self._has_thinking and not self.toPlainText().strip().endswith("Thinking…"):
            return

        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        cursor.select(QtGui.QTextCursor.BlockUnderCursor)
        cursor.removeSelectedText()
        cursor.deletePreviousChar()
        self._has_thinking = False

    # ---------- public API ----------
    def set_vocab_mode(self, enabled: bool) -> None:
        self._vocab_mode_enabled = enabled
        if enabled:
            self._apply_underlines()
        else:
            self._clear_vocab_formatting()

    def append_user(self, text: str) -> None:
        safe = self._escape_html(text).replace("\n", "<br>")
        # Keep it simple & stable
        self.append(f"<p><b>You:</b><br>{safe}</p>")

    def show_thinking(self, text: str = "⏳ Thinking…") -> None:
        safe = self._escape_html(text).replace("\n", "<br>")
        header = self._tutor_header_html()
        self.append(f"<p>{header}<br>{safe}</p>")
        self._has_thinking = True

    def append_bot(self, text: str, new_words: Iterable[str]) -> None:
        # Track new words globally for this chat (for all tutor messages)
        for w in new_words:
            if w:
                self._new_words.add(w.lower())

        # Remove thinking placeholder (if it exists)
        self._remove_thinking_if_any()

        safe = self._escape_html(text)
        # markdown-style **bold**
        safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
        safe = safe.replace("\n", "<br>")

        header = self._tutor_header_html()
        self.append(f"<p>{header}<br>{safe}</p>")

        # Underline only in tutor blocks (only if mode enabled)
        self._apply_underlines()

    # ---------- double-click handling ----------
    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        if not self._vocab_mode_enabled:
            return super().mouseDoubleClickEvent(event)

        cursor = self.cursorForPosition(event.pos())
        cursor.select(QtGui.QTextCursor.WordUnderCursor)
        raw = cursor.selectedText()
        word = raw.strip(".,!?;:\"'()[]{}").lower()

        if word and word in self._new_words:
            context = self.toPlainText()
            self.wordActivated.emit(word, context)

        super().mouseDoubleClickEvent(event)
