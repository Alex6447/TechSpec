import asyncio
import logging
from pathlib import Path

import uvicorn
from aiogram import Bot, Dispatcher
from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


_HOME_BTN = """
<style>
  #home-btn-inject {
    position: fixed; top: 20px; left: 24px; z-index: 99999;
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 16px;
    background: rgba(10,13,20,0.88);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(99,120,255,0.25);
    border-radius: 10px;
    color: #94a3b8;
    text-decoration: none;
    font-family: Inter, sans-serif;
    font-size: 0.82rem; font-weight: 500;
    transition: all 0.2s;
    letter-spacing: 0;
  }
  #home-btn-inject:hover { color: #e2e8f0; border-color: rgba(99,120,255,0.5); background: #151b2e; }
</style>
<a id="home-btn-inject" href="/">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <path d="M19 12H5M12 5l-7 7 7 7"/>
  </svg>
  На главную
</a>
"""

_COMMON_CSS = """
<style>
  body { background: #0a0d14 !important; }
  body::before {
    content: '';
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image:
      linear-gradient(rgba(99,120,255,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(99,120,255,0.04) 1px, transparent 1px);
    background-size: 40px 40px;
  }
</style>
"""


def create_app() -> FastAPI:
    app = FastAPI(
        title="B2C Telegram Bot API",
        description="Admin API and TWA endpoints for virtual card management",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
    )

    from app.routers.admin.accounts import router as admin_accounts_router

    app.include_router(admin_accounts_router, prefix="/api/v1")

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/health", response_class=HTMLResponse, include_in_schema=False)
    async def health():
        return (static_dir / "health.html").read_text(encoding="utf-8")

    @app.get("/health/json", tags=["system"])
    async def health_json():
        return {"status": "ok"}

    @app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
    async def swagger_ui():
        html = get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="API Docs — B2C Cards",
            swagger_favicon_url="/static/logo.png",
        )
        patched = html.body.decode().replace(
            "</body>", _COMMON_CSS + _HOME_BTN + "</body>"
        )
        return HTMLResponse(patched)

    @app.get("/redoc", response_class=HTMLResponse, include_in_schema=False)
    async def redoc_ui():
        html = get_redoc_html(
            openapi_url="/openapi.json",
            title="ReDoc — B2C Cards",
            redoc_favicon_url="/static/logo.png",
        )
        patched = html.body.decode().replace(
            "</body>", _COMMON_CSS + _HOME_BTN + "</body>"
        )
        return HTMLResponse(patched)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def index():
        return (static_dir / "index.html").read_text(encoding="utf-8")

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
