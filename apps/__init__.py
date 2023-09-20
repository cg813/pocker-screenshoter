import os

import motor.motor_asyncio
from beanie import init_beanie
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.connections import redis_cache
from apps.game.documents import Game, GamePlayer, GameRound, Merchant, Tip
from apps.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        root_path="/blackjack/api/v1"
        if os.environ.get("ENVIRONMENT") == "production"
        else ""
    )

    from apps.celery_utils import create_celery

    app.celery_app = create_celery()

    from apps.game.views import router as game_router

    app.include_router(game_router)

    from apps.game.consumers import sio_app

    app.mount("/ws/blackjack", sio_app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup_event():
        client = motor.motor_asyncio.AsyncIOMotorClient(
            os.environ.get("BLACKJACK_MONGODB_URL")
        )
        await init_beanie(
            database=client[os.environ.get("DATABASE_NAME")],
            document_models=[Game, GameRound, GamePlayer, Merchant, Tip],
        )
        await redis_cache.init_cache()

    @app.on_event("shutdown")
    async def shutdown_event():
        await redis_cache.close()

    @app.get("/health")
    async def root():
        return {"message": "success"}

    return app
