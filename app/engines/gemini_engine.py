# app/engines/gemini_engine.py
# HYBRID VERSION: Uses Groq if Gemini fails!

import os
import json
import requests
import time

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv())
except Exception:
    pass

from app.services.db_supabase import add_learning_event, get_recent_learning_events


class GeminiEngine:
    """
    Hybrid Gemini/Groq client with automatic fallback.

    Priority:
    1. Try Gemini (if available)
    2. Fall back to Groq (if Gemini fails)

    This solves your 429 problem permanently!
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
        # Try to initialize Gemini
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")

        if not self.gemini_key and not self.groq_key:
            raise ValueError(
                "❌ Either GEMINI_API_KEY or GROQ_API_KEY must be in .env\n"
                "   Get Groq key (FREE): https://console.groq.com"
            )

        # Gemini setup
        if self.gemini_key:
            model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
            self.gemini_endpoint = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={self.gemini_key}"
            )
            self.use_gemini = True
            print("✅ Gemini initialized (will try first)")
        else:
            self.use_gemini = False
            print("⚠️  No Gemini key found")

        # Groq setup
        if self.groq_key:
            self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            self.groq_endpoint = "https://api.groq.com/openai/v1/chat/completions"
            self.use_groq = True
            print("✅ Groq initialized (fallback)")
        else:
            self.use_groq = False
            print("⚠️  No Groq key found")

        # Rate limiting
        self.last_request_time = 0
        self.min_interval = 2.0
        self.gemini_failed_count = 0
        self.max_failures_before_switch = 2

    def ask(self, text: str, session_id: int | None = None) -> str:
        """
        Main entry point - tries Gemini first, falls back to Groq.
        """
        # Build context
        context = self._build_learning_context()
        prompt_text = context + "\n\nCurrent user message:\n" + text

        # Try Gemini first (if available and hasn't failed too much)
        if self.use_gemini and self.gemini_failed_count < self.max_failures_before_switch:
            reply = self._try_gemini(prompt_text)

            # Check if Gemini failed
            if "[Gemini error" in reply or "429" in reply:
                self.gemini_failed_count += 1
                print(f"⚠️  Gemini failed ({self.gemini_failed_count}/{self.max_failures_before_switch})")

                # Fall back to Groq
                if self.use_groq:
                    print("🔄 Falling back to Groq...")
                    reply = self._try_groq(prompt_text)
            else:
                # Success - reset failure count
                self.gemini_failed_count = 0

        # Use Groq if Gemini is unavailable or has failed too much
        elif self.use_groq:
            reply = self._try_groq(prompt_text)

        else:
            reply = "[ERROR: No AI service available. Please configure GEMINI_API_KEY or GROQ_API_KEY]"

        # Grammar analysis (only if not an error)
        grammar_info = {}
        if not reply.startswith("[") and not reply.startswith("ERROR"):
            grammar_info = self._analyse_grammar(text, reply)

        # Log learning event
        self._log_learning_event(
            user_input=text,
            reply_text=reply,
            session_id=session_id,
            extra=grammar_info,
        )

        return reply

    def _try_gemini(self, prompt: str) -> str:
        """Try to get response from Gemini."""
        body = {"contents": [{"parts": [{"text": prompt}]}]}

        try:
            # Rate limiting
            self._rate_limit()

            r = requests.post(self.gemini_endpoint, json=body, timeout=60)

            if r.status_code == 200:
                data = r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            elif r.status_code == 429:
                return f"[Gemini error 429: Quota exceeded. Falling back to Groq...]"
            else:
                return f"[Gemini error {r.status_code}]"

        except requests.Timeout:
            return "[Gemini error: timeout]"
        except Exception as e:
            return f"[Gemini error: {e}]"

    def _try_groq(self, prompt: str) -> str:
        """Try to get response from Groq."""
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }

        body = {
            "model": self.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful AI language tutor. Provide clear, encouraging responses."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 2048
        }

        try:
            # Rate limiting
            self._rate_limit()

            r = requests.post(self.groq_endpoint, json=body, headers=headers, timeout=30)

            if r.status_code == 200:
                data = r.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"[Groq error {r.status_code}: {r.text[:100]}]"

        except requests.Timeout:
            return "[Groq error: timeout]"
        except Exception as e:
            return f"[Groq error: {e}]"

    def _rate_limit(self):
        """Simple rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def _build_learning_context(self) -> str:
        """FR17: Use past learning points."""
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
            "When answering now:\n"
            "- Re-use similar vocabulary or grammar structures occasionally.\n"
            "- Briefly remind important rules if related.\n"
            "- Keep tone supportive and help build long-term memory."
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
        return list(dict.fromkeys(out))

    def _strip_code_fence(self, text: str) -> str:
        """Strip ```json fences if present."""
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
        """Grammar category detection."""
        prompt = (
            "You are an English teacher.\n"
            f"Analyse: \"{user_input}\"\n\n"
            "Return ONLY JSON with:\n"
            f'  "grammar_categories": array from {self.GRAMMAR_CATEGORIES}\n'
            '  "short_comment": max 80 chars\n\n'
            'Example: {"grammar_categories": ["verb_tense"], "short_comment": "Past tense needs review."}'
        )

        # Try with current engine (Gemini or Groq)
        if self.use_gemini and self.gemini_failed_count < self.max_failures_before_switch:
            response = self._try_gemini(prompt)
        elif self.use_groq:
            response = self._try_groq(prompt)
        else:
            return {}

        try:
            cleaned = self._strip_code_fence(response)
            obj = json.loads(cleaned)
            cats = self._normalise_categories(obj.get("grammar_categories"))
            comment = obj.get("short_comment")

            out: dict = {}
            if cats:
                out["grammar_categories"] = cats
            if isinstance(comment, str) and comment.strip():
                out["grammar_comment"] = comment.strip()[:120]
            return out
        except Exception:
            return {}

    def _log_learning_event(
            self,
            user_input: str,
            reply_text: str,
            session_id: int | None = None,
            extra: dict | None = None,
    ) -> None:
        """FR16: Save learning info."""
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
            pass