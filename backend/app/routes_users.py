from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import json
from database import get_connection
from app.routes_auth import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])


class UserCreate(BaseModel):
    username: str
    email: str

class UserUpdate(BaseModel):
    username: str = None
    email: str = None

class RewardCreate(BaseModel):
    title: str
    cost:  int


AVATARS_CATALOG = [
    {"emoji": "🧙‍♂️", "name": "Маг",          "cost": 0,    "rarity": "common"},
    {"emoji": "🧙‍♀️", "name": "Чаклунка",     "cost": 100,  "rarity": "common"},
    {"emoji": "🦸‍♂️", "name": "Супергерой",   "cost": 150,  "rarity": "uncommon"},
    {"emoji": "🦸‍♀️", "name": "Супергероїня", "cost": 150,  "rarity": "uncommon"},
    {"emoji": "🧝‍♂️", "name": "Ельф",         "cost": 250,  "rarity": "uncommon"},
    {"emoji": "🧝‍♀️", "name": "Ельфійка",     "cost": 250,  "rarity": "uncommon"},
    {"emoji": "🧛‍♂️", "name": "Вампір",       "cost": 400,  "rarity": "rare"},
    {"emoji": "🤴",   "name": "Принц",        "cost": 500,  "rarity": "rare"},
    {"emoji": "👸",   "name": "Принцеса",     "cost": 500,  "rarity": "rare"},
    {"emoji": "🥷",   "name": "Ніндзя",       "cost": 750,  "rarity": "epic"},
    {"emoji": "🤖",   "name": "Робот",        "cost": 900,  "rarity": "epic"},
    {"emoji": "👑",   "name": "Монарх",       "cost": 1200, "rarity": "legendary"},
    {"emoji": "🐉",   "name": "Дракон",       "cost": 2000, "rarity": "legendary"},
]


# ── ВАЖЛИВО: статичні роути ПЕРЕД /{user_id} ─────────────────────────────────

@router.get("/")
def get_all_users():
    conn = get_connection()
    users = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    result = []
    for u in users:
        user = dict(u)
        user.pop("password", None)   # ніколи не повертаємо пароль
        result.append(user)
    return result


@router.get("/leaderboard")
def leaderboard(sort_by: str = "xp", limit: int = 20):
    valid = ("xp", "level", "streak", "best_streak", "total_completed")
    if sort_by not in valid:
        sort_by = "xp"
    conn = get_connection()
    rows = conn.execute(f"""
        SELECT username, avatar, level, xp, streak, best_streak, total_completed
        FROM leaderboard ORDER BY {sort_by} DESC LIMIT ?
    """, (min(limit, 100),)).fetchall()
    conn.close()
    return [{"rank": i + 1, **dict(r)} for i, r in enumerate(rows)]


@router.get("/me/history")
def my_history(current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    logs = conn.execute("""
        SELECT hl.action, hl.xp_gained, hl.gold_gained, hl.done_at, h.title as habit_title
        FROM habit_logs hl
        JOIN habits h ON h.id = hl.habit_id
        WHERE hl.user_id = ?
        ORDER BY hl.done_at DESC LIMIT 100
    """, (current_user["id"],)).fetchall()
    conn.close()
    return [dict(l) for l in logs]


@router.get("/me/rewards")
def get_rewards(current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    rewards = conn.execute(
        "SELECT * FROM rewards WHERE user_id = ? ORDER BY created_at", (current_user["id"],)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rewards]


@router.post("/me/rewards")
def add_reward(data: RewardCreate, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    conn.execute("INSERT INTO rewards (user_id, title, cost) VALUES (?, ?, ?)",
                 (current_user["id"], data.title, data.cost))
    conn.commit()
    conn.close()
    return {"message": "Нагороду додано"}

@router.get("/me/activity-log")
def get_activity_log(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Завантажує журнал подій для поточного користувача"""
    conn = get_connection()
    logs = conn.execute("""
        SELECT message, created_at FROM activity_logs 
        WHERE user_id = ?
        ORDER BY created_at DESC LIMIT ?
    """, (current_user["id"], limit)).fetchall()
    conn.close()
    return [dict(l) for l in logs]


@router.post("/me/activity-log")
def add_activity_log(body: dict, current_user: dict = Depends(get_current_user)):
    """Додає запис в журнал подій"""
    message = body.get("message", "")
    if not message:
        raise HTTPException(400, "Повідомлення не може бути пустим")
    conn = get_connection()
    conn.execute(
        "INSERT INTO activity_logs (user_id, message) VALUES (?, ?)",
        (current_user["id"], message)
    )
    conn.commit()
    conn.close()
    return {"message": "Запис додано"}

@router.delete("/me/activity-log")
def clear_activity_log(current_user: dict = Depends(get_current_user)):
    """Очищає журнал подій користувача"""
    conn = get_connection()
    conn.execute("DELETE FROM activity_logs WHERE user_id = ?", (current_user["id"],))
    conn.commit()
    conn.close()
    return {"message": "Журнал очищено"}


@router.delete("/me/rewards/{reward_id}")
def delete_reward(reward_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    r = conn.execute("SELECT id FROM rewards WHERE id = ? AND user_id = ?",
                     (reward_id, current_user["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Нагороду не знайдено")
    conn.execute("DELETE FROM rewards WHERE id = ?", (reward_id,))
    conn.commit()
    conn.close()
    return {"message": "Нагороду видалено"}


@router.post("/me/rewards/{reward_id}/buy")
def buy_reward(reward_id: int, current_user: dict = Depends(get_current_user)):
    conn = get_connection()
    r = conn.execute("SELECT * FROM rewards WHERE id = ? AND user_id = ?",
                     (reward_id, current_user["id"])).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "Нагороду не знайдено")
    user = conn.execute("SELECT coins FROM users WHERE id = ?", (current_user["id"],)).fetchone()
    if user["coins"] < r["cost"]:
        conn.close()
        raise HTTPException(400, f"Не вистачає монет (потрібно {r['cost']})")
    conn.execute("UPDATE users SET coins = coins - ? WHERE id = ?", (r["cost"], current_user["id"]))
    conn.execute("INSERT INTO reward_logs (reward_id, user_id) VALUES (?, ?)",
                 (reward_id, current_user["id"]))
    conn.commit()
    conn.close()
    return {"message": f"🎁 '{r['title']}' отримано!", "cost": r["cost"]}


@router.get("/avatars/catalog")
def avatars_catalog(current_user: dict = Depends(get_current_user)):
    import json
    owned = json.loads(current_user.get("owned_avatars") or '["🧙‍♂️"]')
    return [{**av, "owned": av["emoji"] in owned, "equipped": av["emoji"] == current_user["avatar"]}
            for av in AVATARS_CATALOG]


@router.post("/avatars/buy")
def buy_avatar(body: dict, current_user: dict = Depends(get_current_user)):
    import json
    emoji = body.get("emoji")
    av = next((a for a in AVATARS_CATALOG if a["emoji"] == emoji), None)
    if not av:
        raise HTTPException(400, "Аватар не знайдено")
    owned = json.loads(current_user.get("owned_avatars") or '["🧙‍♂️"]')
    if emoji in owned:
        raise HTTPException(400, "Аватар вже є у тебе")
    conn = get_connection()
    user = conn.execute("SELECT coins FROM users WHERE id = ?", (current_user["id"],)).fetchone()
    if user["coins"] < av["cost"]:
        conn.close()
        raise HTTPException(400, f"Не вистачає монет (потрібно {av['cost']})")
    owned.append(emoji)
    conn.execute("UPDATE users SET coins = coins - ?, owned_avatars = ? WHERE id = ?",
                 (av["cost"], json.dumps(owned), current_user["id"]))
    conn.commit()
    conn.close()
    return {"message": f"Аватар {emoji} куплено!", "cost": av["cost"]}


@router.post("/avatars/equip")
def equip_avatar(body: dict, current_user: dict = Depends(get_current_user)):
    import json
    emoji = body.get("emoji")
    owned = json.loads(current_user.get("owned_avatars") or '["🧙‍♂️"]')
    if emoji not in owned:
        raise HTTPException(400, "Цей аватар не в твоїй колекції")
    conn = get_connection()
    conn.execute("UPDATE users SET avatar = ? WHERE id = ?", (emoji, current_user["id"]))
    conn.execute("UPDATE leaderboard SET avatar = ? WHERE user_id = ?", (emoji, current_user["id"]))
    conn.commit()
    conn.close()
    return {"message": f"Аватар {emoji} встановлено"}


# ── Роути з path параметром /{user_id} — завжди ОСТАННІ ──────────────────────

@router.get("/{user_id}/stats")
def get_user_stats(user_id: int):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Користувача не знайдено")
    total_habits = conn.execute(
        "SELECT COUNT(*) FROM habits WHERE user_id = ?", (user_id,)
    ).fetchone()[0]
    conn.close()
    return {
        "username":                 user["username"],
        "level":                    user["level"],
        "xp":                       user["xp"],
        "xp_needed_for_next_level": user["level"] * 100,
        "coins":                    user["coins"],
        "total_habits":             total_habits,
    }


@router.get("/{user_id}")
def get_user(user_id: int):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user is None:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")
    u = dict(user)
    u.pop("password", None)
    return u


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
    new_email    = data.email    if data.email    else user["email"]
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
    conn.execute("DELETE FROM habits WHERE user_id = ?",   (user_id,))
    conn.execute("DELETE FROM rewards WHERE user_id = ?",  (user_id,))
    conn.execute("DELETE FROM leaderboard WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?",         (user_id,))
    conn.commit()
    conn.close()
    return {"message": "Користувача видалено"}

class AchievementUpdate(BaseModel):
    achievements: list[str]

@router.put("/me/achievements")
def update_my_achievements(
    data: AchievementUpdate,
    current_user = Depends(get_current_user)
):
    from database import get_connection
    
    # Витягання ID користувача (залежить від того, як він у тебе зберігається)
    user_id = current_user["id"] if isinstance(current_user, dict) else current_user.id

    
    # Перетворюємо масив досягнень на текст (JSON) для бази даних
    achievements_json = json.dumps(data.achievements)
    
    # Записуємо в базу
    conn = get_connection()
    conn.execute("UPDATE users SET achievements = ? WHERE id = ?", (achievements_json, user_id))
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": "Досягнення збережено"}