from fastapi import APIRouter, HTTPException
from database import get_connection

router = APIRouter(prefix="/habits", tags=["Habits"])


@router.get("/user/{user_id}")
def get_habits_by_user(user_id: int):
    conn = get_connection()
    habits = conn.execute(
        "SELECT * FROM habits WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(h) for h in habits]


@router.get("/{habit_id}")
def get_habit(habit_id: int):
    conn = get_connection()
    habit = conn.execute(
        "SELECT * FROM habits WHERE id = ?", (habit_id,)
    ).fetchone()
    conn.close()

    if habit is None:
        raise HTTPException(status_code=404, detail="Звичку не знайдено")

    return dict(habit)


@router.post("/{habit_id}/complete")
def complete_habit(habit_id: int):
    conn = get_connection()

    habit = conn.execute(
        "SELECT * FROM habits WHERE id = ?", (habit_id,)
    ).fetchone()

    if habit is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Звичку не знайдено")

    # Запис виконання у лог
    conn.execute(
        "INSERT INTO habit_logs (habit_id) VALUES (?)", (habit_id,)
    )

    # Збільшення страйку та додавання XP користувачу
    conn.execute(
        "UPDATE habits SET streak = streak + 1 WHERE id = ?", (habit_id,)
    )
    conn.execute(
        "UPDATE users SET xp = xp + ? WHERE id = ?",
        (habit["xp_reward"], habit["user_id"])
    )

    conn.commit()
    conn.close()

    return {
        "message":    "Звичку виконано! +XP нараховано",
        "xp_gained":  habit["xp_reward"],
        "habit_title": habit["title"],
    }
