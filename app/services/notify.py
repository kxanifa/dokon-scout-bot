import logging

from aiogram import Bot

from app.config import get_settings
from app.services.sheets import (
    Agent,
    Store,
    Visit,
    get_current_tashkent_time,
    normalize_date_str,
    sheets_service,
)

logger = logging.getLogger(__name__)


async def notify_new_store_saved(bot: Bot, store: Store) -> None:
    """Send notification to admin group or admins when a new store is saved."""
    try:
        notify_enabled = await sheets_service.get_setting("notify_new_store", "1")
        if notify_enabled != "1":
            return

        settings = get_settings()
        admin_group_id_str = await sheets_service.get_setting("admin_group_id", "")
        admin_group_id = int(admin_group_id_str) if admin_group_id_str else settings.ADMIN_GROUP_ID

        caption = (
            f"🔔 <b>Yangi do'kon qo'shildi! №{store.id}</b>\n\n"
            f"🏪 <b>Nomi:</b> {store.name}\n"
            f"🔢 <b>INN:</b> {store.inn}\n"
            f"📞 <b>Tel:</b> {store.phone or 'Kiritilmagan'}\n"
            f"📍 <b>Hudud:</b> {store.state}, {store.district}, {store.mahalla}\n"
            f"👤 <b>Agent:</b> {store.agent_name} (<code>{store.agent_id}</code>)\n"
            f"🕒 <b>Vaqt:</b> {store.date} {store.time}\n"
            f"🗺 <a href=\"https://www.google.com/maps?q={store.lat},{store.lon}\">Google Maps'da ochish</a>"
        )

        destinations = []
        if admin_group_id:
            destinations.append(admin_group_id)
        else:
            agents = await sheets_service.get_agents()
            for ag in agents.values():
                if ag.role in ("admin", "superadmin") and ag.status == "active":
                    destinations.append(ag.telegram_id)
            if settings.SUPERADMIN_ID and settings.SUPERADMIN_ID not in destinations:
                destinations.append(settings.SUPERADMIN_ID)

        for chat_id in set(destinations):
            try:
                if store.photo1_id:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=store.photo1_id,
                        caption=caption,
                        parse_mode="HTML",
                    )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=caption,
                        parse_mode="HTML",
                    )
            except Exception as e:
                logger.warning(f"Failed to send notification to chat {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Error in notify_new_store_saved: {e}", exc_info=True)


async def notify_new_visit_saved(bot: Bot, visit: Visit, store_name: str) -> None:
    """Send notification when a revisit is saved."""
    try:
        notify_enabled = await sheets_service.get_setting("notify_new_store", "1")
        if notify_enabled != "1":
            return

        settings = get_settings()
        admin_group_id_str = await sheets_service.get_setting("admin_group_id", "")
        admin_group_id = int(admin_group_id_str) if admin_group_id_str else settings.ADMIN_GROUP_ID

        caption = (
            f"🔁 <b>Qayta tashrif qayd etildi! №{visit.id}</b>\n\n"
            f"🏪 <b>Do'kon:</b> {store_name} (ID: #{visit.store_id})\n"
            f"👤 <b>Agent:</b> {visit.agent_name} (<code>{visit.agent_id}</code>)\n"
            f"🕒 <b>Vaqt:</b> {visit.date} {visit.time}\n"
            f"🗺 <a href=\"https://www.google.com/maps?q={visit.lat},{visit.lon}\">Google Maps'da ochish</a>"
        )

        destinations = []
        if admin_group_id:
            destinations.append(admin_group_id)
        else:
            agents = await sheets_service.get_agents()
            for ag in agents.values():
                if ag.role in ("admin", "superadmin") and ag.status == "active":
                    destinations.append(ag.telegram_id)
            if settings.SUPERADMIN_ID and settings.SUPERADMIN_ID not in destinations:
                destinations.append(settings.SUPERADMIN_ID)

        for chat_id in set(destinations):
            try:
                if visit.photo1_id:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=visit.photo1_id,
                        caption=caption,
                        parse_mode="HTML",
                    )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=caption,
                        parse_mode="HTML",
                    )
            except Exception as e:
                logger.warning(f"Failed to send visit notification to chat {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Error in notify_new_visit_saved: {e}", exc_info=True)


# In-memory guard to prevent duplicate executions within the same day/process
_last_sent_report_date: str | None = None


async def send_daily_report(bot: Bot, force: bool = False) -> bool:
    """
    Compile and deliver the end-of-day summary report to all active admins.
    Prevents sending duplicate reports on the same calendar day unless force=True.
    """
    global _last_sent_report_date
    now = get_current_tashkent_time()
    today_str = now.strftime("%Y-%m-%d")

    # In-memory fast guard
    if _last_sent_report_date == today_str and not force:
        logger.info(f"Bugungi ({today_str}) hisobot in-memory tekshiruvi bo'yicha allaqachon yuborilgan.")
        return False

    # Prevent duplicate daily report via Google Sheets setting
    raw_last_report_date = await sheets_service.get_setting("last_report_date", "")
    last_report_date = normalize_date_str(raw_last_report_date)
    if last_report_date == today_str and not force:
        _last_sent_report_date = today_str
        logger.info(f"Bugungi ({today_str}) hisobot allaqachon yuborilgan.")
        return False

    stores = await sheets_service.get_stores(include_deleted=False)
    visits = await sheets_service.get_visits()
    agents = await sheets_service.get_agents()

    today_stores = [s for s in stores if s.date == today_str]
    today_visits = [v for v in visits if v.date == today_str]

    # Calculate agent breakdown
    agent_counts: dict[int, int] = {}
    for s in today_stores:
        agent_counts[s.agent_id] = agent_counts.get(s.agent_id, 0) + 1

    active_agents = [ag for ag in agents.values() if ag.status == "active" and ag.role == "agent"]
    total_active_agents_count = len(active_agents)

    idle_agents_count = sum(1 for ag in active_agents if agent_counts.get(ag.telegram_id, 0) == 0)

    # Sorted list of agent performances
    sorted_agents = sorted(
        active_agents,
        key=lambda ag: agent_counts.get(ag.telegram_id, 0),
        reverse=True,
    )

    best_agent_name = "Yo'q"
    if sorted_agents and agent_counts.get(sorted_agents[0].telegram_id, 0) > 0:
        top_ag = sorted_agents[0]
        best_agent_name = f"{top_ag.name} ({agent_counts[top_ag.telegram_id]} ta)"

    agent_lines_uz = []
    agent_lines_uz_cyr = []
    agent_lines_ru = []

    for idx, ag in enumerate(sorted_agents, start=1):
        cnt = agent_counts.get(ag.telegram_id, 0)
        plan = ag.daily_plan or 20
        pct = int((cnt / plan) * 100) if plan > 0 else 0
        medal = "🥇 " if idx == 1 and cnt > 0 else "• "

        agent_lines_uz.append(f"{medal}{ag.name}: <b>{cnt}/{plan} ta</b> ({pct}%)")
        agent_lines_uz_cyr.append(f"{medal}{ag.name}: <b>{cnt}/{plan} та</b> ({pct}%)")
        agent_lines_ru.append(f"{medal}{ag.name}: <b>{cnt}/{plan} шт.</b> ({pct}%)")

    agents_list_uz = "\n".join(agent_lines_uz) if agent_lines_uz else "Agentlar topilmadi."
    agents_list_uz_cyr = "\n".join(agent_lines_uz_cyr) if agent_lines_uz_cyr else "Агентлар топилмади."
    agents_list_ru = "\n".join(agent_lines_ru) if agent_lines_ru else "Агенты не найдены."

    report_texts = {
        "uz": (
            f"📊 <b>Kunlik hisobot ({today_str})</b>\n\n"
            f"🏪 Yangi do'konlar: <b>{len(today_stores)} ta</b>\n"
            f"🔁 Qayta tashriflar: <b>{len(today_visits)} ta</b>\n"
            f"🏆 Kun qahramoni: <b>{best_agent_name}</b>\n"
            f"👥 Faol agentlar: <b>{total_active_agents_count} ta</b> (Ish qilmaganlar: {idle_agents_count})\n\n"
            f"<b>Agentlar natijasi:</b>\n{agents_list_uz}"
        ),
        "uz_cyr": (
            f"📊 <b>Кунлик ҳисобот ({today_str})</b>\n\n"
            f"🏪 Янги дўконлар: <b>{len(today_stores)} та</b>\n"
            f"🔁 Қайта ташрифлар: <b>{len(today_visits)} та</b>\n"
            f"🏆 Кун қаҳрамони: <b>{best_agent_name}</b>\n"
            f"👥 Фаол агентлар: <b>{total_active_agents_count} та</b> (Иш қилмаганлар: {idle_agents_count})\n\n"
            f"<b>Агентлар натижаси:</b>\n{agents_list_uz_cyr}"
        ),
        "ru": (
            f"📊 <b>Ежедневный отчет ({today_str})</b>\n\n"
            f"🏪 Новых магазинов: <b>{len(today_stores)} шт.</b>\n"
            f"🔁 Повторных визитов: <b>{len(today_visits)} шт.</b>\n"
            f"🏆 Лучший агент: <b>{best_agent_name}</b>\n"
            f"👥 Активных агентов: <b>{total_active_agents_count}</b> (Не работали сегодня: {idle_agents_count})\n\n"
            f"<b>Результаты агентов:</b>\n{agents_list_ru}"
        ),
    }

    settings = get_settings()
    admin_targets = []
    for ag in agents.values():
        if ag.role in ("admin", "superadmin") and ag.status == "active":
            admin_targets.append(ag)

    # Ensure superadmin is included even if not in agent list
    if settings.SUPERADMIN_ID and not any(a.telegram_id == settings.SUPERADMIN_ID for a in admin_targets):
        admin_targets.append(Agent(telegram_id=settings.SUPERADMIN_ID, name="SuperAdmin", lang="uz"))

    for admin in admin_targets:
        lang = admin.lang if admin.lang in report_texts else "uz"
        text = report_texts[lang]
        try:
            await bot.send_message(
                chat_id=admin.telegram_id,
                text=text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Failed to send daily report to admin {admin.telegram_id}: {e}")

    # Mark report as sent for today
    _last_sent_report_date = today_str
    await sheets_service.set_setting("last_report_date", today_str)
    logger.info(f"Kunlik hisobot ({today_str}) muvaffaqiyatli yuborildi.")
    return True
