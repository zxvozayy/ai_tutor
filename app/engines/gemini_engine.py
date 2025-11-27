# app/engines/gemini_engine.py

import os
import json
import requests

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())  # load .env if present
except Exception:
    pass

from app.services.db_supabase import add_learning_event, get_recent_learning_events


class GeminiEngine:
    """
    Gemini client (free AI Studio key) with learning memory + grammar detection.

    - Uses GEMINI_API_KEY + optional GEMINI_MODEL from .env
    - ask(text, session_id=None):
        * Adds small "learning context" from past events.
        * Calls Gemini for the main tutor reply.
        * Calls Gemini again for a tiny JSON grammar analysis.
        * Logs everything into learning_events (FR16 & FR17).
    """

    GRAMMAR_CATEGORIES = [
        "verb_tense",
        "subject_verb_agreement",
        "articles",
        "prepositions",
        "word_order",
        "plural_singular",
        "pronouns",
        "vocabulary_choice",
        "spelling",
        "punctuation",
        "other",
    ]

    def __init__(self):
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("❌ GEMINI_API_KEY missing in .env")

        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        # v1beta endpoint for free AI Studio / MakerSuite keys
        self.endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={key}"
        )

    # ----------------- public API -----------------

    def ask(self, text: str, session_id: int | None = None) -> str:
        """
        Main entry point.

        - text: user message
        - session_id: optional chat_session id for logging (can be None)

        You can safely call:
            engine.ask("Hello")              # works
            engine.ask("Hello", session_id)  # also works
        """

        # 1) Build short learning context from recent events (FR17)
        context = self._build_learning_context()
        prompt_text = context + "\n\nCurrent user message:\n" + text

        body = {"contents": [{"parts": [{"text": prompt_text}]}]}

        # 2) Get main tutor reply from Gemini
        try:
            r = requests.post(self.endpoint, json=body, timeout=60)
            if r.status_code != 200:
                reply = f"[Gemini error {r.status_code}: {r.text[:180]}]"
            else:
                data = r.json()
                reply = data["candidates"][0]["content"]["parts"][0]["text"]
        except requests.Timeout:
            reply = "[Gemini error: request timed out]"
        except Exception as e:
            reply = f"[Gemini error: {e}]"

        # 3) Grammar category detection (Stage 2)
        grammar_info = self._analyse_grammar(text, reply)

        # 4) Log as a learning event (FR16)
        self._log_learning_event(
            user_input=text,
            reply_text=reply,
            session_id=session_id,
            extra=grammar_info,
        )

        return reply

    # ----------------- internal helpers -----------------

    def _build_learning_context(self) -> str:
        """
        FR17: Use past learning points in new conversations.
        Simple version: remind Gemini of a few recent learner sentences.
        """
        events = get_recent_learning_events(limit=5)
        if not events:
            return (
                "You are an AI language tutor. "
                "Explain grammar and vocabulary clearly, give examples, "
                "and keep a friendly, encouraging tone."
            )

        sentences: list[str] = []
        for e in events:
            payload = e.get("payload") or {}
            last_input = payload.get("last_input")
            if last_input and last_input not in sentences:
                sentences.append(last_input)

        if not sentences:
            return (
                "You are an AI language tutor. "
                "Explain grammar and vocabulary clearly, give examples, "
                "and gently review previous topics the user struggled with."
            )

        bullet_lines = "\n".join(f"- {s}" for s in sentences)

        context = (
            "You are an AI language tutor having an ongoing relationship with the learner.\n"
            "Previously, the user produced sentences like:\n"
            f"{bullet_lines}\n\n"
            "When answering now, do the following:\n"
            "- Re-use similar vocabulary or grammar structures occasionally to create retrieval practice.\n"
            "- Briefly remind important rules if the current message is related.\n"
            "- Keep the tone supportive and help the learner build long-term memory."
        )
        return context

    def _normalise_categories(self, cats) -> list[str]:
        if not cats:
            return []
        if isinstance(cats, str):
            cats = [cats]
        out: list[str] = []
        for c in cats:
            if not isinstance(c, str):
                continue
            c = c.strip().lower().replace(" ", "_")
            if c in self.GRAMMAR_CATEGORIES:
                out.append(c)
        # keep unique order
        return list(dict.fromkeys(out))

    def _strip_code_fence(self, text: str) -> str:
        """If Gemini returns ```json ... ```, strip the fences."""
        s = text.strip()
        if not s.startswith("```"):
            return s
        lines = s.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _analyse_grammar(self, user_input: str, reply_text: str) -> dict:
        """
        Stage 2: Grammar Category Detection.

        Asks Gemini for a tiny JSON with:
          - grammar_categories: subset of GRAMMAR_CATEGORIES
          - short_comment: brief English comment
        """
        prompt = (
            "You are an English teacher.\n"
            "Analyse the learner sentence below and decide which grammar/vocabulary areas "
            "are most relevant.\n\n"
            f'Learner sentence: "{user_input}"\n\n'
            "Return ONLY a JSON object with two keys:\n"
            '  "grammar_categories": an array of 1-3 items chosen ONLY from this list:\n'
            f"{self.GRAMMAR_CATEGORIES}\n"
            '  "short_comment": a very short English comment (max 80 characters) about the main issue.\n\n'
            "Example JSON:\n"
            '{\"grammar_categories\": [\"verb_tense\", \"prepositions\"], '
            '\"short_comment\": \"Past tense and preposition choice need review.\"}'
        )

        body = {"contents": [{"parts": [{"text": prompt}]}]}

        try:
            r = requests.post(self.endpoint, json=body, timeout=30)
            if r.status_code != 200:
                return {}
            data = r.json()
            txt = data["candidates"][0]["content"]["parts"][0]["text"]
            cleaned = self._strip_code_fence(txt)
            obj = json.loads(cleaned)
        except Exception:
            return {}

        cats = self._normalise_categories(obj.get("grammar_categories"))
        comment = obj.get("short_comment")

        out: dict = {}
        if cats:
            out["grammar_categories"] = cats
        if isinstance(comment, str) and comment.strip():
            out["grammar_comment"] = comment.strip()[:120]
        return out

    def _log_learning_event(
            self,
            user_input: str,
            reply_text: str,
            session_id: int | None = None,
            extra: dict | None = None,
    ) -> None:
        """
        FR16: Save key learning info from this interaction.
        extra may include grammar_categories, grammar_comment, etc.
        """
        payload: dict = {
            "last_input": user_input[:200],
            "last_reply": reply_text[:400],
        }
        if session_id is not None:
            payload["session_id"] = session_id
        if extra:
            payload.update(extra)

        try:
            add_learning_event(
                kind="tutor_interaction",
                payload=payload,
                session_id=session_id,
            )
        except Exception:
            # If table/rls/network fails, don't crash the app.
            pass
