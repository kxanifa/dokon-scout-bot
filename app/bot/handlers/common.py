from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import (
    get_back_cancel_keyboard,
    get_location_keyboard,
    get_main_menu,
    get_photos_control_inline_keyboard,
    get_region_confirm_keyboard,
)
from app.bot.states import StoreFlowStates
from app.config import get_settings
from app.i18n import t

router = Router(name="common_router")


@router.message(Command("cancel"))
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


@router.message(F.text.in_(["⬅️ Orqaga", "⬅️ Орқага", "⬅️ Назад"]))
async def process_back_button(message: Message, state: FSMContext, lang: str, role: str):
    current_state = await state.get_state()
    settings = get_settings()
    webapp_url = f"{settings.PUBLIC_BASE_URL}/app"

    if not current_state:
        await message.answer(
            t("main_menu_prompt", lang),
            reply_markup=get_main_menu(lang=lang, role=role, webapp_url=webapp_url),
        )
        return

    # Handle back navigation based on current FSM state
    if current_state == StoreFlowStates.waiting_for_location.state:
        await state.set_state(StoreFlowStates.waiting_for_photos)
        data = await state.get_data()
        photos = data.get("photos", [])
        await message.answer(
            t("prompt_photo_next", lang, count=len(photos)),
            reply_markup=get_photos_control_inline_keyboard(len(photos), lang),
        )
    elif current_state in (
        StoreFlowStates.confirm_region.state,
        StoreFlowStates.manual_mahalla.state,
        StoreFlowStates.manual_all_region.state,
    ):
        await state.set_state(StoreFlowStates.waiting_for_location)
        await message.answer(
            t("prompt_location", lang),
            reply_markup=get_location_keyboard(lang),
        )
    elif current_state == StoreFlowStates.waiting_for_inn.state:
        await state.set_state(StoreFlowStates.confirm_region)
        data = await state.get_data()
        await message.answer(
            t(
                "prompt_region_detected",
                lang,
                state=data.get("state_name", ""),
                district=data.get("district_name", ""),
                mahalla=data.get("mahalla_name", ""),
            ),
            reply_markup=get_region_confirm_keyboard(lang),
        )
    elif current_state == StoreFlowStates.waiting_for_store_name.state:
        await state.set_state(StoreFlowStates.waiting_for_inn)
        await message.answer(t("prompt_inn", lang), reply_markup=get_back_cancel_keyboard(lang))
    elif current_state == StoreFlowStates.waiting_for_phone.state:
        await state.set_state(StoreFlowStates.waiting_for_store_name)
        await message.answer(t("prompt_store_name", lang), reply_markup=get_back_cancel_keyboard(lang))
    elif current_state == StoreFlowStates.summary_confirmation.state:
        await state.set_state(StoreFlowStates.waiting_for_phone)
        await message.answer(t("prompt_phone", lang), reply_markup=get_back_cancel_keyboard(lang))
    else:
        await state.clear()
        await message.answer(
            t("main_menu_prompt", lang),
            reply_markup=get_main_menu(lang=lang, role=role, webapp_url=webapp_url),
        )
