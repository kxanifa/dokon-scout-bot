from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from app.config import get_settings
from app.i18n import t
from app.services.sheets import Agent, get_current_tashkent_time, sheets_service
from app.services.stats import get_top_ranking

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
@router.message(F.text.in_(["📊 Statistika", "📊 Statistikam", "📊 Статистика", "📊 Статистикам", "📊 Моя статистика"]))
async def cmd_stats(message: Message, role: str, lang: str, agent: Agent | None = None):
    # Only superadmin (and authorized admin) can view system-wide statistics
    if role not in ("admin", "superadmin"):
        await message.answer(t("only_admin_stats", lang))
        return

    stores = await sheets_service.get_stores(include_deleted=False)
    visits = await sheets_service.get_visits()
    agents = await sheets_service.get_agents()

    now = get_current_tashkent_time()
    today_str = now.strftime("%Y-%m-%d")

    today_stores = [s for s in stores if s.date == today_str]
    today_visits = [v for v in visits if v.date == today_str]
    active_agents = [a for a in agents.values() if a.status == "active" and a.role == "agent"]

    agent_counts: dict[int, int] = {}
    for s in today_stores:
        agent_counts[s.agent_id] = agent_counts.get(s.agent_id, 0) + 1

    best_agent_name = "Hali yo'q"
    if active_agents and agent_counts:
        top_aid = max(agent_counts, key=agent_counts.get)
        top_ag = agents.get(top_aid)
        if top_ag:
            best_agent_name = f"{top_ag.name} ({agent_counts[top_aid]} ta)"

    settings = get_settings()
    base_url = settings.PUBLIC_BASE_URL.rstrip("/")
    webapp_url = f"{base_url}/app"

    text = (
        f"📊 <b>Umumiy Tizim Statistikasi ({today_str})</b>\n\n"
        f"🏪 <b>Bugungi yangi do'konlar:</b> {len(today_stores)} ta\n"
        f"🔁 <b>Bugungi qayta tashriflar:</b> {len(today_visits)} ta\n"
        f"🏪 <b>Jami barcha do'konlar:</b> {len(stores)} ta\n"
        f"👥 <b>Faol agentlar:</b> {len(active_agents)} ta\n"
        f"🏆 <b>Bugungi eng faol agent:</b> {best_agent_name}\n\n"
        f"<i>Batafsil xarita, agentlar faolligi va hisobotlar uchun Mini App boshqaruv panelidan foydalanishingiz mumkin.</i>"
    )

    kb_buttons = []
    if webapp_url and "example.com" not in webapp_url and webapp_url.startswith("https://"):
        kb_buttons.append([
            InlineKeyboardButton(
                text="📊 Mini App Boshqaruv Paneli",
                web_app=WebAppInfo(url=webapp_url),
            )
        ])
    kb_buttons.append([
        InlineKeyboardButton(
            text="🏆 Agentlar reytingi (/top)",
            callback_data="top_period:day",
        )
    ])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_buttons), parse_mode="HTML")


@router.message(Command("top"))
async def cmd_top(message: Message, role: str, lang: str):
    if role not in ("admin", "superadmin"):
        await message.answer(t("only_admin_stats", lang))
        return

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
async def callback_top_period(callback: CallbackQuery, role: str, lang: str):
    if role not in ("admin", "superadmin"):
        await callback.answer(t("only_admin_stats", lang), show_alert=True)
        return

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
