# app/ui/vocab_browser.py
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Iterable, Set

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
        self._messages_html = []  # Store all messages as HTML

        self._tutor_icon_uri = self._make_file_uri("app/resources/images/ai_tutor_icon.png")

    # ---------- helpers ----------
    @staticmethod
    def _escape_html(text: str) -> str:
        return html.escape(text, quote=False)

    @staticmethod
    def _make_file_uri(rel_path: str) -> str:
        try:
            p = Path(rel_path).resolve()
            if p.exists():
                return p.as_uri()
        except Exception:
            pass
        return ""

    def _tutor_header_inline(self) -> str:
        """
        IMPORTANT: Keep literal 'Tutor:' visible because underline logic checks for it.
        """
        if self._tutor_icon_uri:
            return (
                f'<img src="{self._tutor_icon_uri}" width="18" height="18" '
                f'style="vertical-align:middle; border-radius:9px; margin-right:6px;" />'
                f'<span style="font-weight:700; color:#3B2FEA;">Tutor:</span>'
            )
        return '<span style="font-weight:700; color:#3B2FEA;">Tutor:</span>'

    def _render_all_messages(self) -> None:
        """Re-render all stored messages."""
        full_html = """
<!DOCTYPE html>
<html>
<head>
<style>
body {
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 14px;
    color: #1F2330;
    padding: 10px;
    margin: 0;
}
.message {
    margin: 10px 0;
    clear: both;
}
.message-left {
    text-align: left;
}
.message-right {
    text-align: right;
}
.bubble {
    display: inline-block;
    max-width: 70%;
    min-width: 150px;
    padding: 12px 16px;
    border-radius: 16px;
    text-align: left;
    word-wrap: break-word;
}
.bubble-left {
    background: #FFFFFF;
    border: 1px solid #E0E2E8;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.bubble-right {
    background: #F4F4F8;
    border: 1px solid #E0E2E8;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.header {
    margin-bottom: 6px;
    font-weight: 700;
    color: #3B2FEA;
}
.content {
    line-height: 1.5;
}
</style>
</head>
<body>
"""

        for msg_html in self._messages_html:
            full_html += msg_html

        full_html += """
</body>
</html>
"""

        self.setHtml(full_html)

        # Scroll to bottom
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ---------- underline logic ----------
    def _apply_underlines(self) -> None:
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
                if "Tutor:" in block_text and "You:" not in block_text:
                    match_cursor.mergeCharFormat(fmt)
                match_cursor = doc.find(regex, match_cursor)

        cursor.endEditBlock()

    def _clear_vocab_formatting(self) -> None:
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.select(QtGui.QTextCursor.Document)
        fmt = QtGui.QTextCharFormat()
        fmt.setFontUnderline(False)
        fmt.setUnderlineStyle(QtGui.QTextCharFormat.NoUnderline)
        cursor.mergeCharFormat(fmt)
        cursor.endEditBlock()

    # ---------- public API ----------
    def set_vocab_mode(self, enabled: bool) -> None:
        self._vocab_mode_enabled = enabled
        if enabled:
            self._apply_underlines()
        else:
            self._clear_vocab_formatting()

    def append_user(self, text: str) -> None:
        safe = self._escape_html(text).replace("\n", "<br>")

        msg_html = f'''
<div class="message message-right">
    <div class="bubble bubble-right">
        <div class="header">You:</div>
        <div class="content">{safe}</div>
    </div>
</div>
'''

        self._messages_html.append(msg_html)
        self._render_all_messages()

    def show_thinking(self, text: str = "⏳ Thinking…") -> None:
        safe = self._escape_html(text).replace("\n", "<br>")
        header = self._tutor_header_inline()

        msg_html = f'''
<div class="message message-left" id="thinking-message">
    <div class="bubble bubble-left">
        <div class="header">{header}</div>
        <div class="content">{safe}</div>
    </div>
</div>
'''

        self._messages_html.append(msg_html)
        self._has_thinking = True
        self._render_all_messages()

    def append_bot(self, text: str, new_words: Iterable[str]) -> None:
        for w in new_words:
            if w:
                self._new_words.add(w.lower())

        # Remove thinking message if present
        if self._has_thinking and self._messages_html:
            # Remove the last message if it's a thinking message
            if "thinking-message" in self._messages_html[-1] or "Thinking" in self._messages_html[-1]:
                self._messages_html.pop()
            self._has_thinking = False

        safe = self._escape_html(text)
        safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
        safe = safe.replace("\n", "<br>")

        header = self._tutor_header_inline()

        msg_html = f'''
<div class="message message-left">
    <div class="bubble bubble-left">
        <div class="header">{header}</div>
        <div class="content">{safe}</div>
    </div>
</div>
'''

        self._messages_html.append(msg_html)
        self._render_all_messages()
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
