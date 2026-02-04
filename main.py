from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from api.users import router as user_router
from api.calendars import router as calendar_router
from api.auth import router as auth_router
from api.events import router as event_router

from ui.start import print_start_message, print_end_message


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(set)
    from core.database import init_db
    from models import calendar, calendar_user, user, event
    await init_db()
    print_start_message()
    yield
    print_end_message()
    

# App
app = FastAPI(lifespan=lifespan)

# Include router
app.include_router(user_router)
app.include_router(auth_router)
app.include_router(calendar_router)
app.include_router(event_router)


# CORS middleware (for correct work with friontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:3000",
        "http://192.168.0.9:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get('/ping')
async def main_page():
    return {'message': 'pong'}
