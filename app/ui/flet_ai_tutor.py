"""
🔥 AI TUTOR - FLET EDITION (STABLE) 🔥
One-shot fix: NO ft.icons usage (icons differ across Flet builds)
Uses emoji/text "icons" so it works on ANY Flet version.

Features (graceful demo fallback):
- Login/Auth (if db_supabase exists)
- Sessions list (if db_supabase exists)
- Chat UI + typing indicator
- Topic + Persona dropdowns
- Weak points / Summary / Vocabulary dialogs
"""

from __future__ import annotations

import os
import sys
import asyncio
from datetime import datetime
from typing import Optional

import flet as ft

# ==========================================================
# Make "from app...." imports work even when running as script
# ==========================================================
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ==========================================================
# Padding/Margin compatibility (avoid deprecated helpers)
# ==========================================================
def PadAll(v: int):
    return ft.Padding.all(v) if hasattr(ft, "Padding") else ft.padding.all(v)

def PadOnly(left=None, top=None, right=None, bottom=None):
    if hasattr(ft, "Padding"):
        return ft.Padding(left=left, top=top, right=right, bottom=bottom)
    return ft.padding.only(left=left, top=top, right=right, bottom=bottom)

def PadSymmetric(horizontal: int = 0, vertical: int = 0):
    if hasattr(ft, "Padding"):
        return ft.Padding.symmetric(horizontal=horizontal, vertical=vertical)
    return ft.padding.symmetric(horizontal=horizontal, vertical=vertical)

def MarOnly(left=None, top=None, right=None, bottom=None):
    if hasattr(ft, "Margin"):
        return ft.Margin(left=left, top=top, right=right, bottom=bottom)
    return ft.margin.only(left=left, top=top, right=right, bottom=bottom)


# ============================================
# IMPORTS FROM YOUR PROJECT (optional)
# ============================================
try:
    from app.engines.gemini_engine import GeminiEngine
    from app.services.db_supabase import (
        sign_in, sign_up, sign_out, load_session_if_any,
        current_user_id, current_user_email,
        get_or_create_default_session, list_user_sessions,
        create_session, rename_session, delete_session,
        add_message, list_messages,
        get_current_profile, get_recent_learning_events,
    )
    from app.modules.vocab_store import get_known_words_set, get_user_vocab
    IMPORTS_OK = True
except Exception as e:
    print(f"⚠️ Import error: {e}")
    print("Running in demo mode...")
    IMPORTS_OK = False


# ============================================
# MESSAGE CLASS
# ============================================
class Message:
    def __init__(self, sender: str, text: str, timestamp: datetime = None, msg_id: int = None):
        self.sender = sender
        self.text = text
        self.timestamp = timestamp or datetime.now()
        self.id = msg_id


# ============================================
# TOPIC PROMPTS & PERSONAS
# ============================================
TOPIC_PROMPTS = {
    "Free Chat": "",
    "At the Restaurant": "You are a waiter talking to a customer in a restaurant.",
    "Shopping": "You are a shop assistant helping a customer buy something.",
    "Ordering Coffee": "You are a barista taking an order at a coffee shop.",
    "At the Airport": "You are a flight attendant helping a traveler.",
    "Hotel Check-in": "You are a hotel receptionist checking in a guest.",
    "Job Interview": "You are the interviewer asking questions in a job interview.",
    "Doctor Appointment": "You are a doctor having a check-up conversation.",
}

PERSONA_STYLES = {
    "Default": "Use a clear, helpful but neutral tone.",
    "Friendly 😊": "Be warm, encouraging and supportive.",
    "Formal 🎓": "Use polite, academic and professional language.",
    "Coach 💪": "Act like a motivating language coach.",
    "Comedian 😂": "Keep a light, humorous tone with small jokes.",
}


# ============================================
# Small UI helpers (emoji icons)
# ============================================
def emoji_badge(emoji: str, bg: str, size: int = 18, box: int = 36):
    return ft.Container(
        content=ft.Text(emoji, size=size, color="white"),
        width=box,
        height=box,
        border_radius=box // 2,
        bgcolor=bg,
        alignment=ft.Alignment(0, 0),
    )


def emoji_button(emoji: str, tooltip: str, on_click, bg: str, fg: str = "white", box: int = 40):
    return ft.Container(
        content=ft.Text(emoji, size=18, color=fg),
        width=box,
        height=box,
        border_radius=box // 2,
        bgcolor=bg,
        alignment=ft.Alignment(0, 0),
        on_click=on_click,
        tooltip=tooltip,
    )


# ============================================
# LOGIN DIALOG
# ============================================
def show_login_dialog(page: ft.Page, on_success):
    email_field = ft.TextField(
        label="Email",
        border_radius=12,
        bgcolor="white",
        border_color="#b5e48c",
        focused_border_color="#168aad",
    )

    password_field = ft.TextField(
        label="Password",
        password=True,
        can_reveal_password=True,
        border_radius=12,
        bgcolor="white",
        border_color="#b5e48c",
        focused_border_color="#168aad",
    )

    error_text = ft.Text("", color="red", size=12)
    is_signup = ft.Checkbox(label="Create new account", value=False)

    def do_login(e):
        email = (email_field.value or "").strip()
        pwd = (password_field.value or "").strip()

        if not email or not pwd:
            error_text.value = "Please enter email and password"
            page.update()
            return

        try:
            if is_signup.value:
                sign_up(email, pwd)
                sign_in(email, pwd)
            else:
                sign_in(email, pwd)

            page.close(dialog)
            on_success()
        except Exception as ex:
            error_text.value = f"Error: {str(ex)[:120]}"
            page.update()

    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text("Welcome to AI Tutor", weight=ft.FontWeight.BOLD, color="#184e77"),
        content=ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Text("🎓", size=44),
                        alignment=ft.Alignment(0, 0),
                        padding=PadOnly(bottom=14),
                    ),
                    email_field,
                    password_field,
                    is_signup,
                    error_text,
                ],
                spacing=12,
                tight=True,
            ),
            width=330,
            padding=PadAll(10),
        ),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: page.close(dialog)),
            ft.ElevatedButton("Continue", on_click=do_login, bgcolor="#168aad", color="white"),
        ],
    )

    page.open(dialog)


# ============================================
# MAIN APP CLASS
# ============================================
class AITutorApp:
    def __init__(self, page: ft.Page):
        self.page = page

        self.messages: list[Message] = []
        self.session_id: Optional[int] = None
        self.sessions: list[dict] = []
        self.engine = None

        self.current_topic = "Free Chat"
        self.current_persona = "Default"

        self.user_id = None
        self.user_email = None
        self.known_words = set()

        # Page setup
        self.page.title = "AI Tutor ✨"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 0
        self.page.spacing = 0
        self.page.window.width = 1200
        self.page.window.height = 800
        self.page.window.min_width = 860
        self.page.window.min_height = 600

        # Engine
        if IMPORTS_OK:
            try:
                self.engine = GeminiEngine()
            except Exception as e:
                print(f"Engine init error: {e}")
                self.engine = None

        self.check_auth_and_build()

    def check_auth_and_build(self):
        if IMPORTS_OK and load_session_if_any():
            self.on_login_success()
        elif IMPORTS_OK:
            show_login_dialog(self.page, self.on_login_success)
        else:
            self.build_ui()
            self.add_welcome_message()

    def on_login_success(self):
        try:
            self.user_id = current_user_id()
            self.user_email = current_user_email()

            if self.user_id:
                try:
                    self.known_words = get_known_words_set(self.user_id)
                except Exception:
                    self.known_words = set()

            self.load_sessions()
        except Exception as e:
            print(f"Login success error: {e}")

        self.build_ui()

        if self.session_id:
            self.load_messages()
        else:
            self.add_welcome_message()

    def load_sessions(self):
        try:
            self.sessions = list_user_sessions(limit=50)
            if self.sessions:
                self.session_id = self.sessions[0]["id"]
            else:
                self.session_id = get_or_create_default_session()
                self.sessions = list_user_sessions(limit=50)
        except Exception as e:
            print(f"Load sessions error: {e}")
            self.sessions = []
            self.session_id = None

    def load_messages(self):
        if not self.session_id or not IMPORTS_OK:
            return

        try:
            msgs = list_messages(self.session_id, limit=200)
            self.messages.clear()
            self.chat_list.controls.clear()

            for m in msgs:
                msg = Message(
                    sender="user" if m.get("role") == "user" else "tutor",
                    text=m.get("content", ""),
                    msg_id=m.get("id"),
                )
                self.messages.append(msg)
                self.chat_list.controls.append(self.create_bubble(msg))

            self.page.update()
        except Exception as e:
            print(f"Load messages error: {e}")

    # -----------------------------
    # UI BUILD
    # -----------------------------
    def build_ui(self):
        # Chat list
        self.chat_list = ft.ListView(
            expand=True,
            spacing=8,
            padding=PadAll(20),
            auto_scroll=True,
        )

        # Typing indicator
        self.typing_indicator = ft.Container(
            content=ft.Row(
                [
                    emoji_badge("🤖", "#52b69a", size=16, box=34),
                    ft.Container(width=8),
                    ft.Container(
                        content=ft.Text("Thinking...", color="#168aad", italic=True, size=13),
                        bgcolor="white",
                        border_radius=16,
                        padding=PadSymmetric(horizontal=16, vertical=10),
                    ),
                ]
            ),
            visible=False,
            padding=PadOnly(left=16, bottom=10),
        )

        # Input
        self.msg_input = ft.TextField(
            hint_text="Type a message...",
            border=ft.InputBorder.NONE,
            bgcolor="transparent",
            expand=True,
            text_size=14,
            color="#184e77",
            on_submit=self.send_message,
        )

        send_btn = emoji_button("📨", "Send", self.send_message, bg="#168aad", box=46)
        mic_btn = emoji_button("🎙️", "Mic (soon)", self.toggle_mic, bg="#e8f5f0", fg="#168aad", box=46)

        input_bar = ft.Container(
            content=ft.Row(
                [self.msg_input, mic_btn, send_btn],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor="white",
            border_radius=28,
            padding=PadOnly(left=16, top=8, right=8, bottom=8),
            shadow=ft.BoxShadow(blur_radius=15, color="#00000015", offset=ft.Offset(0, 3)),
            margin=MarOnly(left=16, right=16, top=8, bottom=16),
        )

        # Dropdowns
        self.topic_dropdown = ft.Dropdown(
            value=self.current_topic,
            options=[ft.dropdown.Option(t) for t in TOPIC_PROMPTS.keys()],
            width=170,
            border_radius=12,
            bgcolor="#ffffff22",
            color="white",
            border_color="transparent",
        )
        self.topic_dropdown.on_change = self.on_topic_change

        self.persona_dropdown = ft.Dropdown(
            value=self.current_persona,
            options=[ft.dropdown.Option(p) for p in PERSONA_STYLES.keys()],
            width=150,
            border_radius=12,
            bgcolor="#ffffff22",
            color="white",
            border_color="transparent",
        )
        self.persona_dropdown.on_change = self.on_persona_change

        # Level badge
        user_level = "B1"
        if IMPORTS_OK:
            try:
                profile = get_current_profile()
                if profile and profile.get("cefr_level"):
                    user_level = profile["cefr_level"]
            except Exception:
                pass

        header = ft.Container(
            content=ft.Row(
                [
                    emoji_badge("🎓", "#52b69a", size=18, box=48),
                    ft.Column(
                        [
                            ft.Text("AI Tutor", size=20, weight=ft.FontWeight.BOLD, color="white"),
                            ft.Row(
                                [
                                    ft.Container(width=8, height=8, border_radius=4, bgcolor="#76c893"),
                                    ft.Text("Online", size=11, color="#ffffffcc"),
                                ],
                                spacing=5,
                            ),
                        ],
                        spacing=1,
                    ),
                    ft.Container(expand=True),
                    ft.Text("Topic:", color="white", size=12),
                    self.topic_dropdown,
                    ft.Container(width=10),
                    ft.Text("Style:", color="white", size=12),
                    self.persona_dropdown,
                    ft.Container(width=10),
                    ft.Container(
                        content=ft.Text(user_level, color="white", weight=ft.FontWeight.BOLD, size=13),
                        bgcolor="#ffffff33",
                        border_radius=10,
                        padding=PadSymmetric(horizontal=12, vertical=6),
                        tooltip="Your English Level",
                    ),
                    emoji_button("🚪", "Logout", self.logout, bg="#ffffff22", fg="white", box=40),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=PadSymmetric(horizontal=20, vertical=14),
            gradient=ft.LinearGradient(
                colors=["#184e77", "#168aad", "#34a0a4"],
                begin=ft.Alignment(-1, 0),
                end=ft.Alignment(1, 0),
            ),
        )

        # Sidebar session list
        self.session_list = ft.Column([], spacing=4, scroll=ft.ScrollMode.AUTO, expand=True)
        self.refresh_session_list()

        sidebar = ft.Container(
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Text("➕", size=16, color="white"),
                                ft.Text("New Chat", color="white", weight=ft.FontWeight.W_600, size=13),
                            ],
                            spacing=6,
                            alignment=ft.MainAxisAlignment.CENTER,
                        ),
                        bgcolor="#168aad",
                        border_radius=12,
                        padding=PadAll(12),
                        on_click=self.new_chat,
                    ),
                    ft.Container(height=16),
                    ft.Text("Recent Chats", size=11, color="#888", weight=ft.FontWeight.W_600),
                    ft.Container(height=6),
                    self.session_list,
                    ft.Container(expand=True),
                    ft.Divider(color="#eee"),
                    self.sidebar_action("📊", "Weak Points", self.show_weak_points),
                    self.sidebar_action("🧾", "Summary", self.show_summary),
                    self.sidebar_action("📚", "My Vocabulary", self.show_vocabulary),
                ],
                spacing=4,
            ),
            width=240,
            bgcolor="white",
            padding=PadAll(14),
            border=ft.border.only(right=ft.BorderSide(1, "#eee")),
        )

        # Chat area background
        chat_area = ft.Container(
            content=ft.Column([self.chat_list, self.typing_indicator, input_bar], spacing=0, expand=True),
            expand=True,
            gradient=ft.LinearGradient(
                colors=["#d9ed92", "#b5e48c", "#76c893", "#52b69a", "#34a0a4", "#168aad"],
                begin=ft.Alignment(0, -1),
                end=ft.Alignment(0, 1),
            ),
        )

        self.page.controls.clear()
        self.page.add(
            ft.Column(
                [
                    header,
                    ft.Row([sidebar, chat_area], expand=True, spacing=0),
                ],
                spacing=0,
                expand=True,
            )
        )
        self.page.update()

    # ============================================
    # MESSAGE BUBBLE
    # ============================================
    def create_bubble(self, msg: Message):
        is_user = msg.sender == "user"

        avatar = emoji_badge("🙂" if is_user else "🤖", "#168aad" if is_user else "#52b69a", size=16, box=36)

        bubble = ft.Container(
            content=ft.Column(
                [
                    ft.Text(msg.text, color="#184e77", size=14, selectable=True),
                    ft.Text(msg.timestamp.strftime("%H:%M") if msg.timestamp else "", color="#888", size=10),
                ],
                spacing=4,
            ),
            bgcolor="white",
            border_radius=18,
            padding=PadSymmetric(horizontal=14, vertical=12),
            shadow=ft.BoxShadow(blur_radius=8, color="#00000012", offset=ft.Offset(0, 2)),
        )

        if is_user:
            return ft.Container(
                content=ft.Row(
                    [ft.Container(expand=True), bubble, ft.Container(width=8), avatar],
                    vertical_alignment=ft.CrossAxisAlignment.END,
                ),
                padding=PadSymmetric(horizontal=16, vertical=4),
            )
        else:
            return ft.Container(
                content=ft.Row(
                    [avatar, ft.Container(width=8), bubble, ft.Container(expand=True)],
                    vertical_alignment=ft.CrossAxisAlignment.END,
                ),
                padding=PadSymmetric(horizontal=16, vertical=4),
            )

    # ============================================
    # SIDEBAR HELPERS
    # ============================================
    def sidebar_action(self, emoji: str, label: str, on_click):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Text(emoji, size=16),
                    ft.Text(label, color="#184e77", size=12),
                ],
                spacing=10,
            ),
            padding=PadAll(10),
            border_radius=8,
            on_click=on_click,
        )

    def refresh_session_list(self):
        self.session_list.controls.clear()

        # Demo sessions if imports not available
        if not IMPORTS_OK:
            if not self.sessions:
                self.sessions = [{"id": 1, "title": "Demo Chat"}]
                self.session_id = 1

        for s in (self.sessions or [])[:12]:
            is_active = s["id"] == self.session_id
            title = s.get("title", f"Chat {s['id']}")

            item = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Text("💬", size=14),
                            width=32,
                            height=32,
                            border_radius=8,
                            bgcolor="#e8f5f0" if is_active else "#f5f5f5",
                            alignment=ft.Alignment(0, 0),
                        ),
                        ft.Text(
                            (title[:20] + "...") if len(title) > 20 else title,
                            size=12,
                            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400,
                            color="#184e77",
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Text("✖", size=12, color="#999"),
                            width=24,
                            height=24,
                            border_radius=12,
                            visible=(not is_active and IMPORTS_OK),
                            alignment=ft.Alignment(0, 0),
                            on_click=lambda e, sid=s["id"]: self.delete_chat(sid),
                        ),
                    ],
                    spacing=8,
                ),
                bgcolor="#f0faf5" if is_active else "transparent",
                border_radius=10,
                padding=PadAll(8),
                border=ft.border.all(1, "#b5e48c") if is_active else None,
                on_click=lambda e, sid=s["id"]: self.switch_session(sid),
                data=s["id"],
            )
            self.session_list.controls.append(item)

    # ============================================
    # ACTIONS
    # ============================================
    async def send_message(self, e):
        text = (self.msg_input.value or "").strip()
        if not text:
            return

        self.msg_input.value = ""
        self.page.update()

        user_msg = Message("user", text)
        self.messages.append(user_msg)
        self.chat_list.controls.append(self.create_bubble(user_msg))

        if IMPORTS_OK and self.session_id:
            try:
                add_message(self.session_id, "user", text)
            except Exception as ex:
                print(f"Save error: {ex}")

        self.typing_indicator.visible = True
        self.page.update()

        def build_prompt():
            prompt = text
            if self.current_topic != "Free Chat":
                topic_prompt = TOPIC_PROMPTS.get(self.current_topic, "")
                prompt = f"[TOPIC: {self.current_topic}]\n{topic_prompt}\n\n{text}"
            if self.current_persona != "Default":
                style = PERSONA_STYLES.get(self.current_persona, "")
                prompt = f"[STYLE: {style}]\n\n{prompt}"
            return prompt

        def get_response_sync():
            if self.engine:
                try:
                    return self.engine.ask(build_prompt(), session_id=self.session_id)
                except Exception as ex:
                    return f"⚠️ Engine error: {ex}"
            return f"Demo response to: {text}"

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, get_response_sync)

        self.typing_indicator.visible = False

        ai_msg = Message("tutor", response)
        self.messages.append(ai_msg)
        self.chat_list.controls.append(self.create_bubble(ai_msg))

        if IMPORTS_OK and self.session_id:
            try:
                add_message(self.session_id, "assistant", response)
            except Exception:
                pass

        self.page.update()

    def new_chat(self, e):
        if IMPORTS_OK:
            try:
                result = create_session("New Chat")
                self.session_id = result["id"]
                self.sessions = list_user_sessions(limit=50)
            except Exception as ex:
                print(f"New chat error: {ex}")
        else:
            new_id = (max([s["id"] for s in self.sessions]) + 1) if self.sessions else 1
            self.sessions.insert(0, {"id": new_id, "title": "Demo Chat"})
            self.session_id = new_id

        self.refresh_session_list()
        self.messages.clear()
        self.chat_list.controls.clear()
        self.add_welcome_message()
        self.page.update()

    def switch_session(self, session_id: int):
        self.session_id = session_id
        self.refresh_session_list()

        if IMPORTS_OK:
            self.load_messages()
        else:
            self.messages.clear()
            self.chat_list.controls.clear()
            self.add_welcome_message()

        self.page.update()

    def delete_chat(self, session_id: int):
        if not IMPORTS_OK:
            return
        try:
            delete_session(session_id)
            self.sessions = list_user_sessions(limit=50)

            if self.session_id == session_id:
                if self.sessions:
                    self.session_id = self.sessions[0]["id"]
                    self.load_messages()
                else:
                    self.session_id = None
                    self.new_chat(None)

            self.refresh_session_list()
            self.page.update()
        except Exception as ex:
            print(f"Delete error: {ex}")

    def toggle_mic(self, e):
        self.page.open(ft.SnackBar(ft.Text("Mic feature coming soon!")))

    def on_topic_change(self, e):
        self.current_topic = self.topic_dropdown.value

    def on_persona_change(self, e):
        self.current_persona = self.persona_dropdown.value

    def logout(self, e):
        if IMPORTS_OK:
            try:
                sign_out()
            except Exception:
                pass
        self.page.window.close()

    def add_welcome_message(self):
        welcome = Message(
            "tutor",
            "Hello! 👋 I'm your AI English Tutor!\n\n"
            "I'm here to help you improve your English. You can:\n"
            "• Practice conversations with me\n"
            "• Ask grammar questions\n"
            "• Learn new vocabulary\n"
            "• Choose a topic from the dropdown above\n\n"
            "What would you like to work on today? 😊",
        )
        self.messages.append(welcome)
        self.chat_list.controls.append(self.create_bubble(welcome))

    # ============================================
    # DIALOGS
    # ============================================
    def show_weak_points(self, e):
        content = "No learning data yet. Chat more to see your weak points!"

        if IMPORTS_OK:
            try:
                events = get_recent_learning_events(limit=100)
                if events:
                    from collections import Counter
                    cats = Counter()
                    for ev in events:
                        payload = ev.get("payload", {}) or {}
                        for c in payload.get("grammar_categories", []) or []:
                            cats[c] += 1
                    if cats:
                        lines = ["Your focus areas:\n"]
                        for cat, count in cats.most_common(5):
                            lines.append(f"• {cat.replace('_', ' ').title()}: {count}x")
                        content = "\n".join(lines)
            except Exception:
                pass

        dialog = ft.AlertDialog(
            title=ft.Text("Weak Points Analysis", weight=ft.FontWeight.BOLD),
            content=ft.Text(content),
            actions=[ft.TextButton("Close", on_click=lambda e: self.page.close(dialog))],
        )
        self.page.open(dialog)

    def show_summary(self, e):
        msg_count = len(self.messages)
        user_msgs = sum(1 for m in self.messages if m.sender == "user")
        content = f"This session:\n• Total messages: {msg_count}\n• Your messages: {user_msgs}"

        dialog = ft.AlertDialog(
            title=ft.Text("Session Summary", weight=ft.FontWeight.BOLD),
            content=ft.Text(content),
            actions=[ft.TextButton("Close", on_click=lambda e: self.page.close(dialog))],
        )
        self.page.open(dialog)

    def show_vocabulary(self, e):
        content = "No saved words yet."

        if IMPORTS_OK and self.user_id:
            try:
                vocab = get_user_vocab(self.user_id)
                if vocab:
                    lines = [f"Your saved words ({len(vocab)}):\n"]
                    for word in list(vocab.keys())[:12]:
                        lines.append(f"• {word}")
                    if len(vocab) > 12:
                        lines.append(f"...and {len(vocab) - 12} more")
                    content = "\n".join(lines)
            except Exception:
                pass

        dialog = ft.AlertDialog(
            title=ft.Text("My Vocabulary", weight=ft.FontWeight.BOLD),
            content=ft.Text(content),
            actions=[ft.TextButton("Close", on_click=lambda e: self.page.close(dialog))],
        )
        self.page.open(dialog)


# ============================================
# 🚀 MAIN
# ============================================
def main(page: ft.Page):
    AITutorApp(page)

if __name__ == "__main__":
    ft.run(main)
