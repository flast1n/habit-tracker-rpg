"""
migrate_activity_log.py — створює таблицю activity_logs.
Запустити один раз: python migrate_activity_log.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "habit_tracker.db")
if not os.path.exists(DB_PATH):
    alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "habit_tracker.db")
    if os.path.exists(alt):
        DB_PATH = alt

print(f"БД: {DB_PATH}")
conn = sqlite3.connect(DB_PATH)
cur  = conn.cursor()

tables = {r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
if "activity_logs" not in tables:
    cur.execute("""
        CREATE TABLE activity_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            message    TEXT    NOT NULL,
            created_at TEXT    NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    print("  + таблиця activity_logs створена")
else:
    print("  ✓ activity_logs вже є")

conn.commit()
conn.close()
print("✅ Готово!")
