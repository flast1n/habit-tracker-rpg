"""
routes_admin.py — Новий файл: адмін-панель
Захищений через require_admin (роль = 'admin')
"""
import json
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from database import get_connection
from app.routes_auth import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/stats", summary="Глобальна статистика")
def admin_stats(admin=Depends(require_admin)):
    conn = get_connection()
    stats = {
        "total_users":   conn.execute("SELECT COUNT(*) FROM users WHERE role='player'").fetchone()[0],
        "banned":        conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0],
        "total_habits":  conn.execute("SELECT COUNT(*) FROM habits").fetchone()[0],
        "done_today":    conn.execute("SELECT COUNT(*) FROM habits WHERE is_done=1").fetchone()[0],
        "total_logs":    conn.execute("SELECT COUNT(*) FROM habit_logs").fetchone()[0],
        "active_today":  conn.execute(
            "SELECT COUNT(*) FROM users WHERE last_active >= date('now') AND is_banned=0"
        ).fetchone()[0],
        "total_gold":    conn.execute("SELECT COALESCE(SUM(coins),0) FROM users").fetchone()[0],
    }
    conn.close()
    return stats


@router.get("/users", summary="Список гравців")
def list_users(
    search: str = "", role: str = "all", status: str = "all",
    page: int = 1, page_size: int = 20,
    admin=Depends(require_admin),
):
    conn = get_connection()
    query, params = "SELECT * FROM users WHERE 1=1", []

    if search:
        query  += " AND (username LIKE ? OR email LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    if role != "all":
        query  += " AND role = ?"; params.append(role)
    if status == "active":
        query  += " AND is_banned = 0"
    elif status == "banned":
        query  += " AND is_banned = 1"

    total = conn.execute(query.replace("SELECT *", "SELECT COUNT(*)"), params).fetchone()[0]
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [page_size, (page - 1) * page_size]

    rows = conn.execute(query, params).fetchall()
    conn.close()

    users = []
    for r in rows:
        u = dict(r)
        u.pop("password", None)
        users.append(u)

    return {"total": total, "page": page, "users": users}


@router.get("/users/{user_id}", summary="Деталі гравця")
def get_user_detail(user_id: int, admin=Depends(require_admin)):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(404, "Користувача не знайдено")

    habits = conn.execute("SELECT * FROM habits WHERE user_id = ?", (user_id,)).fetchall()
    logs   = conn.execute("""
        SELECT hl.*, h.title as habit_title FROM habit_logs hl
        JOIN habits h ON h.id = hl.habit_id
        WHERE hl.user_id = ? ORDER BY hl.done_at DESC LIMIT 20
    """, (user_id,)).fetchall()

    u = dict(user); u.pop("password", None)
    conn.close()
    return {"user": u, "habits": [dict(h) for h in habits], "recent_logs": [dict(l) for l in logs]}


class AdminUserEdit(BaseModel):
    level:  Optional[int] = None
    xp:     Optional[int] = None
    coins:  Optional[int] = None
    hp:     Optional[int] = None
    role:   Optional[str] = None


class ReviveTimeUpdate(BaseModel):
    revive_timeout_sec: int


@router.get("/settings/revive-time", summary="Поточний час до відродження")
def get_revival_time(admin=Depends(require_admin)):
    from app.routes_auth import DEATH_TIMEOUT_SEC
    return {"revive_timeout_sec": DEATH_TIMEOUT_SEC}


@router.put("/settings/revive-time", summary="Оновити час до відродження")
def update_revival_time(data: ReviveTimeUpdate, admin=Depends(require_admin)):
    if data.revive_timeout_sec < 1 or data.revive_timeout_sec > 86400:
        raise HTTPException(400, "Час відродження має бути від 1 до 86400 секунд")
    import app.routes_auth as routes_auth
    routes_auth.DEATH_TIMEOUT_SEC = data.revive_timeout_sec
    return {"message": "Час відродження оновлено", "revive_timeout_sec": routes_auth.DEATH_TIMEOUT_SEC}


@router.put("/users/{user_id}", summary="Редагувати гравця")
def edit_user(user_id: int, data: AdminUserEdit, admin=Depends(require_admin)):
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(404, "Користувача не знайдено")

    conn.execute("""
        UPDATE users SET level = ?, xp = ?, coins = ?, hp = ?, role = ? WHERE id = ?
    """, (
        data.level if data.level is not None else user["level"],
        data.xp    if data.xp    is not None else user["xp"],
        data.coins if data.coins is not None else user["coins"],
        data.hp    if data.hp    is not None else user["hp"],
        data.role  if data.role  is not None else user["role"],
        user_id,
    ))
    conn.execute(
        "INSERT INTO action_logs (actor_id, target_id, action, details) VALUES (?, ?, 'edit_user', ?)",
        (admin["id"], user_id, json.dumps(data.dict(exclude_none=True)))
    )
    conn.commit()
    conn.close()
    return {"message": "Дані гравця оновлено"}

@router.post("/users/{user_id}/kill")
def kill_user(user_id: int, admin=Depends(require_admin)):
    from datetime import datetime
    from app.routes_auth import _death_registry, DEATH_TIMEOUT_SEC
    
    conn = get_connection()
    conn.execute("UPDATE users SET hp = 0 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    _death_registry[user_id] = datetime.utcnow()
    return {"message": f"Гравця {user_id} вбито для тесту"}

@router.post("/users/{user_id}/ban", summary="Заблокувати")
def ban_user(user_id: int, admin=Depends(require_admin)):
    conn = get_connection()
    user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close(); raise HTTPException(404, "Не знайдено")
    if user["role"] == "admin":
        conn.close(); raise HTTPException(400, "Не можна заблокувати адміна")
    conn.execute("UPDATE users SET is_banned = 1 WHERE id = ?", (user_id,))
    conn.execute("INSERT INTO action_logs (actor_id, target_id, action) VALUES (?, ?, 'ban')",
                 (admin["id"], user_id))
    conn.commit(); conn.close()
    return {"message": "Заблоковано"}


@router.post("/users/{user_id}/unban", summary="Розблокувати")
def unban_user(user_id: int, admin=Depends(require_admin)):
    conn = get_connection()
    conn.execute("UPDATE users SET is_banned = 0 WHERE id = ?", (user_id,))
    conn.execute("INSERT INTO action_logs (actor_id, target_id, action) VALUES (?, ?, 'unban')",
                 (admin["id"], user_id))
    conn.commit(); conn.close()
    return {"message": "Розблоковано"}


@router.delete("/users/{user_id}", summary="Видалити гравця")
def delete_user(user_id: int, admin=Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(400, "Не можна видалити себе")
    conn = get_connection()
    user = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close(); raise HTTPException(404, "Не знайдено")
    if user["role"] == "admin":
        conn.close(); raise HTTPException(400, "Не можна видалити адміна")

    for h in conn.execute("SELECT id FROM habits WHERE user_id = ?", (user_id,)).fetchall():
        conn.execute("DELETE FROM habit_logs WHERE habit_id = ?", (h["id"],))
    conn.execute("DELETE FROM habits WHERE user_id = ?",    (user_id,))
    conn.execute("DELETE FROM rewards WHERE user_id = ?",   (user_id,))
    conn.execute("DELETE FROM leaderboard WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?",          (user_id,))
    conn.execute("INSERT INTO action_logs (actor_id, target_id, action) VALUES (?, ?, 'delete_user')",
                 (admin["id"], user_id))
    conn.commit(); conn.close()
    return {"message": "Гравця видалено"}


@router.get("/logs", summary="Аудит-журнал")
def audit_logs(limit: int = 50, admin=Depends(require_admin)):
    conn = get_connection()
    logs = conn.execute("""
        SELECT al.*, u1.username as actor_name, u2.username as target_name
        FROM action_logs al
        LEFT JOIN users u1 ON u1.id = al.actor_id
        LEFT JOIN users u2 ON u2.id = al.target_id
        ORDER BY al.created_at DESC LIMIT ?
    """, (min(limit, 500),)).fetchall()
    conn.close()
    return [dict(l) for l in logs]
