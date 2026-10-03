import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import get_settings
from app.i18n import t
from app.services.sheets import Agent, LogEntry, sheets_service

logger = logging.getLogger(__name__)


class UserContextMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        settings = get_settings()
        is_superadmin = (user.id == settings.SUPERADMIN_ID)

        agent = await sheets_service.get_agent_by_id(user.id)
        if agent:
            # If user is superadmin in settings, ensure role is superadmin and active
            if is_superadmin and (agent.role != "superadmin" or agent.status != "active"):
                agent.role = "superadmin"
                agent.status = "active"
                await sheets_service.upsert_agent(agent)

            # Auto-activate any legacy pending agent so no user remains locked out
            if agent.status == "pending":
                agent.status = "active"
                asyncio.create_task(sheets_service.upsert_agent(agent))

            data["agent"] = agent
            data["lang"] = agent.lang or "uz"
            data["role"] = agent.role
            data["status"] = agent.status
            asyncio.create_task(sheets_service.update_agent_activity(user.id))
        else:
            if is_superadmin:
                # Auto register superadmin
                agent = Agent(
                    telegram_id=user.id,
                    name=user.full_name or "SuperAdmin",
                    username=user.username or "",
                    lang="uz",
                    role="superadmin",
                    status="active",
                )
                await sheets_service.upsert_agent(agent)
                data["agent"] = agent
                data["lang"] = "uz"
                data["role"] = "superadmin"
                data["status"] = "active"
            else:
                data["agent"] = None
                data["lang"] = "uz"
                data["role"] = "guest"
                data["status"] = "unregistered"

        return await handler(event, data)


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        role = data.get("role", "guest")
        status = data.get("status", "unregistered")
        lang = data.get("lang", "uz")

        # Superadmin always has full access
        if role == "superadmin":
            return await handler(event, data)

        # Check if user is in middle of registration
        state: FSMContext = data.get("state")
        current_state = await state.get_state() if state else None
        is_registering = (
            current_state
            and current_state.startswith("RegistrationStates")
        )

        # Check if start command or registration callback
        is_start_cmd = False
        is_reg_callback = False
        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            is_start_cmd = True
        elif isinstance(event, CallbackQuery) and event.data and event.data.startswith("set_lang:"):
            is_reg_callback = True

        # Unregistered users can /start or register, or sending any message triggers registration directly
        if status == "unregistered":
            if is_start_cmd or is_reg_callback or is_registering:
                return await handler(event, data)
            if isinstance(event, Message):
                state: FSMContext = data.get("state")
                if state:
                    from app.bot.states import RegistrationStates
                    await state.set_state(RegistrationStates.waiting_for_lang)
                from app.bot.keyboards import get_language_inline_keyboard
                await event.answer(
                    t("welcome_select_lang", "uz"),
                    reply_markup=get_language_inline_keyboard(),
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("Iltimos, avval ro'yxatdan o'ting.", show_alert=True)
            return

        # Blocked users
        if status == "blocked":
            msg = t("access_blocked", lang)
            if isinstance(event, Message):
                await event.answer(msg)
            elif isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            return

        # Pending users
        if status == "pending":
            msg = t("access_pending", lang)
            if isinstance(event, Message):
                await event.answer(msg)
            elif isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            return

        return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: int = 3):
        self.rate_limit = rate_limit
        self.user_timestamps: dict[int, list[float]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        now = time.time()
        user_id = user.id
        timestamps = self.user_timestamps.get(user_id, [])

        # Keep timestamps within the last 1.0 second
        timestamps = [ts for ts in timestamps if now - ts < 1.0]

        if len(timestamps) >= self.rate_limit:
            # Drop message silently
            logger.warning(f"User {user_id} throttled (> {self.rate_limit} msg/s)")
            return

        timestamps.append(now)
        self.user_timestamps[user_id] = timestamps

        return await handler(event, data)


class ErrorHandlingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            logger.error(f"Global handler exception: {e}", exc_info=True)
            lang = data.get("lang", "uz")
            user = data.get("event_from_user")
            user_id = user.id if user else 0
            user_name = user.full_name if user else "Anon"

            try:
                await sheets_service.append_log(
                    LogEntry(
                        time=time.strftime("%Y-%m-%d %H:%M:%S"),
                        user_id=user_id,
                        user_name=user_name,
                        action="XATOLIK",
                        target="Bot Handler",
                        details=f"Xato: {str(e)[:200]}",
                    )
                )
            except Exception:
                pass

            msg = t("general_error", lang)
            if isinstance(event, Message):
                try:
                    await event.answer(msg)
                except Exception:
                    pass
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer(msg, show_alert=True)
                except Exception:
                    pass
            return None
