import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db, seed_fake_data
from app.routes_users  import router as users_router
from app.routes_habits import router as habits_router
from app.routes_auth   import router as auth_router
from app.routes_admin  import router as admin_router
from app.scheduler     import start_scheduler

app = FastAPI(
    title       = "HabitRPG API",
    description = "Трекер звичок з гейміфікацією — v2",
    version     = "2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# роутери
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(habits_router)
app.include_router(admin_router)


@app.on_event("startup")
def on_startup():
    init_db()
    seed_fake_data()
    start_scheduler()


@app.get("/")
def root():
    return {
        "project": "HabitRPG",
        "version": "2.0.0",
        "status":  "running 🐉",
        "docs":    "/docs",
    }


@app.get("/health")
def health():
    try:
        from database import get_connection
        users = get_connection().execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return {"status": "ok", "users": users}
    except Exception as e:
        return {"status": "error", "detail": str(e)}
