from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from app.bot.handlers import admin, common, my_records, registration, start, stats, store_flow
from app.bot.middlewares import (
    AccessMiddleware,
    ErrorHandlingMiddleware,
    ThrottleMiddleware,
    UserContextMiddleware,
)
from app.config import get_settings


def create_bot_and_dispatcher() -> tuple[Bot, Dispatcher]:
    settings = get_settings()

    # Bot instance
    bot = Bot(token=settings.BOT_TOKEN)

    # Storage
    if settings.REDIS_URL:
        try:
            from aiogram.fsm.storage.redis import RedisStorage
            storage = RedisStorage.from_url(settings.REDIS_URL)
        except Exception:
            storage = MemoryStorage()
    else:
        storage = MemoryStorage()

    dp = Dispatcher(storage=storage)

    # Middlewares
    dp.update.outer_middleware(ThrottleMiddleware(rate_limit=3))
    dp.update.outer_middleware(ErrorHandlingMiddleware())
    dp.update.middleware(UserContextMiddleware())
    dp.update.middleware(AccessMiddleware())

    # Routers (order matters)
    dp.include_router(common.router)
    dp.include_router(start.router)
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(store_flow.router)
    dp.include_router(my_records.router)
    dp.include_router(stats.router)

    return bot, dp
