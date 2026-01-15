# app/engines/gemini_engine.py
# MERGED VERSION: Your original + teammate's check_grammar + Groq fallback

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
    Hybrid Gemini/Groq engine with:
    1. ask() - Main tutor conversation with learning memory (YOUR ORIGINAL)
    2. check_grammar() - Grammar correction JSON (YOUR TEAMMATE'S NEW)
    3. Automatic fallback to Groq when Gemini fails
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
            self.endpoint = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={self.gemini_key}"
            )
            self.use_gemini = True
            print("✅ Gemini initialized")
        else:
            self.use_gemini = False
            print("⚠️  No Gemini key")

        # Groq setup
        if self.groq_key:
            self.groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            self.groq_endpoint = "https://api.groq.com/openai/v1/chat/completions"
            self.use_groq = True
            print("✅ Groq initialized (fallback)")
        else:
            self.use_groq = False
            print("⚠️  No Groq key")

        # Rate limiting & failure tracking
        self.last_request_time = 0
        self.min_interval = 2.0
        self.gemini_failed_count = 0
        self.max_failures_before_switch = 2

    # ========================================================================
    # 1. YOUR ORIGINAL: ask() - Main tutor conversation with learning memory
    # ========================================================================
    def ask(self, text: str, session_id: int | None = None) -> str:
        """
        Main tutor conversation entry point.
        - Builds learning context from past events (FR17)
        - Gets AI response (Gemini or Groq)
        - Analyzes grammar categories
        - Logs learning event (FR16)
        """
        # Build learning context
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

        # Use Groq if Gemini unavailable or failed
        elif self.use_groq:
            reply = self._try_groq(prompt_text)
        else:
            reply = "[ERROR: No AI service available]"

        # Grammar category analysis (only if not an error)
        grammar_info = {}
        if not reply.startswith("[") and not reply.startswith("ERROR"):
            grammar_info = self._analyse_grammar(text, reply)

        # Log learning event (FR16)
        self._log_learning_event(
            user_input=text,
            reply_text=reply,
            session_id=session_id,
            extra=grammar_info,
        )

        return reply

    # ========================================================================
    # 2. YOUR TEAMMATE'S NEW: check_grammar() - Grammar correction JSON
    # ========================================================================
    def check_grammar(self, text: str) -> dict:
        """
        Grammar correction engine (NEW from your teammate).

        Returns:
        {
          "original": "I goed to school yesterday.",
          "corrected": "I went to school yesterday.",
          "errors": [
            {
              "original": "goed",
              "suggestion": "went",
              "start": 2,
              "end": 6
            }
          ]
        }
        """
        prompt = f"""
You are a grammar correction engine for English learners.
Return ONLY JSON.

TASK:
- Analyze the user sentence.
- Correct grammar/spelling mistakes.
- Ignore capitalization and whitespace issues. Only REAL mistakes matter.
- Return a JSON with:
  "original": string (the original sentence),
  "corrected": string (the fully corrected sentence),
  "errors": a list of objects with:
      "original": wrong word/phrase,
      "suggestion": corrected form,
      "start": index in original text,
      "end": index in original text.

NO explanations. NO text outside JSON.
User sentence:
{text}
        """.strip()

        body = {"contents": [{"parts": [{"text": prompt}]}]}

        # Try Gemini first, then Groq
        try:
            if self.use_gemini and self.gemini_failed_count < self.max_failures_before_switch:
                r = requests.post(self.endpoint, json=body, timeout=60)
            elif self.use_groq:
                # Groq version
                headers = {
                    "Authorization": f"Bearer {self.groq_key}",
                    "Content-Type": "application/json"
                }
                groq_body = {
                    "model": self.groq_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                }
                r = requests.post(self.groq_endpoint, json=groq_body, headers=headers, timeout=30)
            else:
                return {
                    "original": text,
                    "corrected": text,
                    "errors": [],
                    "error": "No AI service available"
                }

            if r.status_code != 200:
                return {
                    "original": text,
                    "corrected": text,
                    "errors": [],
                    "error": f"Error {r.status_code}: {r.text[:180]}",
                }

            # Parse response
            data = r.json()
            if self.use_groq and "choices" in data:
                raw = data["choices"][0]["message"]["content"]
            else:
                raw = data["candidates"][0]["content"]["parts"][0]["text"]

            # Clean JSON fences
            raw = self._strip_code_fence(raw)

            result = json.loads(raw)

            # Validate structure
            if "errors" not in result or not isinstance(result["errors"], list):
                result["errors"] = []
            result.setdefault("original", text)
            result.setdefault("corrected", text)

            return result

        except Exception as e:
            return {
                "original": text,
                "corrected": text,
                "errors": [],
                "error": f"Parse error: {e}",
            }

    # ========================================================================
    # INTERNAL HELPERS (from your original code)
    # ========================================================================

    def _try_gemini(self, prompt: str) -> str:
        """Try Gemini API."""
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            self._rate_limit()
            r = requests.post(self.endpoint, json=body, timeout=60)
            if r.status_code == 200:
                data = r.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            elif r.status_code == 429:
                return "[Gemini error 429: Quota exceeded]"
            else:
                return f"[Gemini error {r.status_code}]"
        except requests.Timeout:
            return "[Gemini error: timeout]"
        except Exception as e:
            return f"[Gemini error: {e}]"

    def _try_groq(self, prompt: str) -> str:
        """Try Groq API."""
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json"
        }
        body = {
            "model": self.groq_model,
            "messages": [
                {"role": "system", "content": "You are a helpful AI language tutor."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2048
        }
        try:
            self._rate_limit()
            r = requests.post(self.groq_endpoint, json=body, headers=headers, timeout=30)
            if r.status_code == 200:
                data = r.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"[Groq error {r.status_code}]"
        except Exception as e:
            return f"[Groq error: {e}]"

    def _rate_limit(self):
        """Simple rate limiting."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()

    def _build_learning_context(self) -> str:
        """FR17: Build context from past learning events."""
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
                "Explain grammar and vocabulary clearly."
            )

        bullet_lines = "\n".join(f"- {s}" for s in sentences)
        return (
            "You are an AI language tutor.\n"
            "Previously, the user produced sentences like:\n"
            f"{bullet_lines}\n\n"
            "When answering:\n"
            "- Re-use similar vocabulary occasionally for retrieval practice.\n"
            "- Briefly remind important rules if related.\n"
            "- Keep tone supportive."
        )

    def _normalise_categories(self, cats) -> list[str]:
        """Normalize grammar categories."""
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
        """Strip ```json fences."""
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
        Grammar category detection (YOUR ORIGINAL).
        Returns grammar_categories and short_comment.
        """
        prompt = (
            "You are an English teacher.\n"
            f"Analyse: \"{user_input}\"\n\n"
            "Return ONLY JSON:\n"
            f'  "grammar_categories": array from {self.GRAMMAR_CATEGORIES}\n'
            '  "short_comment": max 80 chars\n\n'
            'Example: {"grammar_categories": ["verb_tense"], "short_comment": "Past tense needs review."}'
        )

        # Use current engine
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
        """FR16: Log learning event to Supabase."""
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
            pass  # Don't crash if logging fails