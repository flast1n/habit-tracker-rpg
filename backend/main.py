import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from database import init_db, seed_fake_data
from app.routes_users import router as users_router
from app.routes_habits import router as habits_router

app = FastAPI(
    title="HabitRPG API",
    description="Бекенд для трекера звичок із елементами гейміфікації",
    version="0.1.0",
)

app.include_router(users_router)
app.include_router(habits_router)


@app.on_event("startup")
def on_startup():
    init_db()
    seed_fake_data()


@app.get("/")
def root():
    return {
        "project": "HabitRPG",
        "status":  "running",
        "docs":    "/docs",
    }
