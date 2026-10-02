"""
scripts/run_polling.py
Lokal muhitda botni Telegram Webhook sozlamasdan, Long Polling rejimida
tez va oson sinash uchun yordamchi skript.
"""

import asyncio
import logging
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Loyiha ildizini sys.path ga qo'shish
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.bot.dispatcher import create_bot_and_dispatcher
from app.config import get_settings
from app.services.sheets import sheets_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_polling")


async def main():
    settings = get_settings()

    if not settings.BOT_TOKEN or settings.BOT_TOKEN.startswith("1234567890:"):
        print("\n" + "=" * 60)
        print("❌ XATOLIK: BOT_TOKEN sozlanmagan!")
        print("=" * 60)
        print("Iltimos, .env faylida o'zingizning @BotFather bergan haqiqiy")
        print("BOT_TOKEN qiymatini kiriting.")
        print("=" * 60 + "\n")
        sys.exit(1)

    bot, dp = create_bot_and_dispatcher()

    logger.info("Google Sheets fon xizmati (worker) ishga tushmoqda...")
    sheets_service.start_worker()
    logger.info("Google Sheets keshi xotiraga yuklanmoqda (pre-warming)...")
    await sheets_service.warm_cache()

    logger.info("Eski webhook o'chirilmoqda va kutilayotgan xabarlar tozalanmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)

    bot_info = await bot.get_me()
    print("\n" + "=" * 60)
    print(f"✅ Bot muvaffaqiyatli ishga tushdi: @{bot_info.username} ({bot_info.first_name})")
    print("Bot xabarlarni qabul qilishga tayyor! To'xtatish uchun CTRL+C bosing.")
    print("=" * 60 + "\n")

    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Bot to'xtatilmoqda...")
        await sheets_service.stop_worker()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Bot to'xtatildi.")
