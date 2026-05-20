from fastapi import APIRouter, HTTPException
from database import get_connection

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/")
def get_all_users():
    conn = get_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return [dict(u) for u in users]


@router.get("/{user_id}")
def get_user(user_id: int):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()

    if user is None:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")

    return dict(user)


@router.get("/{user_id}/stats")
def get_user_stats(user_id: int):
    conn = get_connection()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()

    if user is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Користувача не знайдено")

    total_habits = conn.execute(
        "SELECT COUNT(*) FROM habits WHERE user_id = ?", (user_id,)
    ).fetchone()[0]

    conn.close()

    xp_needed_for_next_level = user["level"] * 100

    return {
        "username":              user["username"],
        "level":                 user["level"],
        "xp":                    user["xp"],
        "xp_needed_for_next_level": xp_needed_for_next_level,
        "coins":                 user["coins"],
        "total_habits":          total_habits,
    }
