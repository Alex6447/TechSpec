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
  /* ── base ── */
  html, body {
    background: #0a0d14 !important;
    color: #c8d8f0 !important;
  }
  body::before {
    content: '';
    position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background-image:
      linear-gradient(rgba(99,120,255,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(99,120,255,0.04) 1px, transparent 1px);
    background-size: 40px 40px;
  }

  /* ── Swagger UI dark theme ── */
  .swagger-ui { background: transparent !important; color: #c8d8f0 !important; }

  /* top bar */
  .swagger-ui .topbar { background: #0f1320 !important; border-bottom: 1px solid rgba(99,120,255,0.2) !important; }
  .swagger-ui .topbar a { color: #a78bfa !important; }
  .swagger-ui .info .title { color: #e2e8f0 !important; }
  .swagger-ui .info p, .swagger-ui .info li,
  .swagger-ui .info a { color: #94a3b8 !important; }

  /* wrappers / panels */
  .swagger-ui .wrapper,
  .swagger-ui .scheme-container,
  .swagger-ui section.models,
  .swagger-ui .model-container,
  .swagger-ui .model-box { background: #0f1320 !important; }

  .swagger-ui .opblock-tag,
  .swagger-ui .opblock-tag-section { background: transparent !important; }
  .swagger-ui .opblock-tag { color: #a5b4fc !important; border-bottom: 1px solid rgba(99,120,255,0.18) !important; }

  /* operation blocks */
  .swagger-ui .opblock { background: #0f1320 !important; border: 1px solid rgba(99,120,255,0.18) !important; border-radius: 10px !important; margin-bottom: 6px !important; }
  .swagger-ui .opblock .opblock-summary { background: transparent !important; }
  .swagger-ui .opblock .opblock-summary-description { color: #94a3b8 !important; }
  .swagger-ui .opblock .opblock-summary-path,
  .swagger-ui .opblock .opblock-summary-path__deprecated { color: #c8d8f0 !important; }

  /* GET / POST colours */
  .swagger-ui .opblock.opblock-get   { border-color: rgba(52,211,153,0.3) !important; }
  .swagger-ui .opblock.opblock-get   .opblock-summary-method { background: rgba(52,211,153,0.2) !important; color: #34d399 !important; }
  .swagger-ui .opblock.opblock-post  { border-color: rgba(99,120,255,0.3) !important; }
  .swagger-ui .opblock.opblock-post  .opblock-summary-method { background: rgba(99,120,255,0.2) !important; color: #818cf8 !important; }
  .swagger-ui .opblock.opblock-put   { border-color: rgba(251,191,36,0.3) !important; }
  .swagger-ui .opblock.opblock-put   .opblock-summary-method { background: rgba(251,191,36,0.15) !important; color: #fbbf24 !important; }
  .swagger-ui .opblock.opblock-delete { border-color: rgba(248,113,113,0.3) !important; }
  .swagger-ui .opblock.opblock-delete .opblock-summary-method { background: rgba(248,113,113,0.15) !important; color: #f87171 !important; }

  /* expand body */
  .swagger-ui .opblock-body,
  .swagger-ui .opblock-section,
  .swagger-ui .opblock-description-wrapper { background: #0a0d14 !important; }
  .swagger-ui .tab li { color: #94a3b8 !important; }
  .swagger-ui .tab li.active { color: #a5b4fc !important; border-bottom-color: #6378ff !important; }

  /* parameters */
  .swagger-ui .parameters-col_description p,
  .swagger-ui .parameter__name,
  .swagger-ui .parameter__type,
  .swagger-ui table thead tr th { color: #94a3b8 !important; }
  .swagger-ui table tbody tr td { color: #c8d8f0 !important; border-color: rgba(99,120,255,0.12) !important; }
  .swagger-ui .parameter__in { color: #6ee7b7 !important; }

  /* inputs */
  .swagger-ui input[type=text],
  .swagger-ui input[type=password],
  .swagger-ui input[type=email],
  .swagger-ui textarea,
  .swagger-ui select {
    background: #151b2e !important;
    color: #c8d8f0 !important;
    border: 1px solid rgba(99,120,255,0.3) !important;
    border-radius: 6px !important;
  }
  .swagger-ui input::placeholder, .swagger-ui textarea::placeholder { color: #475569 !important; }

  /* buttons */
  .swagger-ui .btn { border-radius: 7px !important; }
  .swagger-ui .btn.execute { background: #6378ff !important; border-color: #6378ff !important; color: #fff !important; }
  .swagger-ui .btn.cancel  { background: transparent !important; border-color: rgba(248,113,113,0.4) !important; color: #f87171 !important; }
  .swagger-ui .btn.authorize { background: transparent !important; border-color: rgba(52,211,153,0.4) !important; color: #34d399 !important; }
  .swagger-ui .btn:hover { opacity: 0.85 !important; }

  /* responses */
  .swagger-ui .responses-inner,
  .swagger-ui .response,
  .swagger-ui .response-col_status { background: transparent !important; color: #c8d8f0 !important; }
  .swagger-ui .response-col_status { color: #34d399 !important; }
  .swagger-ui .microlight, .swagger-ui pre.microlight { background: #0f1320 !important; color: #7dd3fc !important; border-radius: 8px !important; }
  .swagger-ui .highlight-code pre { background: #0f1320 !important; color: #7dd3fc !important; }

  /* models */
  .swagger-ui .model { color: #c8d8f0 !important; }
  .swagger-ui .model-title, .swagger-ui .model-title span { color: #a5b4fc !important; }
  .swagger-ui .prop-type { color: #6ee7b7 !important; }
  .swagger-ui .prop-format { color: #94a3b8 !important; }
  .swagger-ui section.models h4 { color: #a5b4fc !important; border-color: rgba(99,120,255,0.2) !important; }
  .swagger-ui .model-box { border: 1px solid rgba(99,120,255,0.18) !important; border-radius: 8px !important; }
  .swagger-ui .prop { color: #7dd3fc !important; }

  /* authorize modal */
  .swagger-ui .dialog-ux .modal-ux { background: #0f1320 !important; border: 1px solid rgba(99,120,255,0.25) !important; border-radius: 14px !important; }
  .swagger-ui .dialog-ux .modal-ux-header { background: #0f1320 !important; border-bottom: 1px solid rgba(99,120,255,0.2) !important; }
  .swagger-ui .dialog-ux .modal-ux-header h3 { color: #e2e8f0 !important; }
  .swagger-ui .auth-container label, .swagger-ui .auth-container p { color: #94a3b8 !important; }

  /* misc text */
  .swagger-ui .renderedMarkdown p { color: #94a3b8 !important; }
  .swagger-ui .opblock-section-header { background: #0f1320 !important; border-bottom: 1px solid rgba(99,120,255,0.12) !important; }
  .swagger-ui .opblock-section-header label, .swagger-ui .opblock-section-header h4 { color: #94a3b8 !important; }
  .swagger-ui svg { fill: #64748b !important; }
  .swagger-ui .arrow { fill: #64748b !important; }

  /* ── ReDoc dark theme ── */
  redoc-ui, [data-role="search-input"],
  .redoc-wrap { background: #0a0d14 !important; color: #c8d8f0 !important; }

  /* sidebar */
  .menu-content { background: #0f1320 !important; }
  .menu-content * { color: #94a3b8 !important; }
  .menu-content a:hover, .menu-content li.active > label { color: #a5b4fc !important; }
  .scrollbar-width { background: #0f1320 !important; }

  /* main content panels */
  [role="main"] { background: #0a0d14 !important; color: #c8d8f0 !important; }

  /* operation titles, text */
  h1, h2, h3, h4, h5 { color: #e2e8f0 !important; }
  p, li, td, th { color: #94a3b8 !important; }
  a { color: #818cf8 !important; }
  code { background: #151b2e !important; color: #7dd3fc !important; border-radius: 4px !important; }
  pre { background: #0f1320 !important; color: #7dd3fc !important; border-radius: 8px !important; border: 1px solid rgba(99,120,255,0.15) !important; }

  /* ReDoc API method labels */
  span[type="get"]    { background: rgba(52,211,153,0.18) !important; color: #34d399 !important; }
  span[type="post"]   { background: rgba(99,120,255,0.18) !important; color: #818cf8 !important; }
  span[type="put"]    { background: rgba(251,191,36,0.15) !important; color: #fbbf24 !important; }
  span[type="delete"] { background: rgba(248,113,113,0.15) !important; color: #f87171 !important; }
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
