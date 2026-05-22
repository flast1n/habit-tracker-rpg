from apscheduler.schedulers.background import BackgroundScheduler
from database import get_connection


def reset_daily_habits():
    conn = get_connection()

    # Знаходимо всі щоденні звички які не були виконані
    not_done = conn.execute("""
        SELECT id, user_id, xp_reward, streak
        FROM habits
        WHERE frequency = 'daily' AND is_done = 0 AND streak > 0
    """).fetchall()

    # За кожну невиконану звичку знімаємо XP і скидаємо streak
    for habit in not_done:
        penalty = habit["xp_reward"]

        conn.execute("""
            UPDATE users
            SET xp = MAX(0, xp - ?)
            WHERE id = ?
        """, (penalty, habit["user_id"]))

        conn.execute("""
            UPDATE habits SET streak = 0 WHERE id = ?
        """, (habit["id"],))

    # Скидаємо is_done для всіх щоденних звичок
    conn.execute("""
        UPDATE habits SET is_done = 0 WHERE frequency = 'daily'
    """)

    conn.commit()
    conn.close()
    print("Щоденне скидання виконано о 00:00")

def reset_weekly_habits():
    conn = get_connection()

    not_done = conn.execute("""
        SELECT id, user_id, xp_reward, streak
        FROM habits
        WHERE frequency = 'weekly' AND is_done = 0 AND streak > 0
    """).fetchall()

    for habit in not_done:
        penalty = habit["xp_reward"]
        conn.execute("UPDATE users SET xp = MAX(0, xp - ?) WHERE id = ?", (penalty, habit["user_id"]))
        conn.execute("UPDATE habits SET streak = 0 WHERE id = ?", (habit["id"],))

    conn.execute("UPDATE habits SET is_done = 0 WHERE frequency = 'weekly'")

    conn.commit()
    conn.close()
    print("Тижневе скидання виконано")


def start_scheduler():
    from pytz import timezone
    scheduler = BackgroundScheduler(timezone = timezone("Europe/Kiev"))

    # Запуск оновлених звичок reset_daily_habits кожен день о 0:00, або щотижневих звичок reset_weekly_habits кожен день перезапускаються в Понеділок в 0:00
    scheduler.add_job(reset_daily_habits, "cron", hour = 0, minute = 0)
    scheduler.add_job(reset_weekly_habits, "cron", day_of_week = "mon", hour = 0, minute = 0)

    scheduler.start()
    print("Scheduler запущено — скидання звичок о 00:00")
