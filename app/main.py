import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from fastapi import FastAPI

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="B2C Telegram Bot API",
        description="Admin API and TWA endpoints for virtual card management",
        version="1.0.0",
    )

    from app.routers.admin.accounts import router as admin_accounts_router

    app.include_router(admin_accounts_router, prefix="/api/v1")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


async def start_bot(bot: Bot, dp: Dispatcher) -> None:
    logger.info("Starting Telegram bot (long polling)...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def main() -> None:
    from app.bot.setup import create_dispatcher

    bot = Bot(token=settings.telegram_bot_token)
    dp = create_dispatcher()

    fastapi_app = create_app()

    config = uvicorn.Config(
        app=fastapi_app,
        host=settings.app_host,
        port=settings.app_port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    await asyncio.gather(
        server.serve(),
        start_bot(bot, dp),
    )


if __name__ == "__main__":
    asyncio.run(main())
