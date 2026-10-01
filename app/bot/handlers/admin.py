from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings
from app.services.backup import run_backup_job
from app.services.notify import send_daily_report
from app.services.sheets import sheets_service

router = Router(name="admin_router")


@router.message(Command("agents"))
async def cmd_agents(message: Message, role: str):
    if role not in ("admin", "superadmin"):
        return

    agents = await sheets_service.get_agents()
    if not agents:
        await message.answer("Hech qanday agent topilmadi.")
        return

    active_agents = []
    pending_agents = []
    blocked_agents = []

    for a in agents.values():
        info = f"• <b>{a.name}</b> (<code>{a.telegram_id}</code>) - {a.phone} [{a.role}]"
        if a.status == "active":
            active_agents.append(info)
        elif a.status == "pending":
            pending_agents.append(info)
        elif a.status == "blocked":
            blocked_agents.append(info)

    text_parts = ["👥 <b>Agentlar ro'yxati:</b>\n"]
    if active_agents:
        text_parts.append(f"<b>✅ Faol ({len(active_agents)}):</b>\n" + "\n".join(active_agents))
    if pending_agents:
        text_parts.append(f"\n<b>⏳ Kutilmoqda ({len(pending_agents)}):</b>\n" + "\n".join(pending_agents))
    if blocked_agents:
        text_parts.append(f"\n<b>🚫 Bloklangan ({len(blocked_agents)}):</b>\n" + "\n".join(blocked_agents))

    full_text = "\n".join(text_parts)
    if len(full_text) > 4000:
        for i in range(0, len(full_text), 4000):
            await message.answer(full_text[i : i + 4000], parse_mode="HTML")
    else:
        await message.answer(full_text, parse_mode="HTML")


@router.message(Command("block"))
async def cmd_block(message: Message, role: str):
    if role not in ("admin", "superadmin"):
        return

    settings = get_settings()
    args = (message.text or "").split()
    if len(args) < 2:
        await message.answer("Foydalanish: <code>/block &lt;telegram_id&gt;</code>", parse_mode="HTML")
        return

    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("Noto'g'ri Telegram ID!")
        return

    if target_id == settings.SUPERADMIN_ID:
        await message.answer("Superadminni bloklab bo'lmaydi!")
        return
    if target_id == message.from_user.id:
        await message.answer("O'zingizni bloklay olmaysiz!")
        return

    agent = await sheets_service.get_agent_by_id(target_id)
    if not agent:
        await message.answer(f"ID {target_id} bo'lgan agent topilmadi.")
        return

    admin_name = message.from_user.full_name or "Admin"
    await sheets_service.set_agent_status(
        telegram_id=target_id,
        status="blocked",
        admin_id=message.from_user.id,
        admin_name=admin_name,
    )
    await message.answer(f"Agent {agent.name} (<code>{target_id}</code>) bloklandi.", parse_mode="HTML")

    try:
        await message.bot.send_message(
            chat_id=target_id,
            text="Sizning hisobingiz admin tomonidan bloklandi.",
        )
    except Exception:
        pass


@router.message(Command("unblock"))
async def cmd_unblock(message: Message, role: str):
    if role not in ("admin", "superadmin"):
        return

    args = (message.text or "").split()
    if len(args) < 2:
        await message.answer("Foydalanish: <code>/unblock &lt;telegram_id&gt;</code>", parse_mode="HTML")
        return

    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("Noto'g'ri Telegram ID!")
        return

    agent = await sheets_service.get_agent_by_id(target_id)
    if not agent:
        await message.answer(f"ID {target_id} bo'lgan agent topilmadi.")
        return

    admin_name = message.from_user.full_name or "Admin"
    await sheets_service.set_agent_status(
        telegram_id=target_id,
        status="active",
        admin_id=message.from_user.id,
        admin_name=admin_name,
    )
    await message.answer(f"Agent {agent.name} (<code>{target_id}</code>) blokdan chiqarildi.", parse_mode="HTML")

    try:
        await message.bot.send_message(
            chat_id=target_id,
            text="Sizning hisobingiz blokdan chiqarildi va faollashtirildi.",
        )
    except Exception:
        pass


@router.message(Command("addadmin"))
async def cmd_addadmin(message: Message):
    settings = get_settings()
    if message.from_user.id != settings.SUPERADMIN_ID:
        await message.answer("Bu buyruq faqat Superadmin uchun!")
        return

    args = (message.text or "").split()
    if len(args) < 2:
        await message.answer("Foydalanish: <code>/addadmin &lt;telegram_id&gt;</code>", parse_mode="HTML")
        return

    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("Noto'g'ri Telegram ID!")
        return

    agent = await sheets_service.get_agent_by_id(target_id)
    if not agent:
        await message.answer(f"ID {target_id} bo'lgan foydalanuvchi Agentlar varag'ida topilmadi.")
        return

    admin_name = message.from_user.full_name or "Superadmin"
    await sheets_service.set_agent_role(
        telegram_id=target_id,
        role="admin",
        admin_id=message.from_user.id,
        admin_name=admin_name,
    )
    await message.answer(f"Foydalanuvchi {agent.name} (<code>{target_id}</code>) admin etib tayinlandi!", parse_mode="HTML")

    try:
        await message.bot.send_message(
            chat_id=target_id,
            text="Sizga administrator huquqi berildi! /start bosing.",
        )
    except Exception:
        pass


@router.message(Command("removeadmin"))
async def cmd_removeadmin(message: Message):
    settings = get_settings()
    if message.from_user.id != settings.SUPERADMIN_ID:
        await message.answer("Bu buyruq faqat Superadmin uchun!")
        return

    args = (message.text or "").split()
    if len(args) < 2:
        await message.answer("Foydalanish: <code>/removeadmin &lt;telegram_id&gt;</code>", parse_mode="HTML")
        return

    try:
        target_id = int(args[1])
    except ValueError:
        await message.answer("Noto'g'ri Telegram ID!")
        return

    if target_id == settings.SUPERADMIN_ID:
        await message.answer("Superadminni o'zidan admin huquqini olib bo'lmaydi!")
        return

    agent = await sheets_service.get_agent_by_id(target_id)
    if not agent:
        await message.answer(f"ID {target_id} bo'lgan foydalanuvchi topilmadi.")
        return

    admin_name = message.from_user.full_name or "Superadmin"
    await sheets_service.set_agent_role(
        telegram_id=target_id,
        role="agent",
        admin_id=message.from_user.id,
        admin_name=admin_name,
    )
    await message.answer(f"Foydalanuvchi {agent.name} (<code>{target_id}</code>) adminlikdan olindi (agent qilindi).", parse_mode="HTML")


@router.message(Command("setgroup"))
async def cmd_setgroup(message: Message):
    settings = get_settings()
    if message.from_user.id != settings.SUPERADMIN_ID:
        await message.answer("Bu buyruq faqat Superadmin uchun!")
        return

    chat_id = str(message.chat.id)
    await sheets_service.set_setting("admin_group_id", chat_id)
    await message.answer(f"✅ Ushbu guruh (ID: <code>{chat_id}</code>) bildirishnomalar uchun admin guruhi sifatida saqlandi!", parse_mode="HTML")


@router.message(Command("report_now"))
async def cmd_report_now(message: Message):
    settings = get_settings()
    if message.from_user.id != settings.SUPERADMIN_ID:
        return

    await message.answer("⏳ Kunlik hisobot tuzilmoqda va yuborilmoqda...")
    success = await send_daily_report(message.bot, force=True)
    if success:
        await message.answer("✅ Kunlik hisobot barcha adminlarga yuborildi!")
    else:
        await message.answer("Hisobot yuborishda muammo yuz berdi.")


@router.message(Command("backup_now"))
async def cmd_backup_now(message: Message):
    settings = get_settings()
    if message.from_user.id != settings.SUPERADMIN_ID:
        return

    await message.answer("⏳ Spreadsheet zaxira nusxasi olinmoqda...")
    success = await run_backup_job(message.bot)
    if success:
        await message.answer("✅ Zaxira nusxasi muvaffaqiyatli 'Zaxira/' papkasiga olindi!")
    else:
        await message.answer("❌ Zaxira olishda xatolik yuz berdi.")
