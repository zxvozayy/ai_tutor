# app/ui/vocab_browser.py
from __future__ import annotations

import html
import re
from typing import Iterable, Set
from html import escape as html_escape
from PySide6.QtGui import QPixmap, QPainter, QPainterPath


from PySide6 import QtWidgets, QtGui, QtCore


class VocabBrowser(QtWidgets.QTextBrowser):
    """
    QTextBrowser that:
    - displays chat messages
    - can underline 'new vocabulary' words when vocab mode is enabled
    - underlines ONLY in tutor (AI) messages, not user messages
    - emits wordActivated(word, full_context) when a new word is double-clicked
    """

    wordActivated = QtCore.Signal(str, str)  # word, full context

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self._new_words: Set[str] = set()
        self._has_thinking = False
        self._vocab_mode_enabled = False
    def _make_round_icon(self, size: int = 18) -> str:
        """Yuvarlak, şeffaf PNG'yi base64 olarak döndürür."""
        path = "app/resources/images/ai_tutor_logo.png"

        pix = QtGui.QPixmap(path)
        if pix.isNull():
            return ""

        # Logoyu küçült
        pix = pix.scaled(
            size, size,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation
        )

        # Şeffaf zeminli boş pixmap
        rounded = QtGui.QPixmap(size, size)
        rounded.fill(QtCore.Qt.transparent)

        # Daire maskesi çiz
        painter = QtGui.QPainter(rounded)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        circle = QtGui.QPainterPath()
        circle.addEllipse(0, 0, size, size)
        painter.setClipPath(circle)
        painter.drawPixmap(0, 0, pix)
        painter.end()

        # PNG'yi base64 string'e çevir
        ba = QtCore.QByteArray()
        buf = QtCore.QBuffer(ba)
        buf.open(QtCore.QIODevice.WriteOnly)
        rounded.save(buf, "PNG")
        buf.close()

        b64 = bytes(ba.toBase64()).decode()
        return f"data:image/png;base64,{b64}"

    # ---------- helpers ----------
    @staticmethod
    def _escape_html(text: str) -> str:
        return html.escape(text, quote=False)

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
        doc = self.document()
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

    # ---------- public API for MainWindow ----------
    def set_vocab_mode(self, enabled: bool) -> None:
        """
        Turn vocabulary highlighting on or off.
        - When enabled, all known new words in tutor messages are underlined.
        - When disabled, underlines are removed.
        """
        self._vocab_mode_enabled = enabled
        if enabled:
            self._apply_underlines()
        else:
            self._clear_vocab_formatting()

    def append_user(self, text: str) -> None:
        safe = self._escape_html(text)
        safe = safe.replace("\n", "<br>")

        html = f"""
        <table cellspacing="0" cellpadding="0" style="margin:2px 0;">
          <tr>
            <td style="width:26px; vertical-align:top; padding-top:2px;"></td>
            <td style="vertical-align:top;">
                <b>You:</b> {safe}
            </td>
          </tr>
        </table>
        """

        self.append(html)

    def show_thinking(self, text: str = "⏳ Thinking…") -> None:
        safe = self._escape_html(text)
        self.append(f"<p><b>Tutor:</b><br>{safe}</p>")
        self._has_thinking = True

    def append_bot(self, text: str, new_words: Iterable[str]) -> None:
        # Track new words globally for this chat (for all tutor messages)
        for w in new_words:
            if w:
                self._new_words.add(w.lower())

        # Remove thinking placeholder (if it exists)
        self._remove_thinking_if_any()

        safe = self._escape_html(text)
        safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
        safe = safe.replace("\n", "<br>")

        # Yuvarlak küçük logo (base64)
        logo_b64 = self._make_round_icon(18)
        if logo_b64:
            icon_html = (
                f'<img src="{logo_b64}" width="18" height="18" '
                f'style="vertical-align:middle;">'
            )
        else:
            icon_html = ""

        # 2 sütunlu tablo: solda ikon, sağda metin
        html = f"""
        <table cellspacing="0" cellpadding="0" style="margin:2px 0;">
          <tr>
            <td style="width:26px; vertical-align:top; padding-top:2px;">
                {icon_html}
            </td>
            <td style="vertical-align:top;">
                <b>Tutor:</b> {safe}
            </td>
          </tr>
        </table>
        """

        self.append(html)
        self._apply_underlines()

    # ---------- double-click handling ----------
    def mouseDoubleClickEvent(self, event: QtGui.QMouseEvent) -> None:
        cursor = self.cursorForPosition(event.pos())
        cursor.select(QtGui.QTextCursor.WordUnderCursor)
        raw = cursor.selectedText()
        # Strip common punctuation around the word
        word = raw.strip(".,!?;:\"'()[]{}").lower()

        if word and word in self._new_words:
            context = self.toPlainText()
            self.wordActivated.emit(word, context)

        super().mouseDoubleClickEvent(event)
