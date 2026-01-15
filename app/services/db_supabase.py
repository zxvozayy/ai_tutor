# app/services/db_supabase.py

import os, json, pathlib
from typing import Optional, Dict, Any, List

from supabase import create_client, Client
from dotenv import load_dotenv, find_dotenv

# Load .env from project or CWD
load_dotenv(find_dotenv(usecwd=True) or find_dotenv())

# -------------------- Supabase Init --------------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("Missing SUPABASE_URL / SUPABASE_ANON_KEY in .env")

sb: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def get_client() -> Client:
    """Small helper so other modules can reuse the Supabase client."""
    return sb


# -------------------- Session Persistence --------------------
SESSION_FILE = pathlib.Path.home() / ".ai_tutor_supabase_session.json"


def save_session(access_token: str, refresh_token: str):
    SESSION_FILE.write_text(json.dumps({
        "access_token": access_token,
        "refresh_token": refresh_token
    }, indent=2))
    sb.postgrest.auth(access_token)


def load_session_if_any() -> bool:
    if not SESSION_FILE.exists():
        return False
    try:
        data = json.loads(SESSION_FILE.read_text())
        access = data.get("access_token")
        refresh = data.get("refresh_token")
        if not access or not refresh:
            return False

        sb.postgrest.auth(access)
        sb.auth.set_session(access, refresh)
        sess = sb.auth.get_session()
        if not sess or not sess.user:
            return False

        sb.postgrest.auth(sess.access_token)
        return True
    except Exception:
        return False


# -------------------- Auth --------------------
def sign_up(email: str, password: str) -> Dict[str, Any]:
    res = sb.auth.sign_up({"email": email, "password": password})
    if res.user is None:
        raise RuntimeError("Sign-up failed")
    return {"user_id": res.user.id, "email": res.user.email}


def sign_in(email: str, password: str) -> Dict[str, Any]:
    res = sb.auth.sign_in_with_password({"email": email, "password": password})
    if not res.session or not res.user:
        raise RuntimeError("Login failed")
    save_session(res.session.access_token, res.session.refresh_token)
    return {"user_id": res.user.id, "email": res.user.email}


def sign_out():
    try:
        sb.auth.sign_out()
    except Exception:
        pass
    try:
        if SESSION_FILE.exists():
            SESSION_FILE.unlink()
    except Exception:
        pass


def current_user_id() -> Optional[str]:
    sess = sb.auth.get_session()
    return getattr(getattr(sess, "user", None), "id", None)


def current_user_email() -> Optional[str]:
    """Return the logged-in user's email from Supabase auth (not from profiles)."""
    sess = sb.auth.get_session()
    if not sess or not getattr(sess, "user", None):
        return None
    return getattr(sess.user, "email", None)


# -------------------- Chat Sessions --------------------
def get_or_create_default_session() -> int:
    uid = current_user_id()
    if not uid:
        raise RuntimeError("Not authenticated")

    res = (
        sb.table("chat_sessions")
        .select("id")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]["id"]

    ins = sb.table("chat_sessions").insert({
        "user_id": uid,
        "title": "My Chat"
    }).execute()
    return ins.data[0]["id"]


def add_message(session_id: int, role: str, content: str, meta: dict | None = None) -> int:
    uid = current_user_id()
    if not uid:
        raise RuntimeError("Not authenticated")
    ins = sb.table("chat_messages").insert({
        "session_id": session_id,
        "user_id": uid,
        "role": role,
        "content": content,
        "meta": meta or {}
    }).execute()
    return ins.data[0]["id"]


def list_messages(session_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    res = (
        sb.table("chat_messages")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(reversed(res.data))  # oldest → newest


def list_user_sessions(limit: int = 50) -> List[Dict[str, Any]]:
    uid = current_user_id()
    if not uid:
        raise RuntimeError("Not authenticated")

    res = (
        sb.table("chat_sessions")
        .select("id,title,created_at")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def create_session(title: str = "New Chat") -> Dict[str, Any]:
    uid = current_user_id()
    if not uid:
        raise RuntimeError("Not authenticated")
    ins = sb.table("chat_sessions").insert({
        "user_id": uid,
        "title": title
    }).execute()
    return ins.data[0]


def rename_session(session_id: int, new_title: str) -> None:
    uid = current_user_id()
    if not uid:
        raise RuntimeError("Not authenticated")
    sb.table("chat_sessions") \
        .update({"title": new_title}) \
        .eq("id", session_id) \
        .eq("user_id", uid) \
        .execute()


def delete_session(session_id: int) -> None:
    uid = current_user_id()
    if not uid:
        raise RuntimeError("Not authenticated")
    sb.table("chat_sessions") \
        .delete() \
        .eq("id", session_id) \
        .eq("user_id", uid) \
        .execute()


# -------------------- User Profile (Placement Test) --------------------
def get_current_profile() -> Optional[Dict[str, Any]]:
    uid = current_user_id()
    if not uid:
        return None
    res = sb.table("profiles").select("*").eq("id", uid).limit(1).execute()
    return res.data[0] if res.data else None


def upsert_cefr_level(level: str) -> Dict[str, Any]:
    uid = current_user_id()
    if not uid:
        raise RuntimeError("Not authenticated")

    if level not in ("A1", "A2", "B1", "B2", "C1", "C2"):
        raise ValueError(f"Invalid CEFR level: {level}")

    row = {"id": uid, "cefr_level": level}
    res = sb.table("profiles").upsert(row, on_conflict="id").execute()
    return res.data[0] if res.data else row


def save_placement_result(
        estimated_level: str,
        total_correct: int,
        total_questions: int,
        per_level: Dict[str, Dict[str, int]],
        answers: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    uid = current_user_id()
    if not uid:
        raise RuntimeError("Not authenticated")

    row = {
        "user_id": uid,
        "estimated_level": estimated_level,
        "total_correct": total_correct,
        "total_questions": total_questions,
        "per_level": per_level,
        "answers": answers or {},
    }

    res = sb.table("placement_tests").insert(row).execute()
    saved = res.data[0]

    upsert_cefr_level(estimated_level)
    return saved


def get_last_placement_result() -> Optional[Dict[str, Any]]:
    uid = current_user_id()
    if not uid:
        return None

    res = (
        sb.table("placement_tests")
        .select("*")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


# -------------------- Learning Memory (FR16 & FR17) --------------------
def add_learning_event(
        kind: str,
        payload: Dict[str, Any],
        session_id: Optional[int] = None,
) -> Optional[int]:
    uid = current_user_id()
    if not uid:
        return None

    row = {
        "user_id": uid,
        "kind": kind,
        "payload": payload,
    }
    if session_id is not None:
        row["session_id"] = session_id

    try:
        res = sb.table("learning_events").insert(row).execute()
        return res.data[0]["id"] if res.data else None
    except Exception:
        return None


def get_recent_learning_events(limit: int = 5) -> List[Dict[str, Any]]:
    uid = current_user_id()
    if not uid:
        return []
    try:
        res = (
            sb.table("learning_events")
            .select("kind,payload,created_at,session_id")
            .eq("user_id", uid)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


# -------------------- ADMIN – UC17 / UC18 helpers --------------------

def get_flagged_learning_events(limit: int = 50) -> List[Dict[str, Any]]:
    """
    UC17 – Admin Oversight
    Fetch learning_events that are 'flagged' or 'reported'.
    You can implement the exact condition based on your table design.
    Example assumption:
      - table 'learning_events' has column 'kind' and we flag with kind IN ('flagged_feedback','user_report')
    """
    try:
        res = (
            sb.table("learning_events")
            .select("*")
            .in_("kind", ["flagged_feedback", "user_report"])
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def resolve_flagged_event(event_id: Any, action: str) -> bool:
    """
    Mark a flagged event as 'approved' or 'removed'.
    Requires that 'status' column exists in learning_events (e.g. 'pending', 'approved', 'removed').
    """
    if action not in ("approved", "removed"):
        return False

    try:
        (
            sb.table("learning_events")
            .update({"status": action})
            .eq("id", event_id)
            .execute()
        )
        return True
    except Exception:
        return False


# -------------------- Learning content management (UC18) --------------------

def list_lessons() -> List[Dict[str, Any]]:
    """
    Return all lessons for Tutor Mode / placement content.
    Expect a Supabase table 'lessons' with columns:
      id (uuid), title (text), level (text), content (text), updated_at (timestamp)
    """
    try:
        res = (
            sb.table("lessons")
            .select("*")
            .order("updated_at", desc=True)
            .execute()
        )
        return res.data or []
    except Exception:
        return []


def upsert_lesson(lesson: Dict[str, Any]) -> bool:
    """
    Insert or update a lesson.
    lesson should contain at least: { "id"?, "title", "level", "content" }
    """
    try:
        (
            sb.table("lessons")
            .upsert(lesson)
            .execute()
        )
        return True
    except Exception:
        return False


def delete_lesson(lesson_id: Any) -> bool:
    try:
        (
            sb.table("lessons")
            .delete()
            .eq("id", lesson_id)
            .execute()
        )
        return True
    except Exception:
        return False