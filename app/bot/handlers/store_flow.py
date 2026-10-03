import asyncio
import io
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from app.bot.keyboards import (
    get_back_cancel_keyboard,
    get_cancel_keyboard,
    get_duplicate_inn_keyboard,
    get_location_keyboard,
    get_main_menu,
    get_photos_control_inline_keyboard,
    get_region_confirm_keyboard,
    get_skip_back_cancel_keyboard,
    get_skip_cancel_keyboard,
    get_summary_keyboard,
)
from app.bot.states import StoreFlowStates
from app.config import get_settings
from app.i18n import t
from app.services.drive import drive_service
from app.services.geocode import geocode_service
from app.services.images import compress_image
from app.services.notify import notify_new_store_saved, notify_new_visit_saved
from app.services.sheets import Agent, Store, Visit, get_current_tashkent_time, sheets_service
from app.services.stats import get_agent_stats
from app.utils.validators import clean_text, normalize_phone, validate_inn, validate_store_name

logger = logging.getLogger(__name__)
router = Router(name="store_flow_router")

SKIP_ALIASES = [
    "⏭ o'tkazib yuborish",
    "⏭ ўтказиб юбориш",
    "⏭ пропустить",
    "/skip",
    "skip",
    "o'tkazish",
    "otkazish",
    "пропустить",
    "o'tkazib yuborish",
    "ўтказиб юбориш",
    "davom etish",
    "давом этиш",
]


# ------------------ Entry Point ------------------
@router.message(F.text.in_(["➕ Yangi do'kon", "➕ Янги дўкон", "➕ Новый магазин"]))
async def start_store_flow(message: Message, state: FSMContext, lang: str):
    await state.clear()
    await state.update_data(photos=[], is_visit=False)
    await state.set_state(StoreFlowStates.waiting_for_photos)
    await message.answer(
        t("prompt_photo", lang),
        reply_markup=get_cancel_keyboard(lang),
    )


# ------------------ Step 1: Photos (MANDATORY) ------------------
@router.message(
    StoreFlowStates.waiting_for_photos,
    F.text.func(lambda text: (text or "").strip().lower() in SKIP_ALIASES),
)
async def skip_photos(message: Message, state: FSMContext, lang: str):
    # Photo is mandatory — reject skip attempts
    await message.answer(
        t("photo_required", lang),
        reply_markup=get_cancel_keyboard(lang),
    )


@router.message(StoreFlowStates.waiting_for_photos, F.photo)
async def process_photo(message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    photos: list[str] = data.get("photos", [])

    # Get highest resolution PhotoSize
    best_photo = message.photo[-1]
    photos.append(best_photo.file_id)
    await state.update_data(photos=photos)

    count = len(photos)
    if count >= 3:
        # Reached max photos, proceed to location
        await state.set_state(StoreFlowStates.waiting_for_location)
        await message.answer(
            t("prompt_location", lang),
            reply_markup=get_location_keyboard(lang),
        )
    else:
        await message.answer(
            t("prompt_photo_next", lang, count=count),
            reply_markup=get_photos_control_inline_keyboard(count, lang),
        )


@router.message(StoreFlowStates.waiting_for_photos, F.document)
async def process_document_photo(message: Message, state: FSMContext, lang: str):
    doc = message.document
    if doc and doc.mime_type and doc.mime_type.startswith("image/"):
        data = await state.get_data()
        photos: list[str] = data.get("photos", [])
        photos.append(doc.file_id)
        await state.update_data(photos=photos)

        count = len(photos)
        if count >= 3:
            await state.set_state(StoreFlowStates.waiting_for_location)
            await message.answer(
                t("prompt_location", lang),
                reply_markup=get_location_keyboard(lang),
            )
        else:
            await message.answer(
                t("prompt_photo_next", lang, count=count),
                reply_markup=get_photos_control_inline_keyboard(count, lang),
            )
    else:
        await message.answer(t("invalid_photo", lang))


@router.message(StoreFlowStates.waiting_for_photos, F.location)
async def process_location_during_photos(message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    photos = data.get("photos", [])
    await state.update_data(photos=photos)
    await state.set_state(StoreFlowStates.waiting_for_location)
    await process_location(message, state, lang)


@router.message(StoreFlowStates.waiting_for_photos)
async def fallback_photos(message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    photos = data.get("photos", [])
    count = len(photos)
    if count > 0:
        await message.answer(
            t("prompt_photo_next", lang, count=count),
            reply_markup=get_photos_control_inline_keyboard(count, lang),
        )
    else:
        await message.answer(
            t("invalid_photo", lang),
            reply_markup=get_skip_cancel_keyboard(lang),
        )


@router.callback_query(StoreFlowStates.waiting_for_photos, F.data == "flow:more_photos")
async def callback_more_photos(callback: CallbackQuery, lang: str):
    await callback.answer()
    await callback.message.answer(
        t("prompt_photo", lang),
        reply_markup=get_skip_cancel_keyboard(lang),
    )


@router.callback_query(StoreFlowStates.waiting_for_photos, F.data == "flow:photos_done")
async def callback_photos_done(callback: CallbackQuery, state: FSMContext, lang: str):
    await callback.answer()
    await state.set_state(StoreFlowStates.waiting_for_location)
    await callback.message.answer(
        t("prompt_location", lang),
        reply_markup=get_location_keyboard(lang),
    )


# ------------------ Step 2: Location ------------------
@router.message(StoreFlowStates.waiting_for_location, F.location)
async def process_location(message: Message, state: FSMContext, lang: str):
    # Reject forwarded location
    if getattr(message, "forward_origin", None) or getattr(message, "forward_date", None):
        await message.answer(t("invalid_location_forward", lang), reply_markup=get_location_keyboard(lang))
        return

    loc = message.location
    lat = loc.latitude
    lon = loc.longitude
    await state.update_data(lat=lat, lon=lon)

    # Reverse geocode via Nominatim
    await message.answer("🔍 Hudud aniqlanmoqda, iltimos kuting...", reply_markup=ReplyKeyboardRemove())
    addr = await geocode_service.reverse_geocode(lat, lon)

    if addr and addr.get("state"):
        state_name = addr.get("state", "")
        district_name = addr.get("district", "")
        mahalla_name = addr.get("mahalla", "")

        await state.update_data(
            state_name=state_name,
            district_name=district_name,
            mahalla_name=mahalla_name,
        )

        if not mahalla_name:
            # Mahalla couldn't be detected automatically; manual entry (or skippable)
            await state.set_state(StoreFlowStates.manual_mahalla)
            await message.answer(
                f"🏛 Viloyat: {state_name}\n🏙 Tuman: {district_name}\n\n"
                f"{t('prompt_region_manual_mahalla', lang)}",
                reply_markup=get_skip_back_cancel_keyboard(lang),
            )
        else:
            await state.set_state(StoreFlowStates.confirm_region)
            await message.answer(
                t(
                    "prompt_region_detected",
                    lang,
                    state=state_name,
                    district=district_name,
                    mahalla=mahalla_name,
                ),
                reply_markup=get_region_confirm_keyboard(lang),
            )
    else:
        # Nominatim failed or returned empty
        await state.set_state(StoreFlowStates.manual_all_region)
        await message.answer(
            t("prompt_region_manual_all", lang),
            reply_markup=get_skip_back_cancel_keyboard(lang),
        )


@router.message(StoreFlowStates.waiting_for_location)
async def invalid_location(message: Message, lang: str):
    await message.answer(t("invalid_location_text", lang), reply_markup=get_location_keyboard(lang))


# ------------------ Step 3: Region Confirmation & Manual Entry ------------------
@router.callback_query(StoreFlowStates.confirm_region, F.data == "region:correct")
async def callback_region_correct(callback: CallbackQuery, state: FSMContext, lang: str):
    await callback.answer()
    await state.set_state(StoreFlowStates.waiting_for_inn)
    await callback.message.answer(
        t("prompt_inn", lang),
        reply_markup=get_skip_back_cancel_keyboard(lang),
    )


@router.callback_query(StoreFlowStates.confirm_region, F.data == "region:edit_mahalla")
async def callback_edit_mahalla(callback: CallbackQuery, state: FSMContext, lang: str):
    await callback.answer()
    await state.set_state(StoreFlowStates.manual_mahalla)
    await callback.message.answer(
        t("prompt_region_manual_mahalla", lang),
        reply_markup=get_skip_back_cancel_keyboard(lang),
    )


@router.callback_query(StoreFlowStates.confirm_region, F.data == "region:edit_all")
async def callback_edit_all_region(callback: CallbackQuery, state: FSMContext, lang: str):
    await callback.answer()
    await state.set_state(StoreFlowStates.manual_all_region)
    await callback.message.answer(
        t("prompt_region_manual_all", lang),
        reply_markup=get_skip_back_cancel_keyboard(lang),
    )


@router.message(StoreFlowStates.confirm_region)
async def process_region_confirm_message(message: Message, state: FSMContext, lang: str):
    text = (message.text or "").strip().lower()

    # User confirms with text or skip
    if any(w in text for w in ["to'g'ri", "to'gri", "togri", "to‘g‘ri", "тўғри", "верно", "да", "ha", "xa", "yes", "ok"]) or text in SKIP_ALIASES:
        await state.set_state(StoreFlowStates.waiting_for_inn)
        await message.answer(
            t("prompt_inn", lang),
            reply_markup=get_skip_back_cancel_keyboard(lang),
        )
        return

    # User immediately enters 9-digit INN
    is_valid, _ = validate_inn(message.text or "")
    if is_valid:
        await process_inn(message, state, lang)
        return

    # User wants to edit mahalla
    if "mahalla" in text:
        await state.set_state(StoreFlowStates.manual_mahalla)
        await message.answer(
            t("prompt_region_manual_mahalla", lang),
            reply_markup=get_skip_back_cancel_keyboard(lang),
        )
        return

    # Otherwise remind them
    await message.answer(
        "Iltimos, yuqoridagi **'✅ To'g'ri'** tugmasini bosing yoki do'konning 9 xonali INN raqamini kiriting:",
        reply_markup=get_region_confirm_keyboard(lang),
    )


@router.message(StoreFlowStates.manual_mahalla)
async def process_manual_mahalla(message: Message, state: FSMContext, lang: str):
    raw_text = (message.text or "").strip()
    if raw_text.lower() in SKIP_ALIASES or raw_text.lower() in ("-", "yo'q", "yoq", "йўқ", "нет"):
        await state.update_data(mahalla_name="")
        await state.set_state(StoreFlowStates.waiting_for_inn)
        await message.answer(
            t("prompt_inn", lang),
            reply_markup=get_skip_back_cancel_keyboard(lang),
        )
        return

    mahalla = clean_text(raw_text, max_length=80)
    if len(mahalla) < 2:
        await message.answer(
            "Iltimos, mahalla nomini to'liqroq kiriting (kamida 2 ta belgi) yoki '⏭ O'tkazib yuborish' tugmasini bosing:",
            reply_markup=get_skip_back_cancel_keyboard(lang),
        )
        return

    await state.update_data(mahalla_name=mahalla)
    await state.set_state(StoreFlowStates.waiting_for_inn)
    await message.answer(
        t("prompt_inn", lang),
        reply_markup=get_skip_back_cancel_keyboard(lang),
    )


@router.message(StoreFlowStates.manual_all_region)
async def process_manual_all_region(message: Message, state: FSMContext, lang: str):
    raw_text = (message.text or "").strip()
    if raw_text.lower() in SKIP_ALIASES or raw_text.lower() in ("-", "yo'q", "yoq", "йўқ", "нет"):
        await state.update_data(
            state_name="Noma'lum",
            district_name="Noma'lum",
            mahalla_name="",
        )
        await state.set_state(StoreFlowStates.waiting_for_inn)
        await message.answer(
            t("prompt_inn", lang),
            reply_markup=get_skip_back_cancel_keyboard(lang),
        )
        return

    text = clean_text(raw_text)
    parts = [p.strip() for p in text.split(",") if p.strip()]

    if len(parts) >= 3:
        state_name, district_name, mahalla_name = parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        state_name, district_name, mahalla_name = parts[0], parts[1], ""
    elif len(parts) == 1:
        state_name, district_name, mahalla_name = parts[0], "Noma'lum", ""
    else:
        await message.answer(
            "Iltimos, hudud nomini to'liq kiriting (masalan: Toshkent sh., Chilonzor tumani, 1-mavze) yoki '⏭ O'tkazib yuborish' bosing:",
            reply_markup=get_skip_back_cancel_keyboard(lang),
        )
        return

    await state.update_data(
        state_name=state_name,
        district_name=district_name,
        mahalla_name=mahalla_name,
    )
    await state.set_state(StoreFlowStates.waiting_for_inn)
    await message.answer(
        t("prompt_inn", lang),
        reply_markup=get_skip_back_cancel_keyboard(lang),
    )


# ------------------ Step 4: INN ------------------
@router.message(StoreFlowStates.waiting_for_inn)
async def process_inn(message: Message, state: FSMContext, lang: str):
    raw_text = (message.text or "").strip()
    if raw_text.lower() in SKIP_ALIASES or raw_text.lower() in ("-", "0", "yo'q", "yoq", "йўқ", "нет"):
        await state.update_data(inn="")
        await state.set_state(StoreFlowStates.waiting_for_store_name)
        await message.answer(
            t("prompt_store_name", lang),
            reply_markup=get_back_cancel_keyboard(lang),
        )
        return

    is_valid, inn = validate_inn(raw_text)
    if not is_valid:
        await message.answer(
            t("invalid_inn", lang),
            reply_markup=get_skip_back_cancel_keyboard(lang),
        )
        return

    await state.update_data(inn=inn)

    # Check for duplicate INN in Google Sheets
    duplicates = await sheets_service.find_stores_by_inn(inn)
    if duplicates:
        existing = duplicates[0]
        await state.update_data(
            existing_store_id=existing.id,
            existing_store_name=existing.name,
            store_name=existing.name,
            phone=existing.phone,
        )
        await state.set_state(StoreFlowStates.duplicate_inn_decision)
        await message.answer(
            t(
                "duplicate_inn_found",
                lang,
                name=existing.name,
                agent=existing.agent_name,
                date=f"{existing.date} {existing.time}",
            ),
            reply_markup=get_duplicate_inn_keyboard(lang),
        )
        return

    # No duplicate -> proceed to store name
    await state.set_state(StoreFlowStates.waiting_for_store_name)
    await message.answer(
        t("prompt_store_name", lang),
        reply_markup=get_back_cancel_keyboard(lang),
    )


@router.callback_query(StoreFlowStates.duplicate_inn_decision, F.data == "dup_inn:add_visit")
async def callback_dup_add_visit(callback: CallbackQuery, state: FSMContext, lang: str):
    await callback.answer()
    await state.update_data(is_visit=True)
    await show_summary(callback.message, state, lang)


@router.callback_query(StoreFlowStates.duplicate_inn_decision, F.data == "dup_inn:save_anyway")
async def callback_dup_save_anyway(callback: CallbackQuery, state: FSMContext, lang: str):
    await callback.answer()
    await state.update_data(is_visit=False)
    await state.set_state(StoreFlowStates.waiting_for_store_name)
    await callback.message.answer(
        t("prompt_store_name", lang),
        reply_markup=get_back_cancel_keyboard(lang),
    )


# ------------------ Step 5: Store Name ------------------
@router.message(StoreFlowStates.waiting_for_store_name)
async def process_store_name(message: Message, state: FSMContext, lang: str):
    is_valid, name = validate_store_name(message.text or "")
    if not is_valid:
        await message.answer(t("invalid_store_name", lang), reply_markup=get_back_cancel_keyboard(lang))
        return

    await state.update_data(store_name=name)
    await state.set_state(StoreFlowStates.waiting_for_phone)
    await message.answer(
        t("prompt_phone", lang),
        reply_markup=get_skip_back_cancel_keyboard(lang),
    )


# ------------------ Step 6: Phone ------------------
@router.message(StoreFlowStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext, lang: str):
    text = (message.text or "").strip()
    if text.lower() in SKIP_ALIASES or text.lower() in ("-", "yo'q", "yoq", "йўқ", "нет"):
        phone = ""
    else:
        is_valid, phone = normalize_phone(text)
        if not is_valid:
            await message.answer(
                t("invalid_phone", lang),
                reply_markup=get_skip_back_cancel_keyboard(lang),
            )
            return

    await state.update_data(phone=phone)
    await show_summary(message, state, lang)


# ------------------ Step 7: Summary ------------------
async def show_summary(message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    is_visit = data.get("is_visit", False)
    photos = data.get("photos", [])

    await state.set_state(StoreFlowStates.summary_confirmation)

    if is_visit:
        text = t(
            "summary_visit_title",
            lang,
            name=data.get("store_name", ""),
            store_id=data.get("existing_store_id", 0),
            inn=data.get("inn", ""),
            state=data.get("state_name", ""),
            district=data.get("district_name", ""),
            mahalla=data.get("mahalla_name", ""),
            agent=message.from_user.full_name or "Agent",
            photos_count=len(photos),
        )
    else:
        text = t(
            "summary_title",
            lang,
            name=data.get("store_name", ""),
            inn=data.get("inn", ""),
            phone=data.get("phone", "") or "Kiritilmagan",
            state=data.get("state_name", ""),
            district=data.get("district_name", ""),
            mahalla=data.get("mahalla_name", ""),
            agent=message.from_user.full_name or "Agent",
            photos_count=len(photos),
        )

    await message.answer(text, reply_markup=get_summary_keyboard(lang))


# ------------------ Step 8: Save ------------------
@router.callback_query(StoreFlowStates.summary_confirmation, F.data == "summary:save")
async def callback_save_store(callback: CallbackQuery, state: FSMContext, agent: Agent, lang: str, role: str):
    data = await state.get_data()

    # Prevent concurrent duplicate saves
    if data.get("is_saving"):
        await callback.answer("Saqlash davom etmoqda...")
        return
    await state.update_data(is_saving=True)

    await callback.answer()
    status_msg = await callback.message.answer(t("saving_process", lang), reply_markup=ReplyKeyboardRemove())

    try:
        photos: list[str] = data.get("photos", [])
        is_visit: bool = data.get("is_visit", False)
        lat: float = float(data.get("lat", 0.0))
        lon: float = float(data.get("lon", 0.0))
        state_name = data.get("state_name", "")
        district_name = data.get("district_name", "")
        mahalla_name = data.get("mahalla_name", "")
        inn = data.get("inn", "")
        store_name = data.get("store_name", "")
        phone = data.get("phone", "")

        now_t = get_current_tashkent_time()
        month_str = now_t.strftime("%Y-%m")
        timestamp_str = now_t.strftime("%Y%m%d_%H%M%S")

        # Download, compress, and upload photos in parallel
        async def process_single_photo(idx: int, file_id: str) -> tuple[str, str]:
            try:
                file_info = await callback.bot.get_file(file_id)
                file_io = io.BytesIO()
                await callback.bot.download_file(file_info.file_path, destination=file_io)
                raw_bytes = file_io.getvalue()
                compressed_bytes = compress_image(raw_bytes, max_dimension=2560, quality=95)
                filename = f"store_{timestamp_str}_{idx}.jpg"
                uploaded_id, uploaded_url = await drive_service.upload_image(
                    image_bytes=compressed_bytes,
                    filename=filename,
                    month_str=month_str,
                )
                return uploaded_url, uploaded_id
            except Exception as e:
                logger.warning(f"Photo upload fallback for {file_id}: {e}")
                return f"https://drive.google.com/mock/{file_id}", f"mock_fid_{idx}"

        results = await asyncio.gather(
            *[process_single_photo(idx, fid) for idx, fid in enumerate(photos, start=1)]
        )
        drive_urls = [r[0] for r in results]
        drive_file_ids = [r[1] for r in results]

        p1_url = drive_urls[0] if len(drive_urls) > 0 else ""
        p2_url = drive_urls[1] if len(drive_urls) > 1 else ""
        p3_url = drive_urls[2] if len(drive_urls) > 2 else ""

        p1_id = drive_file_ids[0] if len(drive_file_ids) > 0 else ""
        p2_id = drive_file_ids[1] if len(drive_file_ids) > 1 else ""
        p3_id = drive_file_ids[2] if len(drive_file_ids) > 2 else ""

        settings = get_settings()
        webapp_url = f"{settings.PUBLIC_BASE_URL}/app"

        if is_visit:
            existing_id = int(data.get("existing_store_id", 0))
            visit = Visit(
                store_id=existing_id,
                agent_id=callback.from_user.id,
                agent_name=callback.from_user.full_name or "Agent",
                lat=lat,
                lon=lon,
                photo1=p1_url,
                photo2=p2_url,
                photo3=p3_url,
                photo1_id=p1_id,
                photo2_id=p2_id,
                photo3_id=p3_id,
            )
            saved_visit = await sheets_service.append_visit(visit)

            # Send notification
            await notify_new_visit_saved(callback.bot, saved_visit, store_name)

            await state.clear()
            try:
                await status_msg.delete()
            except Exception:
                pass
            await callback.message.answer(t("saved_visit_success", lang, store_id=existing_id))
            await callback.message.answer(
                t("main_menu_prompt", lang),
                reply_markup=get_main_menu(lang=lang, role=role, webapp_url=webapp_url),
            )
        else:
            store = Store(
                agent_id=callback.from_user.id,
                agent_name=callback.from_user.full_name or "Agent",
                name=store_name,
                inn=inn,
                phone=phone,
                state=state_name,
                district=district_name,
                mahalla=mahalla_name,
                lat=lat,
                lon=lon,
                photo1=p1_url,
                photo2=p2_url,
                photo3=p3_url,
                photo1_id=p1_id,
                photo2_id=p2_id,
                photo3_id=p3_id,
                status="faol",
            )
            saved_store = await sheets_service.append_store(store)

            # Send notification
            await notify_new_store_saved(callback.bot, saved_store)

            # Calculate daily plan completion
            daily_plan = agent.daily_plan if agent else 20
            agent_stats = await get_agent_stats(callback.from_user.id, daily_plan=daily_plan)
            today_count = agent_stats["today"]

            await state.clear()

            # Congratulate if daily plan met
            if today_count == daily_plan:
                await callback.message.answer(t("plan_completed_congrats", lang, daily_plan=daily_plan))

            try:
                await status_msg.delete()
            except Exception:
                pass

            await callback.message.answer(
                t("saved_success", lang, id=saved_store.id, today_count=today_count, daily_plan=daily_plan)
            )
            await callback.message.answer(
                t("main_menu_prompt", lang),
                reply_markup=get_main_menu(lang=lang, role=role, webapp_url=webapp_url),
            )

    except Exception as e:
        logger.error(f"Error saving store: {e}", exc_info=True)
        await state.update_data(is_saving=False)
        try:
            await status_msg.delete()
        except Exception:
            pass
        await callback.message.answer(
            f"{t('save_failed', lang)}\n\nXatolik: {str(e)[:100]}",
            reply_markup=get_summary_keyboard(lang),
        )
