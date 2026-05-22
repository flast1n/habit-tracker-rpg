from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_connection

router = APIRouter(prefix="/habits", tags=["Habits"])


# Модель для створення нової звички
class HabitCreate(BaseModel):
    user_id: int
    title: str
    description: str = ""
    frequency: str = "daily"
    xp_reward: int = 10


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


@router.post("/")
def create_habit(data: HabitCreate):
    conn = get_connection()

    # Перевіряємо чи існує користувач
    user = conn.execute(
        "SELECT id FROM users WHERE id = ?", (data.user_id,)
    ).fetchone()

    if user is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Користувача не знайдено")

    conn.execute("""
        INSERT INTO habits (user_id, title, description, frequency, xp_reward)
        VALUES (?, ?, ?, ?, ?)
    """, (data.user_id, data.title, data.description, data.frequency, data.xp_reward))

    conn.commit()
    conn.close()

    return {"message": "Звичку створено успішно"}

class HabitUpdate(BaseModel):
    title: str = None
    description: str = None
    frequency: str = None
    xp_reward: int = None


@router.put("/{habit_id}")
def update_habit(habit_id: int, data: HabitUpdate):
    conn = get_connection()
    habit = conn.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
    if habit is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Звичку не знайдено")
    new_title       = data.title       if data.title       else habit["title"]
    new_description = data.description if data.description else habit["description"]
    new_frequency   = data.frequency   if data.frequency   else habit["frequency"]
    new_xp_reward   = data.xp_reward   if data.xp_reward   else habit["xp_reward"]
    conn.execute("""
        UPDATE habits SET title = ?, description = ?, frequency = ?, xp_reward = ?
        WHERE id = ?
    """, (new_title, new_description, new_frequency, new_xp_reward, habit_id))
    conn.commit()
    conn.close()
    return {"message": "Звичку оновлено"}


@router.delete("/{habit_id}")
def delete_habit(habit_id: int):
    conn = get_connection()

    habit = conn.execute(
        "SELECT id FROM habits WHERE id = ?", (habit_id,)
    ).fetchone()

    if habit is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Звичку не знайдено")

# Статуси звичок
@router.get("/user/{user_id}")
def get_habits_by_user(user_id: int):
    conn = get_connection()
    habits = conn.execute(
        "SELECT * FROM habits WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()

    result = []
    for h in habits:
        habit = dict(h)
        if habit["is_done"] == 1:
            habit["status"] = "виконано"
        else:
            habit["status"] = "не виконано"
        result.append(habit)

    return result

    # Видаляємо логи цієї звички і саму звичку
    conn.execute("DELETE FROM habit_logs WHERE habit_id = ?", (habit_id,))
    conn.execute("DELETE FROM habits WHERE id = ?", (habit_id,))

    conn.commit()
    conn.close()

    return {"message": "Звичку видалено"}


@router.post("/{habit_id}/complete")
def complete_habit(habit_id: int):
    conn = get_connection()

    habit = conn.execute(
        "SELECT * FROM habits WHERE id = ?", (habit_id,)
    ).fetchone()

    if habit is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Звичку не знайдено")

    # Якщо вже виконана сьогодні тоді не нараховуємо XP двічі
    if habit["is_done"] == 1:
        conn.close()
        return {"message": "Звичку вже виконано сьогодні", "xp_gained": 0}

    conn.execute("INSERT INTO habit_logs (habit_id) VALUES (?)", (habit_id,))
    conn.execute("UPDATE habits SET streak = streak + 1, is_done = 1 WHERE id = ?", (habit_id,))
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
