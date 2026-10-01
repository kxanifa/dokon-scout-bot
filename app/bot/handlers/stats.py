from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.i18n import t
from app.services.sheets import Agent
from app.services.stats import get_agent_stats, get_top_ranking

router = Router(name="stats_router")


def get_top_period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📅 Bugun", callback_data="top_period:day"),
                InlineKeyboardButton(text="📆 Shu hafta", callback_data="top_period:week"),
                InlineKeyboardButton(text="🗓 Shu oy", callback_data="top_period:month"),
            ]
        ]
    )


@router.message(Command("stats"))
@router.message(F.text.in_(["📊 Statistikam", "📊 Статистикам", "📊 Моя статистика"]))
async def cmd_my_stats(message: Message, agent: Agent, lang: str):
    daily_plan = agent.daily_plan if agent else 20
    stats = await get_agent_stats(message.from_user.id, daily_plan=daily_plan)

    text = t(
        "stats_title",
        lang,
        today=stats["today"],
        daily_plan=stats["daily_plan"],
        percent=stats["percent"],
        progress_bar=stats["progress_bar"],
        week=stats["week"],
        month=stats["month"],
        total=stats["total"],
        visits=stats["visits"],
    )
    await message.answer(text)


@router.message(Command("top"))
async def cmd_top(message: Message, lang: str):
    data = await get_top_ranking(period="day", my_agent_id=message.from_user.id)
    text = t(
        "top_rating_title",
        lang,
        period=data["period"],
        ranking=data["ranking_text"],
        my_rank=data["my_rank"],
        my_count=data["my_count"],
    )
    await message.answer(text, reply_markup=get_top_period_keyboard())


@router.callback_query(F.data.startswith("top_period:"))
async def callback_top_period(callback: CallbackQuery, lang: str):
    period = callback.data.split(":")[1]
    data = await get_top_ranking(period=period, my_agent_id=callback.from_user.id)
    text = t(
        "top_rating_title",
        lang,
        period=data["period"],
        ranking=data["ranking_text"],
        my_rank=data["my_rank"],
        my_count=data["my_count"],
    )
    try:
        await callback.message.edit_text(text, reply_markup=get_top_period_keyboard())
    except Exception:
        pass
    await callback.answer()
