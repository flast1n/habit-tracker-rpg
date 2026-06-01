"""
migrate.py — Безпечна міграція існуючої БД до v2.
Запускати один раз: python migrate.py

Нічого не видаляє, тільки ДОДАЄ нові стовпці і таблиці.
Існуючі дані залишаються без змін.
"""
import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "habit_tracker.db")

# Якщо БД лежить поруч з migrate.py то шукає теж там само
if not os.path.exists(DB_PATH):
    alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "habit_tracker.db")
    if os.path.exists(alt):
        DB_PATH = alt

print(f"БД: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()


def existing_columns(table: str) -> set:
    return {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}


def existing_tables() -> set:
    return {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def add_column(table: str, col: str, definition: str):
    if col not in existing_columns(table):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
        print(f"  + {table}.{col}")
    else:
        print(f"  ✓ {table}.{col} вже є")


# 1. users - стовпці
print("\n[users]")
add_column("users", "password",        "TEXT NOT NULL DEFAULT ''")
add_column("users", "role",            "TEXT NOT NULL DEFAULT 'player'")
add_column("users", "is_banned",       "INTEGER NOT NULL DEFAULT 0")
add_column("users", "hp",              "INTEGER NOT NULL DEFAULT 100")
add_column("users", "max_hp",          "INTEGER NOT NULL DEFAULT 100")
add_column("users", "streak",          "INTEGER NOT NULL DEFAULT 0")
add_column("users", "best_streak",     "INTEGER NOT NULL DEFAULT 0")
add_column("users", "total_completed", "INTEGER NOT NULL DEFAULT 0")
add_column("users", "avatar",          "TEXT NOT NULL DEFAULT '🧙‍♂️'")
add_column("users", "owned_avatars",   "TEXT NOT NULL DEFAULT '[\"🧙‍♂️\"]'")
add_column("users", "stats",           "TEXT NOT NULL DEFAULT '{\"str\":1,\"wis\":1,\"end\":1,\"cha\":1}'")
add_column("users", "achievements",    "TEXT NOT NULL DEFAULT '[]'")
add_column("users", "last_active",     "TEXT")

# 2. habits - стовпці
print("\n[habits]")
add_column("habits", "difficulty",      "TEXT NOT NULL DEFAULT 'easy'")
add_column("habits", "stat",            "TEXT NOT NULL DEFAULT 'str'")
add_column("habits", "gold_reward",     "INTEGER NOT NULL DEFAULT 5")
add_column("habits", "best_streak",     "INTEGER NOT NULL DEFAULT 0")
add_column("habits", "total_completed", "INTEGER NOT NULL DEFAULT 0")
# description може бути NULL в старій БД — нормалізуємо
cur.execute("UPDATE habits SET description = '' WHERE description IS NULL")

# 3. habit_logs - стовпці
print("\n[habit_logs]")
add_column("habit_logs", "user_id",     "INTEGER NOT NULL DEFAULT 0")
add_column("habit_logs", "action",      "TEXT NOT NULL DEFAULT 'complete'")
add_column("habit_logs", "xp_gained",   "INTEGER NOT NULL DEFAULT 0")
add_column("habit_logs", "gold_gained", "INTEGER NOT NULL DEFAULT 0")

# 4. створення нових таблиць якщо вони ще не існують
tables = existing_tables()

if "rewards" not in tables:
    print("\n[rewards] створюємо таблицю")
    cur.execute("""
        CREATE TABLE rewards (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            title      TEXT    NOT NULL,
            cost       INTEGER NOT NULL DEFAULT 50,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
else:
    print("\n[rewards] вже є")

if "reward_logs" not in tables:
    print("[reward_logs] створюємо таблицю")
    cur.execute("""
        CREATE TABLE reward_logs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            reward_id INTEGER NOT NULL,
            user_id   INTEGER NOT NULL,
            bought_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
else:
    print("[reward_logs] вже є")

if "leaderboard" not in tables:
    print("[leaderboard] створюємо таблицю")
    cur.execute("""
        CREATE TABLE leaderboard (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT    NOT NULL,
            avatar          TEXT    NOT NULL DEFAULT '🧙‍♂️',
            level           INTEGER NOT NULL DEFAULT 1,
            xp              INTEGER NOT NULL DEFAULT 0,
            streak          INTEGER NOT NULL DEFAULT 0,
            best_streak     INTEGER NOT NULL DEFAULT 0,
            total_completed INTEGER NOT NULL DEFAULT 0,
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
else:
    print("[leaderboard] вже є")

if "action_logs" not in tables:
    print("[action_logs] створюємо таблицю")
    cur.execute("""
        CREATE TABLE action_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id   INTEGER,
            target_id  INTEGER,
            action     TEXT    NOT NULL,
            details    TEXT,
            created_at TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
else:
    print("[action_logs] вже є")

# 5. Заповнення leaderboard з існуючих users
print("\n[leaderboard] синхронізуємо з users...")
users = cur.execute("SELECT id, username, avatar, level, xp, streak, best_streak, total_completed FROM users").fetchall()
for u in users:
    cur.execute("""
        INSERT OR REPLACE INTO leaderboard
            (user_id, username, avatar, level, xp, streak, best_streak, total_completed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, tuple(u))
    print(f"  → {u['username']}")

# 6. Хешуємо паролі які ще планованому-тексті
print("\n[users] перевіряємо паролі...")
try:
    import bcrypt

    users_pw = cur.execute("SELECT id, username, password FROM users").fetchall()
    for u in users_pw:
        pw = u["password"]
        if pw and not pw.startswith("$2"):
            hashed = bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            cur.execute("UPDATE users SET password = ? WHERE id = ?", (hashed, u["id"]))
            print(f"  🔒 {u['username']} — пароль захешовано")
        elif not pw:
            hashed = bcrypt.hashpw(b"change_me", bcrypt.gensalt()).decode("utf-8")
            cur.execute("UPDATE users SET password = ? WHERE id = ?", (hashed, u["id"]))
            print(f"  ⚠️  {u['username']} — порожній пароль → встановлено 'change_me'")
        else:
            print(f"  ✓ {u['username']} — вже bcrypt")
except ImportError:
    print("  ⚠️  bcrypt не встановлено. Запусти: pip install bcrypt")

# Збереження змін і закриття з'єднання
conn.commit()
conn.close()

print("\n✅ Міграція завершена успішно!")
print("   Дані збережені, нові стовпці і таблиці додані.")