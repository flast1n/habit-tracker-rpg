# HabitRPG

## Огляд

HabitRPG — це простий гейміфікований трекер звичок з веб-фронтендом, FastAPI бекендом, SQLite збереженням і Telegram-ботом.

Проєкт містить:

- `HabitRPG/backend/` — серверна частина з REST API, адміністративними маршрутами та базою даних.
- `HabitRPG/frontend/` — фронтенд на чистому JavaScript і HTML/CSS.
- `HabitRPG/backend/bot.py` — Telegram-бот, який синхронізує стан гравця з сайтом.
- `HabitRPG/requirements.txt` — Python-залежності для бекенду і бота.

## Файли та папки

### Корінь проєкту

- `README.md` — цей файл з описом.
- `LICENSE` — ліцензія проєкту.
- `_.gitignore` — правила ігнорування файлів для git.
- `index.html` — порожня шаблонна сторінка у корені.
- `init.py` — простий імпорт для пакету (необхідний для локального імпорту).

### `HabitRPG/requirements.txt`

Залежності Python для запуску FastAPI та Telegram-бота:

- `fastapi`
- `uvicorn`
- `apscheduler`
- `pytz`
- `passlib[bcrypt]`
- `python-jose[cryptography]`
- `python-multipart`

### `HabitRPG/backend/`

#### `HabitRPG/backend/app/main.py`

Головний FastAPI додаток. Підключає роутери, налаштовує CORS та викликає ініціалізацію бази даних при старті.

#### `HabitRPG/backend/app/routes_auth.py`

Маршрути авторизації та реєстрації:

- `/auth/login`
- `/auth/register`
- `/auth/token`
- `/auth/refresh`
- `/auth/me`
- `/auth/revive`

Тут також реалізована логіка JWT, перевірка користувача, стан смерті/відродження (`_death_registry`) та нотифікація Telegram-бота через `notify_bot_async()`.

#### `HabitRPG/backend/app/routes_habits.py`

Маршрути звичок:

- `GET /habits/user/{user_id}` — перелік звичок користувача
- `POST /habits/` — створення звички
- `PUT /habits/{habit_id}` — оновлення звички
- `DELETE /habits/{habit_id}` — видалення звички
- `POST /habits/{habit_id}/complete` — виконання звички
- `POST /habits/{habit_id}/fail` — пропуск звички, втрата HP, можливість смерті
- `GET /habits/{habit_id}/history` — історія звички

#### `HabitRPG/backend/app/routes_users.py`

Маршрути для роботи з користувачами, їхніми нагородами, історією та аватарами.

#### `HabitRPG/backend/app/routes_admin.py`

Адмінські ендпоінти для керування користувачами та налаштуваннями, зокрема:

- отримати і змінити час відродження (`revive_timeout_sec`)
- примусово вбити чи забанити користувача
- перегляд логів та статистики

#### `HabitRPG/backend/app/scheduler.py`

Планувальник для автоматичних завдань:

- скидання щоденних/тижневих звичок
- нагороди за стрік
- відбудова таблиці лідерів
- автоматичне воскресіння померлих гравців

#### `HabitRPG/backend/database/db.py`

Підключення до SQLite та функції ініціалізації бази.

#### `HabitRPG/backend/database/seed.py`

Наповнення бази початковими тестовими даними.

### `HabitRPG/backend/bot.py`

Telegram-бот на `aiogram`:

- обробляє `/start`
- виконує режим логіну через Telegram
- зберігає токени користувачів у `bot_store.json`
- відправляє повідомлення про смерть і відродження
- має локальний HTTP-сервер `/notify` для прийому подій від бекенду
- синхронізується зі станом гравців через `GET /auth/me`

### `HabitRPG/frontend/`

Фронтенд додаток для браузера.

- `index.html` — головний UI шаблон.
- `script.js` — логіка авторизації, роботи зі звичками, станом користувача та дзвінки до API.
- `style.css` — стилі для інтерфейсу.

## Запуск

1. Встановити Python залежності:

```bash
python -m pip install -r HabitRPG/requirements.txt
```

2. Запустити FastAPI сервер:

```bash
cd HabitRPG
uvicorn backend.app.main:app --reload --port 8000
```

3. Запустити Telegram бота в іншому терміналі:

```bash
cd HabitRPG
python backend/bot.py
```

4. Відкрити фронтенд у браузері: `HabitRPG/frontend/index.html` або за допомогою локального статичного сервера.

## Налаштування

- `backend/bot.py` містить `BOT_TOKEN`.
- `backend/app/routes_auth.py` використовує `SECRET_KEY` для JWT.
- `HabitRPG/backend/app/routes_admin.py` дозволяє змінювати `DEATH_TIMEOUT_SEC` через API.

## Примітки

- При смерті гравця система зберігає стан у пам'яті (`_death_registry`) і відновлює HP після часу, заданого `DEATH_TIMEOUT_SEC`.
- Бот отримує події від бекенду через локальний `POST /notify` і додатково перевіряє стан гравця, щоб не пропустити важливі оновлення.
- Для коректної роботи бота і фронтенду сервер повинен бути доступний на `http://127.0.0.1:8000`.
