import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "habit_tracker.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            username        TEXT    NOT NULL UNIQUE,
            email           TEXT    NOT NULL UNIQUE,
            password        TEXT    NOT NULL DEFAULT '',
            role            TEXT    NOT NULL DEFAULT 'player',
            is_banned       INTEGER NOT NULL DEFAULT 0,
            level           INTEGER NOT NULL DEFAULT 1,
            xp              INTEGER NOT NULL DEFAULT 0,
            coins           INTEGER NOT NULL DEFAULT 100,
            hp              INTEGER NOT NULL DEFAULT 100,
            max_hp          INTEGER NOT NULL DEFAULT 100,
            streak          INTEGER NOT NULL DEFAULT 0,
            best_streak     INTEGER NOT NULL DEFAULT 0,
            total_completed INTEGER NOT NULL DEFAULT 0,
            avatar          TEXT    NOT NULL DEFAULT '🧙‍♂️',
            owned_avatars   TEXT    NOT NULL DEFAULT '["🧙‍♂️"]',
            stats           TEXT    NOT NULL DEFAULT '{"str":1,"wis":1,"end":1,"cha":1}',
            achievements    TEXT    NOT NULL DEFAULT '[]',
            last_active     TEXT,
            died_at         TEXT,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS habits (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL,
            title           TEXT    NOT NULL,
            description     TEXT    NOT NULL DEFAULT '',
            frequency       TEXT    NOT NULL DEFAULT 'daily',
            difficulty      TEXT    NOT NULL DEFAULT 'easy',
            stat            TEXT    NOT NULL DEFAULT 'str',
            xp_reward       INTEGER NOT NULL DEFAULT 10,
            gold_reward     INTEGER NOT NULL DEFAULT 5,
            streak          INTEGER NOT NULL DEFAULT 0,
            best_streak     INTEGER NOT NULL DEFAULT 0,
            is_done         INTEGER NOT NULL DEFAULT 0,
            total_completed INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS habit_logs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id    INTEGER NOT NULL,
            user_id     INTEGER NOT NULL DEFAULT 0,
            action      TEXT    NOT NULL DEFAULT 'complete',
            xp_gained   INTEGER NOT NULL DEFAULT 0,
            gold_gained INTEGER NOT NULL DEFAULT 0,
            done_at     TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (habit_id) REFERENCES habits(id)
        );

        -- Нові таблиці
        CREATE TABLE IF NOT EXISTS rewards (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            title      TEXT    NOT NULL,
            cost       INTEGER NOT NULL DEFAULT 50,
            created_at TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS reward_logs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            reward_id INTEGER NOT NULL,
            user_id   INTEGER NOT NULL,
            bought_at TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS leaderboard (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT    NOT NULL,
            avatar          TEXT    NOT NULL DEFAULT '🧙‍♂️',
            level           INTEGER NOT NULL DEFAULT 1,
            xp              INTEGER NOT NULL DEFAULT 0,
            streak          INTEGER NOT NULL DEFAULT 0,
            best_streak     INTEGER NOT NULL DEFAULT 0,
            total_completed INTEGER NOT NULL DEFAULT 0,
            updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
        );

CREATE TABLE IF NOT EXISTS activity_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            message    TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    conn.commit()
    conn.close()
    print(f"База даних ініціалізована: {DB_PATH}")