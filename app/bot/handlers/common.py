from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import get_main_menu
from app.config import get_settings
from app.i18n import t

router = Router(name="common_router")


@router.message(F.text.in_(["❌ Bekor qilish", "❌ Бекор қилиш", "❌ Отмена"]))
async def process_cancel_text(message: Message, state: FSMContext, lang: str, role: str):
    await state.clear()
    settings = get_settings()
    webapp_url = f"{settings.PUBLIC_BASE_URL}/app"
    await message.answer(
        t("flow_cancelled", lang),
        reply_markup=get_main_menu(lang=lang, role=role, webapp_url=webapp_url),
    )


@router.callback_query(F.data == "flow:cancel")
async def process_cancel_callback(callback: CallbackQuery, state: FSMContext, lang: str, role: str):
    await state.clear()
    settings = get_settings()
    webapp_url = f"{settings.PUBLIC_BASE_URL}/app"
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        t("flow_cancelled", lang),
        reply_markup=get_main_menu(lang=lang, role=role, webapp_url=webapp_url),
    )
    await callback.answer()
