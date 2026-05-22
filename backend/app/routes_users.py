from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
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

class UserCreate(BaseModel):
    username: str
    email: str


class UserUpdate(BaseModel):
    username: str = None
    email: str = None


@router.post("/")
def create_user(data: UserCreate):
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ? OR email = ?",
        (data.username, data.email)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Користувач вже існує")
    conn.execute(
        "INSERT INTO users (username, email) VALUES (?, ?)",
        (data.username, data.email)
    )
    conn.commit()
    conn.close()
    return {"message": "Користувача створено успішно"}


@router.put("/{user_id}")
def update_user(user_id: int, data: UserUpdate):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Користувача не знайдено")
    new_username = data.username if data.username else user["username"]
    new_email = data.email if data.email else user["email"]
    conn.execute(
        "UPDATE users SET username = ?, email = ? WHERE id = ?",
        (new_username, new_email, user_id)
    )
    conn.commit()
    conn.close()
    return {"message": "Профіль оновлено"}


@router.delete("/{user_id}")
def delete_user(user_id: int):
    conn = get_connection()
    user = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Користувача не знайдено")
    habits = conn.execute("SELECT id FROM habits WHERE user_id = ?", (user_id,)).fetchall()
    for habit in habits:
        conn.execute("DELETE FROM habit_logs WHERE habit_id = ?", (habit["id"],))
    conn.execute("DELETE FROM habits WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"message": "Користувача видалено"}

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
