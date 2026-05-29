from apscheduler.schedulers.background import BackgroundScheduler
from database import get_connection


# ── Оригінальні функції збережені, трохи розширені ───────────────────────────

def reset_daily_habits():
    conn = get_connection()

    # Оригінал: штраф за невиконані звички
    not_done = conn.execute("""
        SELECT id, user_id, xp_reward, streak
        FROM habits
        WHERE frequency = 'daily' AND is_done = 0 AND streak > 0
    """).fetchall()

    for habit in not_done:
        penalty = habit["xp_reward"]
        conn.execute("""
            UPDATE users SET xp = MAX(0, xp - ?), hp = MAX(0, hp - 5)
            WHERE id = ?
        """, (penalty, habit["user_id"]))
        conn.execute("UPDATE habits SET streak = 0 WHERE id = ?", (habit["id"],))

    # Оригінал: скид is_done
    conn.execute("UPDATE habits SET is_done = 0 WHERE frequency = 'daily'")

    conn.commit()
    conn.close()
    print("✅ [Scheduler] Щоденне скидання виконано о 00:00")


def reset_weekly_habits():
    conn = get_connection()

    not_done = conn.execute("""
        SELECT id, user_id, xp_reward, streak
        FROM habits
        WHERE frequency = 'weekly' AND is_done = 0 AND streak > 0
    """).fetchall()

    for habit in not_done:
        penalty = habit["xp_reward"]
        conn.execute("UPDATE users SET xp = MAX(0, xp - ?), hp = MAX(0, hp - 10) WHERE id = ?",
                     (penalty, habit["user_id"]))
        conn.execute("UPDATE habits SET streak = 0 WHERE id = ?", (habit["id"],))

    conn.execute("UPDATE habits SET is_done = 0 WHERE frequency = 'weekly'")

    conn.commit()
    conn.close()
    print("✅ [Scheduler] Тижневе скидання виконано")


# ── НОВІ функції ──────────────────────────────────────────────────────────────

def award_streak_bonuses():
    """Кожен 7-й день стріку гравець отримує +100 монет."""
    conn = get_connection()
    eligible = conn.execute("""
        SELECT id, username, streak FROM users
        WHERE streak > 0 AND streak % 7 = 0 AND is_banned = 0
    """).fetchall()

    for user in eligible:
        bonus = 100
        conn.execute("UPDATE users SET coins = coins + ? WHERE id = ?", (bonus, user["id"]))
        conn.execute("""
            INSERT INTO action_logs (actor_id, action, details)
            VALUES (?, 'streak_bonus', ?)
        """, (user["id"], f"+{bonus} монет за {user['streak']}-денний стрік"))
        print(f"  💰 {user['username']} +{bonus} монет (стрік {user['streak']})")

    conn.commit()
    conn.close()
    print("✅ [Scheduler] Бонуси за стрік нараховано")


def rebuild_leaderboard():
    """Перебудовує leaderboard з актуальних даних users."""
    conn = get_connection()
    users = conn.execute("""
        SELECT id, username, avatar, level, xp, streak, best_streak, total_completed
        FROM users WHERE is_banned = 0
    """).fetchall()

    for u in users:
        conn.execute("""
            INSERT OR REPLACE INTO leaderboard
                (user_id, username, avatar, level, xp, streak, best_streak, total_completed, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, tuple(u))

    conn.commit()
    conn.close()
    print("✅ [Scheduler] Leaderboard перебудовано")

def revive_dead_players():
    conn = get_connection()
    conn.execute("""
        UPDATE users SET hp = max_hp, died_at = NULL
        WHERE hp <= 0 AND died_at IS NOT NULL
        AND (strftime('%s','now') - strftime('%s', died_at)) >= 900
    """)
    conn.commit()
    conn.close()
    print("❤️ [Scheduler] Воскресіння виконано")

# ── Оригінальна функція start_scheduler, розширена ───────────────────────────

def start_scheduler():
    from pytz import timezone
    scheduler = BackgroundScheduler(timezone=timezone("Europe/Kiev"))

    # Оригінальні jobs
    scheduler.add_job(reset_daily_habits,  "cron", hour=0, minute=0)
    scheduler.add_job(reset_weekly_habits, "cron", day_of_week="mon", hour=0, minute=0)
    scheduler.add_job(revive_dead_players, "interval", minutes=15)

    # Нові jobs
    scheduler.add_job(award_streak_bonuses, "cron", hour=0, minute=5)
    scheduler.add_job(rebuild_leaderboard,  "cron", hour=0, minute=10)

    scheduler.start()
    print("⏰ [Scheduler] Запущено — скидання о 00:00 за Києвом")
