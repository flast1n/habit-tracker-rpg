from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from database import get_connection
import threading

# JWT + bcrypt
try:
    import bcrypt
    from jose import JWTError, jwt
    from datetime import datetime, timedelta

    SECRET_KEY = "CHANGE_IN_PRODUCTION_habitrpg_2024"
    ALGORITHM  = "HS256"
    ACCESS_EXPIRE_MIN  = 60 * 24
    REFRESH_EXPIRE_MIN = 60 * 24 * 7

    def hash_password(plain: str) -> str:
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(plain: str, hashed: str) -> bool:
        if not hashed.startswith("$2"):
            return plain == hashed
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
        except Exception:
            return False

    def make_tokens(user_id: int) -> dict:
        def _tok(data, minutes):
            d = data.copy()
            d["exp"] = datetime.utcnow() + timedelta(minutes=minutes)
            token = jwt.encode(d, SECRET_KEY, algorithm=ALGORITHM)
            return token if isinstance(token, str) else token.decode("utf-8")
        return {
            "access_token":  _tok({"sub": str(user_id), "type": "access"},  ACCESS_EXPIRE_MIN),
            "refresh_token": _tok({"sub": str(user_id), "type": "refresh"}, REFRESH_EXPIRE_MIN),
            "token_type":    "bearer",
        }

    JWT_AVAILABLE = True

except ImportError:
    JWT_AVAILABLE = False
    def hash_password(plain): return plain
    def verify_password(plain, hashed): return plain == hashed
    def make_tokens(user_id): return {}

# ─ протокол OAuth2 
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

def get_current_user(token: str = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status_code=401, detail="Потрібна авторизація")
    if not JWT_AVAILABLE:
        raise HTTPException(status_code=501, detail="JWT не налаштовано")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(401, "Потрібен access token")
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(401, "Недійсний або прострочений токен")

    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not user:
        raise HTTPException(401, "Користувача не знайдено")
    if user["is_banned"]:
        raise HTTPException(403, "Акаунт заблоковано")
    return dict(user)

def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Потрібні права адміністратора")
    return current_user

router = APIRouter(prefix="/auth", tags=["Auth"])


class RegisterData(BaseModel):
    username: str
    password: str
    email: str = ""

class LoginData(BaseModel):
    username: str
    password: str

class RefreshData(BaseModel):
    refresh_token: str


def _user_payload(user: dict) -> dict:
    import json
    return {
        "user_id":         user["id"],
        "username":        user["username"],
        "role":            user["role"],
        "level":           user["level"],
        "xp":              user["xp"],
        "coins":           user["coins"],
        "hp":              user["hp"],
        "max_hp":          user["max_hp"],
        "streak":          user["streak"],
        "best_streak":     user.get("best_streak", 0),
        "avatar":          user["avatar"],
        "owned_avatars":   json.loads(user.get("owned_avatars") or '["🧙\u200d♂️"]'),
        "stats":           json.loads(user.get("stats") or '{"str":1,"wis":1,"end":1,"cha":1}'),
        "achievements":    json.loads(user.get("achievements") or "[]"),
        "total_completed": user.get("total_completed", 0),
    }


def _do_login(username: str, password: str) -> dict:
    """Спільна логіка входу — використовується і JSON і form ендпоінтами."""
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if user is None or not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Невірний логін або пароль")
    if user["is_banned"]:
        raise HTTPException(status_code=403, detail="Акаунт заблоковано")

    conn = get_connection()
    conn.execute("UPDATE users SET last_active = datetime('now') WHERE id = ?", (user["id"],))
    conn.execute("INSERT INTO action_logs (actor_id, action) VALUES (?, 'login')", (user["id"],))
    conn.commit()
    conn.close()

    return {**_user_payload(dict(user)), **make_tokens(user["id"]), "message": "Вхід успішний"}


# /auth/token — для Swagger UI (приймає form-data)

@router.post("/token", include_in_schema=False)
def token_form(form: OAuth2PasswordRequestForm = Depends()):
    """Swagger UI надсилає form-data сюди після натискання Authorize."""
    result = _do_login(form.username, form.password)
    # Swagger очікує саме {"access_token": та інші токени}
    return {"access_token": result["access_token"], "token_type": "bearer"}


# /auth/login — для фронтенду (приймає JSON)

@router.post("/login")
def login(data: LoginData):
    return _do_login(data.username, data.password)


@router.post("/register")
def register(data: RegisterData):
    if len(data.username) < 3:
        raise HTTPException(status_code=400, detail="Логін мінімум 3 символи")
    if len(data.password) < 4:
        raise HTTPException(status_code=400, detail="Пароль мінімум 4 символи")

    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (data.username,)
    ).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Користувач вже існує")

    email = data.email if data.email else f"{data.username}@habitrpg.com"
    conn.execute("""
        INSERT INTO users (username, email, password, role, level, xp, coins, last_active)
        VALUES (?, ?, ?, 'player', 1, 0, 100, datetime('now'))
    """, (data.username, email, hash_password(data.password)))
    conn.commit()

    user = dict(conn.execute(
        "SELECT * FROM users WHERE username = ?", (data.username,)
    ).fetchone())

    conn.execute("""
        INSERT INTO habits (user_id, title, difficulty, stat, xp_reward, gold_reward)
        VALUES (?, 'Ранкова зарядка 15 хв', 'easy', 'str', 10, 5)
    """, (user["id"],))
    conn.execute("""
        INSERT INTO rewards (user_id, title, cost) VALUES (?, 'Пограти в ігри 1 годину', 50)
    """, (user["id"],))
    conn.execute("""
        INSERT OR REPLACE INTO leaderboard (user_id, username, avatar, level, xp, streak, best_streak, total_completed)
        VALUES (?, ?, ?, 1, 0, 0, 0, 0)
    """, (user["id"], user["username"], user["avatar"]))
    conn.execute(
        "INSERT INTO action_logs (actor_id, action, details) VALUES (?, 'register', ?)",
        (user["id"], data.username)
    )
    conn.commit()
    conn.close()

    return {"message": "Реєстрація успішна", **_user_payload(user), **make_tokens(user["id"])}


@router.post("/refresh")
def refresh(data: RefreshData):
    if not JWT_AVAILABLE:
        raise HTTPException(501, "JWT не налаштовано")
    try:
        payload = jwt.decode(data.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Потрібен refresh token")
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(401, "Недійсний refresh token")

    conn = get_connection()
    user = conn.execute("SELECT id, is_banned FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not user or user["is_banned"]:
        raise HTTPException(401, "Недійсний токен")

    tokens = make_tokens(user_id)
    return {"access_token": tokens["access_token"], "token_type": "bearer"}


# Збереження часу смерті в пам'яті (dict: user_id - datetime)
_death_registry: dict = {}
DEATH_TIMEOUT_SEC = 10  # 15 хвилин

@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    from datetime import datetime, timedelta
    uid = current_user["id"]
    payload = _user_payload(current_user)

    # Перевірка чи гравець мертвий
    if uid in _death_registry:
        died_at = _death_registry[uid]
        seconds_left = DEATH_TIMEOUT_SEC - (datetime.utcnow() - died_at).total_seconds()
        if seconds_left > 0:
            # якщо ще мертвий тоді повертаємо died_at
            payload["died_at"] = died_at.isoformat() + "Z"
            payload["death_seconds_left"] = int(seconds_left)
        else:
            # Час минув тоді відновлюємо HP і прибираємо з реєстру
            del _death_registry[uid]
            conn = get_connection()
            conn.execute("UPDATE users SET hp = max_hp, died_at = NULL WHERE id = ?", (uid,))
            conn.commit()
            updated = dict(conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone())
            conn.close()
            payload = _user_payload(updated)
            payload["just_revived"] = True
            notify_bot_async({"event": "revive", "user_id": uid})

    return payload


def notify_bot_async(payload: dict):
    """Send a best-effort notification to bot /notify endpoint in a background thread."""
    def _send():
        try:
            import requests
            requests.post("http://127.0.0.1:9000/notify", json=payload, timeout=1)
        except Exception:
            pass
    try:
        threading.Thread(target=_send, daemon=True).start()
    except Exception:
        pass

@router.post("/revive")
def revive_me(current_user: dict = Depends(get_current_user)):
    """Гравець самостійно воскресає після смерті (якщо час вийшов)."""
    from datetime import datetime, timedelta
    uid = current_user["id"]
    
    # Перевірка чи гравець мертвий
    if uid not in _death_registry:
        conn = get_connection()
        conn.execute("UPDATE users SET hp = max_hp, died_at = NULL WHERE id = ? AND hp <= 0", (uid,))
        conn.commit()
        conn.close()
        return {"revived": True, "message": "Ви вже живі"}
    
    died_at = _death_registry[uid]
    elapsed = (datetime.utcnow() - died_at).total_seconds()
    
    if elapsed < DEATH_TIMEOUT_SEC:
        secs_left = int(DEATH_TIMEOUT_SEC - elapsed)
        raise HTTPException(403, f"Ще мертвий. Залишилось {secs_left} сек.")

    # Час вийшов тоді йде відродження
    del _death_registry[uid]
    
    conn = get_connection()
    conn.execute("UPDATE users SET hp = max_hp, died_at = NULL WHERE id = ?", (uid,))
    conn.commit()
    updated = dict(conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone())
    conn.close()

    notify_bot_async({"event": "revive", "user_id": uid})

    return {"revived": True, "message": "Воскресіння!", "user": _user_payload(updated)}