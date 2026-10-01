import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.bot.keyboards import get_admin_approval_keyboard, get_contact_keyboard, get_main_menu
from app.bot.states import RegistrationStates
from app.config import get_settings
from app.i18n import t
from app.services.sheets import Agent, sheets_service

logger = logging.getLogger(__name__)
router = Router(name="registration_router")


@router.message(RegistrationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("chosen_lang", "uz")

    name = (message.text or "").strip()
    if len(name) < 2 or len(name) > 60:
        await message.answer(t("invalid_name", lang))
        return

    await state.update_data(full_name=name)
    await state.set_state(RegistrationStates.waiting_for_contact)
    await message.answer(
        t("ask_contact", lang),
        reply_markup=get_contact_keyboard(lang),
    )


@router.message(RegistrationStates.waiting_for_contact, F.contact)
async def process_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("chosen_lang", "uz")
    full_name = data.get("full_name", message.from_user.full_name)

    contact = message.contact
    if not contact or contact.user_id != message.from_user.id:
        await message.answer(t("invalid_contact", lang))
        return

    phone = contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    user = message.from_user
    new_agent = Agent(
        telegram_id=user.id,
        name=full_name,
        phone=phone,
        username=user.username or "",
        lang=lang,
        role="agent",
        status="pending",
    )

    await sheets_service.upsert_agent(new_agent)
    await state.clear()

    await message.answer(
        t("reg_pending", lang),
        reply_markup=ReplyKeyboardRemove(),
    )

    # Notify all active admins and superadmin
    settings = get_settings()
    agents = await sheets_service.get_agents()
    admin_ids = {settings.SUPERADMIN_ID}
    for ag in agents.values():
        if ag.role in ("admin", "superadmin") and ag.status == "active":
            admin_ids.add(ag.telegram_id)

    notify_text = t(
        "admin_new_reg_title",
        "uz",
        name=full_name,
        phone=phone,
        username=user.username or "yo'q",
        user_id=user.id,
    )

    for admin_id in admin_ids:
        if admin_id:
            try:
                admin_agent = agents.get(admin_id)
                admin_lang = admin_agent.lang if admin_agent else "uz"
                await message.bot.send_message(
                    chat_id=admin_id,
                    text=notify_text,
                    reply_markup=get_admin_approval_keyboard(user.id, admin_lang),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Failed to send admin notification to {admin_id}: {e}")


@router.message(RegistrationStates.waiting_for_contact)
async def invalid_contact_message(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("chosen_lang", "uz")
    await message.answer(t("invalid_contact", lang))


@router.callback_query(F.data.startswith("approve_agent:"))
async def callback_approve_agent(callback: CallbackQuery, role: str):
    if role not in ("admin", "superadmin"):
        await callback.answer("Sizda bu amal uchun ruxsat yo'q!", show_alert=True)
        return

    target_id = int(callback.data.split(":")[1])
    target_agent = await sheets_service.get_agent_by_id(target_id)
    if not target_agent or target_agent.status != "pending":
        await callback.answer("Bu so'rov allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    admin_name = callback.from_user.full_name or "Admin"
    await sheets_service.set_agent_status(
        telegram_id=target_id,
        status="active",
        admin_id=callback.from_user.id,
        admin_name=admin_name,
    )

    # Edit the inline message to show decision
    try:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ <b>Qabul qilindi</b> ({admin_name})",
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        pass

    # Send message to approved agent
    try:
        settings = get_settings()
        webapp_url = f"{settings.PUBLIC_BASE_URL}/app"
        await callback.bot.send_message(
            chat_id=target_id,
            text=t("reg_approved", target_agent.lang),
            reply_markup=get_main_menu(
                lang=target_agent.lang,
                role=target_agent.role,
                webapp_url=webapp_url,
            ),
        )
    except Exception as e:
        logger.warning(f"Could not notify agent {target_id} of approval: {e}")

    await callback.answer("Agent tasdiqlandi!")


@router.callback_query(F.data.startswith("reject_agent:"))
async def callback_reject_agent(callback: CallbackQuery, role: str):
    if role not in ("admin", "superadmin"):
        await callback.answer("Sizda bu amal uchun ruxsat yo'q!", show_alert=True)
        return

    target_id = int(callback.data.split(":")[1])
    target_agent = await sheets_service.get_agent_by_id(target_id)
    if not target_agent or target_agent.status != "pending":
        await callback.answer("Bu so'rov allaqachon ko'rib chiqilgan!", show_alert=True)
        return

    admin_name = callback.from_user.full_name or "Admin"
    await sheets_service.set_agent_status(
        telegram_id=target_id,
        status="blocked",
        admin_id=callback.from_user.id,
        admin_name=admin_name,
    )

    try:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n❌ <b>Rad etildi</b> ({admin_name})",
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        pass

    try:
        await callback.bot.send_message(
            chat_id=target_id,
            text=t("reg_rejected", target_agent.lang),
        )
    except Exception as e:
        logger.warning(f"Could not notify agent {target_id} of rejection: {e}")

    await callback.answer("Agent rad etildi.")
