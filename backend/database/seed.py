from .db import get_connection, init_db


def seed_fake_data():
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    # Перевіряємо чи вже є дані — не дублюємо
    existing = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        print("Тестові дані вже існують, пропускаємо.")
        conn.close()
        return

    # Хешуємо паролі через bcrypt
    try:
        import bcrypt as _bcrypt
        hash_fn = lambda p: _bcrypt.hashpw(p.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    except ImportError:
        hash_fn = lambda p: p

    import json

    # Тестові користувачі
    users = [
        ("admin",        "admin@example.com",   "admin123",  "admin"),
        ("hero_student", "student@example.com", "hero123",   "player"),
    ]

    for username, email, password, role in users:
        cursor.execute("""
            INSERT INTO users (username, email, password, role, level, xp, coins,
                               stats, owned_avatars, last_active)
            VALUES (?, ?, ?, ?, 3, 250, 340,
                    '{"str":5,"wis":8,"end":3,"cha":2}',
                    '["🧙‍♂️"]',
                    datetime('now'))
        """, (username, email, hash_fn(password), role))

    user_id = cursor.execute(
        "SELECT id FROM users WHERE username = 'hero_student'"
    ).fetchone()[0]

    # Тестові звички (додано stat і gold_reward)
    habits = [
        (user_id, "Ранкова зарядка 15 хв", "Зарядка вранці",        "daily",  "easy",   "str", 10, 5),
        (user_id, "Вчити програмування",    "Python та FastAPI",     "daily",  "hard",   "wis", 40, 25),
        (user_id, "Читати 20 хвилин",       "Будь-яка книга",        "daily",  "medium", "wis", 20, 12),
        (user_id, "Тижневий проєкт",         "Попрацювати над проєктом", "weekly", "hard", "wis", 50, 30),
    ]

    cursor.executemany("""
        INSERT INTO habits (user_id, title, description, frequency, difficulty, stat, xp_reward, gold_reward, streak)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
    """, habits)

    # Тестові нагороди (нова таблиця)
    cursor.executemany(
        "INSERT INTO rewards (user_id, title, cost) VALUES (?, ?, ?)",
        [
            (user_id, "Пограти в ігри 1 годину", 50),
            (user_id, "З'їсти смачну піцу",       120),
        ]
    )

    # Початковий запис у leaderboard
    for row in cursor.execute("SELECT id, username, avatar, level, xp, streak FROM users").fetchall():
        cursor.execute("""
            INSERT OR REPLACE INTO leaderboard (user_id, username, avatar, level, xp, streak, best_streak, total_completed)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0)
        """, tuple(row))

    conn.commit()
    conn.close()
    print("Тестові дані додано успішно.")