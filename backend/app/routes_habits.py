from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_connection
from app.routes_auth import get_current_user, notify_bot_async

router = APIRouter(prefix="/habits", tags=["Habits"])

DIFF = {
    "easy":   {"xp": 10, "gold": 5,  "stat_boost": 1, "hp_loss": 5},
    "medium": {"xp": 20, "gold": 12, "stat_boost": 2, "hp_loss": 10},
    "hard":   {"xp": 40, "gold": 25, "stat_boost": 3, "hp_loss": 15},
}


class HabitCreate(BaseModel):
    user_id:     int = None
    title:       str
    description: str = ""
    frequency:   str = "daily"
    difficulty:  str = "easy"
    stat:        str = "str"
    xp_reward:   int = None


class HabitUpdate(BaseModel):
    title:       str = None
    description: str = None
    frequency:   str = None
    difficulty:  str = None
    stat:        str = None
    xp_reward:   int = None


@router.get("/user/{user_id}")
def get_habits_by_user(user_id: int):
    conn = get_connection()
    habits = conn.execute(
        "SELECT * FROM habits WHERE user_id = ?", (user_id,)
    ).fetchall()
    result = []
    for h in habits:
        habit = dict(h)
        habit["status"] = "виконано" if habit["is_done"] == 1 else "не виконано"
        failed = conn.execute("""
            SELECT id FROM habit_logs 
            WHERE habit_id = ? AND action = 'fail' AND DATE(done_at) = DATE('now')
        """, (habit["id"],)).fetchone()
        habit["failed_today"] = 1 if failed else 0
        result.append(habit)
    conn.close()
    return result


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
def create_habit(data: HabitCreate, current_user: dict = Depends(get_current_user)):
    uid = current_user["id"]
    d   = DIFF.get(data.difficulty, DIFF["easy"])
    xp  = data.xp_reward if data.xp_reward else d["xp"]
    gold = d["gold"]
    conn = get_connection()
    conn.execute("""
        INSERT INTO habits (user_id, title, description, frequency, difficulty, stat, xp_reward, gold_reward)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (uid, data.title, data.description, data.frequency, data.difficulty, data.stat, xp, gold))
    conn.commit()
    conn.close()
    return {"message": "Звичку створено успішно"}


@router.put("/{habit_id}")
def update_habit(habit_id: int, data: HabitUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    habit = conn.execute(
        "SELECT * FROM habits WHERE id = ? AND user_id = ?", (habit_id, current_user["id"])
    ).fetchone()
    if habit is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Звичку не знайдено")
    new_diff = data.difficulty or habit["difficulty"]
    d = DIFF.get(new_diff, DIFF["easy"])
    conn.execute("""
        UPDATE habits SET title = ?, description = ?, frequency = ?, difficulty = ?,
                          stat = ?, xp_reward = ?, gold_reward = ?
        WHERE id = ?
    """, (
        data.title       or habit["title"],
        data.description if data.description is not None else habit["description"],
        data.frequency   or habit["frequency"],
        new_diff,
        data.stat        or habit["stat"],
        data.xp_reward   or d["xp"],
        d["gold"],
        habit_id,
    ))
    conn.commit()
    conn.close()
    return {"message": "Звичку оновлено"}


@router.delete("/{habit_id}")
def delete_habit(habit_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    habit = conn.execute(
        "SELECT id FROM habits WHERE id = ? AND user_id = ?", (habit_id, current_user["id"])
    ).fetchone()
    if habit is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Звичку не знайдено")
    conn.execute("DELETE FROM habit_logs WHERE habit_id = ?", (habit_id,))
    conn.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
    conn.commit()
    conn.close()
    return {"message": "Звичку видалено"}


@router.post("/{habit_id}/complete")
def complete_habit(habit_id: int, current_user: dict = Depends(get_current_user)):
    import json
    conn = get_connection()
    # конвертація sqlite3.Row до dict одразу
    row = conn.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Звичку не знайдено")
    habit = dict(row)

    if habit["is_done"] == 1:
        conn.close()
        return {"message": "Звичку вже виконано сьогодні", "xp_gained": 0, "gold_gained": 0}

    # Блокування якщо гравець мертвий (перевірка через _death_registry)
    from app.routes_auth import _death_registry, DEATH_TIMEOUT_SEC
    from datetime import datetime
    if current_user["id"] in _death_registry:
        died_at = _death_registry[current_user["id"]]
        secs_left = DEATH_TIMEOUT_SEC - (datetime.utcnow() - died_at).total_seconds()
        if secs_left > 0:
            conn.close()
            raise HTTPException(403, f"Ти мертвий! Зачекай ще {int(secs_left)} секунд.")

    d    = DIFF.get(habit["difficulty"], DIFF["easy"])
    xp   = habit["xp_reward"]
    gold = habit["gold_reward"] if habit["gold_reward"] else d["gold"]

    new_streak = habit["streak"] + 1
    new_best   = max(habit["best_streak"] or 0, new_streak)

    conn.execute("""
        UPDATE habits SET is_done = 1, streak = ?, best_streak = ?, total_completed = total_completed + 1
        WHERE id = ?
    """, (new_streak, new_best, habit_id))

    user = dict(conn.execute("SELECT * FROM users WHERE id = ?", (habit["user_id"],)).fetchone())
    stats = json.loads(user.get("stats") or '{"str":1,"wis":1,"end":1,"cha":1}')
    stat_key = habit["stat"] if habit["stat"] in stats else "str"
    stats[stat_key] = stats.get(stat_key, 1) + d["stat_boost"]

    conn.execute("""
        UPDATE users
        SET xp = xp + ?, coins = coins + ?,
            hp = MIN(hp + 2, max_hp),
            streak = streak + 1,
            best_streak = MAX(best_streak, streak + 1),
            total_completed = total_completed + 1,
            stats = ?,
            last_active = datetime('now')
        WHERE id = ?
    """, (xp, gold, json.dumps(stats), habit["user_id"]))

    conn.execute("""
        INSERT INTO habit_logs (habit_id, user_id, action, xp_gained, gold_gained)
        VALUES (?, ?, 'complete', ?, ?)
    """, (habit_id, habit["user_id"], xp, gold))
    conn.commit()

    levelled_up = None
    u = conn.execute("SELECT level, xp FROM users WHERE id = ?", (habit["user_id"],)).fetchone()
    needed = 100 + (u["level"] - 1) * 50
    if u["xp"] >= needed:
        new_level = u["level"] + 1
        conn.execute("""
            UPDATE users SET level = ?, xp = xp - ?, max_hp = max_hp + 10 WHERE id = ?
        """, (new_level, needed, habit["user_id"]))
        levelled_up = new_level

    updated_user = conn.execute("SELECT * FROM users WHERE id = ?", (habit["user_id"],)).fetchone()
    conn.execute("""
        INSERT OR REPLACE INTO leaderboard
            (user_id, username, avatar, level, xp, streak, best_streak, total_completed, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """, (updated_user["id"], updated_user["username"], updated_user["avatar"],
          updated_user["level"], updated_user["xp"], updated_user["streak"],
          updated_user["best_streak"], updated_user["total_completed"]))
    conn.commit()
    conn.close()

    return {
        "message":     "Звичку виконано! +XP нараховано",
        "xp_gained":   xp,
        "gold_gained": gold,
        "habit_title": habit["title"],
        "new_streak":  new_streak,
        "levelled_up": levelled_up,
    }


@router.post("/{habit_id}/fail")
def fail_habit(habit_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM habits WHERE id = ? AND user_id = ?", (habit_id, current_user["id"])
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "Звичку не знайдено")
    habit = dict(row)

    # перевірка чи вже провалено сьогодні через habit_logs
    already_failed = conn.execute("""
        SELECT id FROM habit_logs
        WHERE habit_id = ? AND user_id = ? AND action = 'fail'
          AND DATE(done_at) = DATE('now')
    """, (habit_id, current_user["id"])).fetchone()

    if already_failed:
        conn.close()
        return {"message": "Звичку вже відмічено як провалену сьогодні", "hp_lost": 0}

    d = DIFF.get(habit["difficulty"], DIFF["easy"])
    conn.execute("UPDATE habits SET streak = 0 WHERE id = ?", (habit_id,))
    conn.execute("""
        UPDATE users SET hp = MAX(0, hp - ?), streak = 0 WHERE id = ?
    """, (d["hp_loss"], current_user["id"]))
    conn.execute("""
        INSERT INTO habit_logs (habit_id, user_id, action) VALUES (?, ?, 'fail')
    """, (habit_id, current_user["id"]))

    # Перевірка смерті
    new_hp = conn.execute("SELECT hp FROM users WHERE id = ?", (current_user["id"],)).fetchone()["hp"]
    conn.commit()
    conn.close()

    died = False
    if new_hp == 0:
        from app.routes_auth import _death_registry
        from datetime import datetime
        _death_registry[current_user["id"]] = datetime.utcnow()
        died = True
        notify_bot_async({
            "event": "death",
            "user_id": current_user["id"],
            "username": current_user.get("username"),
            "seconds_left": None,
        })

    return {"message": "💀 Стрік скинуто!", "hp_lost": d["hp_loss"], "died": died}


@router.get("/{habit_id}/history")
def habit_history(habit_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    habit = conn.execute(
        "SELECT id FROM habits WHERE id = ? AND user_id = ?", (habit_id, current_user["id"])
    ).fetchone()
    if not habit:
        conn.close()
        raise HTTPException(404, "Звичку не знайдено")
    logs = conn.execute("""
        SELECT action, xp_gained, gold_gained, done_at
        FROM habit_logs WHERE habit_id = ?
        ORDER BY done_at DESC LIMIT 90
    """, (habit_id,)).fetchall()
    conn.close()
    return [dict(l) for l in logs]