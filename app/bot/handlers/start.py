from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import get_language_inline_keyboard, get_main_menu
from app.bot.states import RegistrationStates
from app.config import get_settings
from app.i18n import t
from app.services.sheets import Agent, sheets_service

router = Router(name="start_router")


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, agent: Agent | None, role: str, status: str, lang: str):
    await state.clear()
    settings = get_settings()
    webapp_url = f"{settings.PUBLIC_BASE_URL}/app"

    # If already active agent/admin, show main menu directly
    if agent and status == "active":
        await message.answer(
            f"{t('main_menu_prompt', lang)}",
            reply_markup=get_main_menu(lang=lang, role=role, webapp_url=webapp_url),
        )
        return

    # If pending or blocked, AccessMiddleware will have handled it, but if somehow here:
    if agent and status == "pending":
        await message.answer(t("access_pending", lang))
        return
    if agent and status == "blocked":
        await message.answer(t("access_blocked", lang))
        return

    # Unregistered user -> ask for language
    await state.set_state(RegistrationStates.waiting_for_lang)
    await message.answer(
        t("welcome_select_lang", "uz"),
        reply_markup=get_language_inline_keyboard(),
    )


@router.callback_query(F.data.startswith("set_lang:"))
async def callback_select_lang(callback: CallbackQuery, state: FSMContext, agent: Agent | None, role: str):
    chosen_lang = callback.data.split(":")[1]
    if chosen_lang not in ("uz", "uz_cyr", "ru"):
        chosen_lang = "uz"

    settings = get_settings()
    webapp_url = f"{settings.PUBLIC_BASE_URL}/app"

    # If user is already registered, this is a language switch
    if agent and agent.status == "active":
        agent.lang = chosen_lang
        await sheets_service.upsert_agent(agent)
        await callback.message.edit_text(t("lang_changed", chosen_lang))
        await callback.message.answer(
            t("main_menu_prompt", chosen_lang),
            reply_markup=get_main_menu(lang=chosen_lang, role=role, webapp_url=webapp_url),
        )
        await callback.answer()
        return

    # Unregistered user -> save lang to FSM, ask for Name
    await state.update_data(chosen_lang=chosen_lang)
    await state.set_state(RegistrationStates.waiting_for_name)
    await callback.message.edit_text(t("ask_name", chosen_lang))
    await callback.answer()


@router.message(Command("lang"))
@router.message(F.text.in_(["⚙️ Til", "⚙️ Тил", "⚙️ Язык"]))
async def cmd_lang(message: Message, lang: str):
    await message.answer(
        t("welcome_select_lang", lang),
        reply_markup=get_language_inline_keyboard(),
    )
