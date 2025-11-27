# app/services/user_profile.py

from app.services.db_supabase import get_current_profile

def get_user_level(default: str = "B1") -> str:
    """
    Returns user's CEFR level (A1–C2) from Supabase profiles.cefr_level.
    Falls back to `default` if not set / error.
    """
    try:
        profile = get_current_profile()
        if profile and profile.get("cefr_level"):
            return profile["cefr_level"]
    except Exception:
        pass
    return default
