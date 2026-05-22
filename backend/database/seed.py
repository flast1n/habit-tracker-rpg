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

    # Тестовий користувач
    cursor.execute("""
        INSERT INTO users (username, email, level, xp, coins)
        VALUES (?, ?, ?, ?, ?)
    """, ("hero_student", "student@example.com", 3, 250, 80))

    user_id = cursor.lastrowid

    # Тестові звички
    habits = [
        (user_id, "Читати 20 хвилин",     "Читати будь-яку книгу",    "daily",   15),
        (user_id, "Зарядка",               "Ранкова зарядка 10 хв",    "daily",   20),
        (user_id, "Повторити конспекти",   "Переглянути нотатки дня",  "daily",   10),
        (user_id, "Тижневий проєкт",       "Попрацювати над проєктом", "weekly",  50),
    ]

    cursor.executemany("""
        INSERT INTO habits (user_id, title, description, frequency, xp_reward, streak)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [h + (0,) for h in habits])

    conn.commit()
    conn.close()
    print("Тестові дані додано успішно.")
