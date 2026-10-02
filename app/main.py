import asyncio
import logging
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

from aiogram.types import Update
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.bot.dispatcher import create_bot_and_dispatcher
from app.config import get_settings
from app.services.backup import run_backup_job
from app.services.notify import send_daily_report
from app.services.sheets import get_current_tashkent_time, sheets_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app.main")

# Global instances
bot, dp = create_bot_and_dispatcher()
scheduler = AsyncIOScheduler(timezone=ZoneInfo("Asia/Tashkent"))


async def scheduled_daily_report_checker():
    """
    Checks every minute if the daily report should be sent based on
    dynamic report_time in Sozlamalar and Tashkent current time.
    Handles wake-up catch-up after sleep.
    """
    try:
        now = get_current_tashkent_time()
        current_time_str = now.strftime("%H:%M")
        report_time = await sheets_service.get_setting("report_time", "21:00")

        if current_time_str >= report_time:
            await send_daily_report(bot, force=False)
    except Exception as e:
        logger.error(f"Error in scheduled daily report checker: {e}")


async def scheduled_weekly_backup():
    """Runs weekly spreadsheet backup on Sundays at 03:00."""
    try:
        logger.info("Rejali haftalik zaxira nusxasi olinmoqda...")
        await run_backup_job(bot)
    except Exception as e:
        logger.error(f"Error in scheduled weekly backup: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Ilova ishga tushmoqda...")

    # Start sequential background write worker for Google Sheets
    sheets_service.start_worker()
    asyncio.create_task(sheets_service.warm_cache())

    # Start APScheduler jobs
    scheduler.add_job(
        scheduled_daily_report_checker,
        "interval",
        minutes=1,
        id="daily_report_checker",
        replace_existing=True,
    )
    scheduler.add_job(
        scheduled_weekly_backup,
        "cron",
        day_of_week="sun",
        hour=3,
        minute=0,
        id="weekly_backup",
        replace_existing=True,
    )
    scheduler.start()

    # Configure Telegram Webhook if real token and public url provided
    if (
        settings.BOT_TOKEN
        and not settings.BOT_TOKEN.startswith("1234567890:ABCDefGh")
        and settings.PUBLIC_BASE_URL
        and "example.com" not in settings.PUBLIC_BASE_URL
    ):
        webhook_url = f"{settings.PUBLIC_BASE_URL.rstrip('/')}/tg/webhook"
        try:
            logger.info(f"Setting Telegram webhook to: {webhook_url}")
            await bot.set_webhook(
                url=webhook_url,
                secret_token=settings.WEBHOOK_SECRET,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query"],
            )
        except Exception as e:
            logger.warning(f"Webhook o'rnatishda xatolik (bu lokal/mock muhitda normal): {e}")

    yield

    logger.info("Ilova to'xtatilmoqda...")
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
    try:
        await bot.session.close()
    except Exception:
        pass
    await sheets_service.stop_worker()


app = FastAPI(
    title="Dokon Scout API",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount API routes
app.include_router(api_router)

# Mount WebApp Static files at /app
app.mount("/app", StaticFiles(directory="app/webapp", html=True), name="webapp")


@app.get("/")
async def root():
    """Redirect root to Mini App."""
    return RedirectResponse(url="/app")


@app.get("/healthz")
async def healthz():
    """Liveness probe for Render and monitoring (does not touch Google Sheets)."""
    return {"ok": True}


@app.post("/tg/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
):
    """Telegram webhook handler with secret token verification."""
    settings = get_settings()
    if settings.WEBHOOK_SECRET and x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        logger.warning("Webhook so'rovi rad etildi: noto'g'ri secret token")
        raise HTTPException(status_code=403, detail="Invalid secret token")

    data = await request.json()
    update = Update.model_validate(data, context={"bot": bot})
    await dp.feed_update(bot=bot, update=update)
    return {"ok": True}
