import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
import json
import os
from aiohttp import web

# ──Налаштування 

BOT_TOKEN = "8413701904:AAErbEx1ovT8Di1kIErviCFp9yGDKF-jSzk"

API_URL   = "http://127.0.0.1:8000"
KYIV_TZ   = pytz.timezone("Europe/Kiev")

bot        = Bot(token=BOT_TOKEN)
dp         = Dispatcher(storage=MemoryStorage())
scheduler  = AsyncIOScheduler(timezone=KYIV_TZ)

# Збереження токенів юзерів: {telegram_id: access_token}
user_tokens: dict = {}
# Track which users we've already notified about death to avoid duplicate alerts
notified_deaths: dict = {}  # { telegram_id: user_id }
# persistent store file
STORE_PATH = os.path.join(os.path.dirname(__file__), "bot_store.json")
# runtime store loaded from disk
store: dict = {}


def load_store():
    global store
    try:
        if os.path.exists(STORE_PATH):
            with open(STORE_PATH, "r", encoding="utf-8") as f:
                store = json.load(f)
        else:
            store = {}
    except Exception:
        store = {}


def save_store():
    try:
        with open(STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# Стани FSM 

class LoginStates(StatesGroup):
    waiting_username = State()
    waiting_password = State()

class AddHabitStates(StatesGroup):
    waiting_title      = State()
    waiting_difficulty = State()

# ── Кнопки управління

def main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Мій профіль"),  KeyboardButton(text="📋 Мої звички")],
        [KeyboardButton(text="➕ Додати звичку"), KeyboardButton(text="✅ Виконати звичку")],
        [KeyboardButton(text="❌ Пропустити звичку"), KeyboardButton(text="🚪 Вийти")],
    ], resize_keyboard=True)

def difficulty_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⚡ Легка"),  KeyboardButton(text="🔥 Середня")],
        [KeyboardButton(text="💀 Важка"), KeyboardButton(text="❌ Скасувати")],
    ], resize_keyboard=True)

# ── допоміжні API 

async def api_post(path: str, body: dict, token: str = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{API_URL}{path}", json=body, headers=headers) as r:
            return await r.json(), r.status

async def api_get(path: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{API_URL}{path}", headers=headers) as r:
            return await r.json(), r.status

async def api_delete(path: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as s:
        async with s.delete(f"{API_URL}{path}", headers=headers) as r:
            return await r.json(), r.status


@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    tg_id = message.from_user.id
    if tg_id in user_tokens:
        await message.answer("Ти вже увійшов! Використовуй меню нижче.", reply_markup=main_keyboard())
        return
    await message.answer(
        "👋 Вітаю в <b>HabitRPG Bot</b>!\n\nВведи свій <b>логін</b>:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(LoginStates.waiting_username)

# ── Логін 

@dp.message(LoginStates.waiting_username)
async def login_username(message: types.Message, state: FSMContext):
    await state.update_data(username=message.text.strip())
    await message.answer("🔒 Введи <b>пароль</b>:", parse_mode="HTML")
    await state.set_state(LoginStates.waiting_password)

@dp.message(LoginStates.waiting_password)
async def login_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    username = data["username"]
    password = message.text.strip()

    data_resp, status = await api_post("/auth/login", {"username": username, "password": password})

    if status != 200:
        detail = data_resp.get("detail", "Невірний логін або пароль")
        await message.answer(f"❌ {detail}\n\nСпробуй ще раз — введи логін:")
        await state.set_state(LoginStates.waiting_username)
        return

    # store tokens and user mapping persistently
    access = data_resp.get("access_token")
    refresh = data_resp.get("refresh_token")
    uid = data_resp.get("user_id") or data_resp.get("userId")
    store_key = str(message.from_user.id)
    store[store_key] = {"access_token": access, "refresh_token": refresh, "user_id": uid}
    save_store()
    user_tokens[message.from_user.id] = access
    # clear any previous death-notification state for this telegram user
    notified_deaths.pop(message.from_user.id, None)
    await state.clear()

    u = data_resp
    text = (
        f"✅ Успішний вхід!\n\n"
        f"🧙 <b>{u['username']}</b>\n"
        f"⚔️ Рівень {u['level']} · ⚡ {u['xp']} XP\n"
        f"❤️ HP: {u['hp']}/{u['max_hp']}\n"
        f"💰 Монети: {u['coins']}\n"
        f"🔥 Стрік: {u['streak']} днів"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard())

# ── Профіль 
@dp.message(F.text == "👤 Мій профіль")
async def show_profile(message: types.Message):
    token = user_tokens.get(message.from_user.id)
    if not token:
        await message.answer("Спочатку увійди — натисни /start")
        return

    data, status = await api_get("/auth/me", token)
    if status != 200:
        await message.answer("❌ Помилка отримання профілю")
        return

    u = data
    stats = u.get("stats", {})
    if isinstance(stats, str):
        import json
        stats = json.loads(stats)

    text = (
        f"👤 <b>Профіль: {u['username']}</b>\n\n"
        f"🏆 Рівень: <b>{u['level']}</b>\n"
        f"⚡ XP: {u['xp']} / {100 + (u['level']-1)*50}\n"
        f"❤️ HP: {u['hp']}/{u['max_hp']}\n"
        f"💰 Монети: {u['coins']}\n"
        f"🔥 Стрік: {u['streak']} днів\n\n"
        f"📊 <b>Характеристики:</b>\n"
        f"⚔️ Сила: {stats.get('str', 1)}\n"
        f"📚 Інтелект: {stats.get('wis', 1)}\n"
        f"🛡️ Витривалість: {stats.get('end', 1)}\n"
        f"✨ Харизма: {stats.get('cha', 1)}\n\n"
        f"✅ Виконано всього: {u.get('total_completed', 0)}"
    )
    await message.answer(text, parse_mode="HTML")

# ── Список звичок
@dp.message(F.text == "📋 Мої звички")
async def show_habits(message: types.Message):
    token = user_tokens.get(message.from_user.id)
    if not token:
        await message.answer("Спочатку увійди — натисни /start")
        return

    me, _ = await api_get("/auth/me", token)
    habits, status = await api_get(f"/habits/user/{me['user_id']}", token)

    if status != 200 or not habits:
        await message.answer("📋 У тебе поки немає звичок. Додай першу!")
        return

    lines = ["📋 <b>Мої звички:</b>\n"]
    for h in habits:
        done = "✅" if h["is_done"] else "⬜"
        diff = {"easy": "⚡", "medium": "🔥", "hard": "💀"}.get(h["difficulty"], "")
        lines.append(f"{done} {diff} <b>{h['title']}</b> (🔥 стрік: {h['streak']})")

    await message.answer("\n".join(lines), parse_mode="HTML")

# ── Додати звичку
@dp.message(F.text == "➕ Додати звичку")
async def add_habit_start(message: types.Message, state: FSMContext):
    if message.from_user.id not in user_tokens:
        await message.answer("Спочатку увійди — натисни /start")
        return
    await message.answer("✏️ Введи назву нової звички:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddHabitStates.waiting_title)

@dp.message(AddHabitStates.waiting_title)
async def add_habit_title(message: types.Message, state: FSMContext):
    if message.text == "❌ Скасувати":
        await state.clear()
        await message.answer("Скасовано.", reply_markup=main_keyboard())
        return
    await state.update_data(title=message.text.strip())
    await message.answer("Обери складність:", reply_markup=difficulty_keyboard())
    await state.set_state(AddHabitStates.waiting_difficulty)

@dp.message(AddHabitStates.waiting_difficulty)
async def add_habit_difficulty(message: types.Message, state: FSMContext):
    if message.text == "❌ Скасувати":
        await state.clear()
        await message.answer("Скасовано.", reply_markup=main_keyboard())
        return

    diff_map = {"⚡ Легка": "easy", "🔥 Середня": "medium", "💀 Важка": "hard"}
    difficulty = diff_map.get(message.text)
    if not difficulty:
        await message.answer("Обери складність з кнопок нижче:")
        return

    data = await state.get_data()
    token = user_tokens[message.from_user.id]

    resp, status = await api_post("/habits/", {
        "title": data["title"],
        "difficulty": difficulty,
        "stat": "str",
        "frequency": "daily"
    }, token)

    await state.clear()
    if status == 200:
        await message.answer(f"✅ Звичку <b>{data['title']}</b> додано!", parse_mode="HTML", reply_markup=main_keyboard())
    else:
        await message.answer(f"❌ Помилка: {resp.get('detail', 'Невідома помилка')}", reply_markup=main_keyboard())

# ── Виконати звичку
@dp.message(F.text == "✅ Виконати звичку")
async def complete_habit_menu(message: types.Message):
    token = user_tokens.get(message.from_user.id)
    if not token:
        await message.answer("Спочатку увійди — натисни /start")
        return

    me, _ = await api_get("/auth/me", token)
    habits, _ = await api_get(f"/habits/user/{me['user_id']}", token)

    not_done = [h for h in habits if not h["is_done"]]
    if not not_done:
        await message.answer("🎉 Всі звички на сьогодні виконані!")
        return

    buttons = [[KeyboardButton(text=f"✅ {h['title']}")] for h in not_done]
    buttons.append([KeyboardButton(text="❌ Скасувати")])
    kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("Обери звичку яку виконав:", reply_markup=kb)

@dp.message(F.text.startswith("✅ "))
async def complete_habit_action(message: types.Message):
    token = user_tokens.get(message.from_user.id)
    if not token:
        return

    title = message.text[2:].strip()
    me, _ = await api_get("/auth/me", token)
    habits, _ = await api_get(f"/habits/user/{me['user_id']}", token)
    habit = next((h for h in habits if h["title"] == title), None)

    if not habit:
        await message.answer("Звичку не знайдено.", reply_markup=main_keyboard())
        return

    resp, status = await api_post(f"/habits/{habit['id']}/complete", {}, token)
    if status == 200:
        await message.answer(
            f"✅ <b>{title}</b> виконано!\n+{resp.get('xp_gained', 0)} XP · +{resp.get('gold_gained', 0)} 💰",
            parse_mode="HTML", reply_markup=main_keyboard()
        )
    else:
        await message.answer(f"❌ {resp.get('detail', 'Помилка')}", reply_markup=main_keyboard())

# ── Пропустити звичку 

@dp.message(F.text == "❌ Пропустити звичку")
async def fail_habit_menu(message: types.Message):
    token = user_tokens.get(message.from_user.id)
    if not token:
        await message.answer("Спочатку увійди — натисни /start")
        return

    me, _ = await api_get("/auth/me", token)
    habits, _ = await api_get(f"/habits/user/{me['user_id']}", token)

    not_done = [h for h in habits if not h["is_done"]]
    if not not_done:
        await message.answer("Немає активних звичок для пропуску.")
        return

    buttons = [[KeyboardButton(text=f"❌ {h['title']}")] for h in not_done]
    buttons.append([KeyboardButton(text="🔙 Назад")])
    kb = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    await message.answer("Обери звичку яку пропускаєш:", reply_markup=kb)

@dp.message(F.text.startswith("❌ ") & ~F.text.in_({"❌ Пропустити звичку", "❌ Скасувати"}))
async def fail_habit_action(message: types.Message):
    token = user_tokens.get(message.from_user.id)
    if not token:
        return

    title = message.text[2:].strip()
    me, _ = await api_get("/auth/me", token)
    habits, _ = await api_get(f"/habits/user/{me['user_id']}", token)
    habit = next((h for h in habits if h["title"] == title), None)

    if not habit:
        await message.answer("Звичку не знайдено.", reply_markup=main_keyboard())
        return

    resp, status = await api_post(f"/habits/{habit['id']}/fail", {}, token)
    if status == 200:
        died = resp.get("died", False)
        text = f"💔 <b>{title}</b> пропущено. −{resp.get('hp_lost', 0)} HP"
        if died:
            text += "\n\n💀 <b>Ти загинув!</b> HP вичерпано. Відновлення через 15 хвилин."
        await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard())
    else:
        await message.answer(f"❌ {resp.get('detail', 'Помилка')}", reply_markup=main_keyboard())

# ── Вийти 

@dp.message(F.text == "🚪 Вийти")
async def logout(message: types.Message):
    user_tokens.pop(message.from_user.id, None)
    # clear any death-notification state for this telegram user
    notified_deaths.pop(message.from_user.id, None)
    await message.answer("👋 Вийшов з акаунту. Натисни /start щоб увійти знову.", reply_markup=ReplyKeyboardRemove())


async def find_tg_ids_by_user(user_id):
    res = []
    for tg, v in store.items():
        try:
            if v and str(v.get("user_id")) == str(user_id):
                res.append(int(tg))
        except Exception:
            continue
    return res


async def send_death_message(tg_id: int, seconds_left):
    if seconds_left:
        mm = int(seconds_left) // 60
        ss = int(seconds_left) % 60
        await bot.send_message(tg_id, f"💀 Твій герой загинув! Відродження через {mm:02d}:{ss:02d}.")
    else:
        await bot.send_message(tg_id, "💀 Твій герой загинув! Очікується відродження.")


async def send_revive_message(tg_id: int):
    await bot.send_message(tg_id, "❤️ Ти воскрес! HP відновлено!")


async def send_notify_to_tg(user_id, payload: dict):
    tg_ids = await find_tg_ids_by_user(user_id)
    for tg in tg_ids:
        try:
            ev = payload.get("event")
            if ev == "death":
                await send_death_message(tg, payload.get("seconds_left"))
                notified_deaths[tg] = user_id
            elif ev == "revive":
                await send_revive_message(tg)
                notified_deaths.pop(tg, None)
            else:
                text = payload.get("text") or json.dumps(payload)
                await bot.send_message(tg, text)
        except Exception:
            pass


# aiohttp notify endpoint for backend to call
async def notify_handler(request):
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)
    event = data.get("event")
    user_id = data.get("user_id")
    if not event or not user_id:
        return web.json_response({"error": "missing fields"}, status=400)
    # dispatch notification to linked telegrams
    asyncio.create_task(send_notify_to_tg(user_id, data))
    return web.json_response({"ok": True})


async def start_notify_server():
    app = web.Application()
    app.router.add_post('/notify', notify_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 9000)
    await site.start()

@dp.message(F.text == "🔙 Назад")
async def go_back(message: types.Message):
    await message.answer("Головне меню:", reply_markup=main_keyboard())

# ── Нагадування о 21:00 

async def send_reminders():
    for tg_id, token in list(user_tokens.items()):
        try:
            me, status = await api_get("/auth/me", token)
            if status != 200:
                continue

            habits, _ = await api_get(f"/habits/user/{me['user_id']}", token)
            not_done = [h for h in habits if not h["is_done"]]

            if not_done:
                names = "\n".join(f"• {h['title']}" for h in not_done)
                await bot.send_message(
                    tg_id,
                    f"⏰ <b>Нагадування!</b>\n\n"
                    f"У тебе ще є {len(not_done)} невиконаних звичок:\n{names}\n\n"
                    f"🔥 Виконай їх до кінця дня щоб не втратити стрік!",
                    parse_mode="HTML"
                )
        except Exception:
            pass


# ── Перевірка смерті гравців (щоб бот отримував ті самі повідомлення що й сайт)
async def check_user_deaths():
    for tg_id, token in list(user_tokens.items()):
        try:
            me, status = await api_get("/auth/me", token)
            if status != 200:
                continue

            user_id = me.get("user_id")
            dead = False
            secs = me.get("death_seconds_left")
            if isinstance(secs, (int, float)) and secs > 0:
                dead = True
            elif me.get("hp") == 0:
                dead = True

            prev_notified = notified_deaths.get(tg_id)

            if dead and prev_notified != user_id:
                await send_death_message(tg_id, secs)
                notified_deaths[tg_id] = user_id

            if (not dead) and prev_notified == user_id:
                await send_revive_message(tg_id)
                notified_deaths.pop(tg_id, None)

        except Exception:
            # ignore per-user errors
            pass

# ── Запуск 

async def main():
    # load persistent store and populate runtime tokens
    load_store()
    for k, v in list(store.items()):
        try:
            tid = int(k)
            tok = v.get("access_token")
            if tok:
                user_tokens[tid] = tok
        except Exception:
            continue

    # start HTTP notify server
    await start_notify_server()

    scheduler.add_job(send_reminders, "cron", hour=21, minute=0)
    # Check for player deaths every 10 seconds to sync site -> bot notifications
    scheduler.add_job(check_user_deaths, "interval", seconds=10)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())