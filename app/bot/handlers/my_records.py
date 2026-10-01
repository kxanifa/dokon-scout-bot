import io

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.bot.states import EditRecordStates
from app.i18n import t
from app.services.drive import drive_service
from app.services.images import compress_image
from app.services.sheets import get_current_tashkent_time, sheets_service
from app.utils.validators import normalize_phone, validate_inn, validate_store_name

router = Router(name="my_records_router")
PAGE_SIZE = 5


def get_records_pagination_keyboard(page: int, total_pages: int, store_ids: list[int]) -> InlineKeyboardMarkup:
    keyboard = []
    # Edit button for each store on this page
    for sid in store_ids:
        keyboard.append([
            InlineKeyboardButton(text=f"✏️ #{sid} Do'konni tahrirlash", callback_data=f"edit_store:{sid}")
        ])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"records_page:{page - 1}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"records_page:{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_edit_fields_keyboard(store_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏪 Nomi", callback_data=f"edit_field:name:{store_id}")],
            [InlineKeyboardButton(text="📞 Telefon", callback_data=f"edit_field:phone:{store_id}")],
            [InlineKeyboardButton(text="🔢 INN", callback_data=f"edit_field:inn:{store_id}")],
            [InlineKeyboardButton(text="📍 Hudud", callback_data=f"edit_field:region:{store_id}")],
            [InlineKeyboardButton(text="🖼 Rasm", callback_data=f"edit_field:photo:{store_id}")],
            [InlineKeyboardButton(text="⬅️ Bekor qilish", callback_data="records_page:1")],
        ]
    )


async def render_records_page(user_id: int, page: int, lang: str) -> tuple[str, InlineKeyboardMarkup | None]:
    all_stores = await sheets_service.get_stores(include_deleted=False)
    my_stores = [s for s in all_stores if s.agent_id == user_id]
    my_stores.sort(key=lambda s: s.id, reverse=True)

    if not my_stores:
        return t("no_records", lang), None

    total_records = len(my_stores)
    total_pages = (total_records + PAGE_SIZE - 1) // PAGE_SIZE
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * PAGE_SIZE
    page_stores = my_stores[start_idx : start_idx + PAGE_SIZE]

    cards = []
    store_ids = []
    for s in page_stores:
        store_ids.append(s.id)
        cards.append(
            t(
                "record_card",
                lang,
                id=s.id,
                name=s.name,
                inn=s.inn,
                phone=s.phone or "Kiritilmagan",
                state=s.state,
                district=s.district,
                mahalla=s.mahalla,
                date=s.date,
                time=s.time,
            )
        )

    title = t("my_records_title", lang, page=page, total_pages=total_pages)
    full_text = f"<b>{title}</b>\n\n" + "\n\n────────────────\n\n".join(cards)
    kb = get_records_pagination_keyboard(page, total_pages, store_ids)
    return full_text, kb


@router.message(Command("records"))
@router.message(F.text.in_(["📋 Mening yozuvlarim", "📋 Менинг ёзувларим", "📋 Мои записи"]))
async def cmd_my_records(message: Message, lang: str):
    text, kb = await render_records_page(message.from_user.id, page=1, lang=lang)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("records_page:"))
async def callback_records_page(callback: CallbackQuery, lang: str):
    page = int(callback.data.split(":")[1])
    text, kb = await render_records_page(callback.from_user.id, page=page, lang=lang)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("edit_store:"))
async def callback_edit_store(callback: CallbackQuery, lang: str):
    store_id = int(callback.data.split(":")[1])
    store = await sheets_service.get_store_by_id(store_id)

    # Server side ownership validation
    if not store or store.agent_id != callback.from_user.id:
        await callback.answer(t("access_denied_record", lang), show_alert=True)
        return

    text = f"<b>№{store.id} — {store.name}</b>\n{t('edit_select_field', lang)}"
    try:
        await callback.message.edit_text(text, reply_markup=get_edit_fields_keyboard(store_id), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"))
async def callback_edit_field(callback: CallbackQuery, state: FSMContext, lang: str):
    parts = callback.data.split(":")
    field = parts[1]
    store_id = int(parts[2])

    store = await sheets_service.get_store_by_id(store_id)
    if not store or store.agent_id != callback.from_user.id:
        await callback.answer(t("access_denied_record", lang), show_alert=True)
        return

    await state.update_data(editing_store_id=store_id)

    if field == "name":
        await state.set_state(EditRecordStates.editing_name)
        await callback.message.answer(f"Yangi do'kon nomini kiriting (hozirgi: {store.name}):")
    elif field == "phone":
        await state.set_state(EditRecordStates.editing_phone)
        await callback.message.answer(f"Yangi telefon raqamini kiriting (hozirgi: {store.phone or 'yoq'}):")
    elif field == "inn":
        await state.set_state(EditRecordStates.editing_inn)
        await callback.message.answer(f"Yangi 9 xonali INN raqamini kiriting (hozirgi: {store.inn}):")
    elif field == "region":
        await state.set_state(EditRecordStates.editing_region)
        await callback.message.answer(
            f"Yangi hudud nomini vergul bilan ajratib yozing:\n(Hozirgi: {store.state}, {store.district}, {store.mahalla})"
        )
    elif field == "photo":
        await state.set_state(EditRecordStates.editing_photo)
        await callback.message.answer("Yangi rasm yuboring (1-rasm o'rniga):")

    await callback.answer()


@router.message(EditRecordStates.editing_name)
async def process_edit_name(message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    store_id = data.get("editing_store_id")
    is_valid, name = validate_store_name(message.text or "")
    if not is_valid:
        await message.answer(t("invalid_store_name", lang))
        return

    await sheets_service.update_store_fields(
        store_id=store_id,
        updates={"name": name},
        updated_by_id=message.from_user.id,
        updated_by_name=message.from_user.full_name or "Agent",
    )
    await state.clear()
    await message.answer(f"✅ {t('edit_field_success', lang)}")
    text, kb = await render_records_page(message.from_user.id, page=1, lang=lang)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(EditRecordStates.editing_phone)
async def process_edit_phone(message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    store_id = data.get("editing_store_id")
    is_valid, phone = normalize_phone(message.text or "")
    if not is_valid:
        await message.answer(t("invalid_phone", lang))
        return

    await sheets_service.update_store_fields(
        store_id=store_id,
        updates={"phone": phone},
        updated_by_id=message.from_user.id,
        updated_by_name=message.from_user.full_name or "Agent",
    )
    await state.clear()
    await message.answer(f"✅ {t('edit_field_success', lang)}")
    text, kb = await render_records_page(message.from_user.id, page=1, lang=lang)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(EditRecordStates.editing_inn)
async def process_edit_inn(message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    store_id = data.get("editing_store_id")
    is_valid, inn = validate_inn(message.text or "")
    if not is_valid:
        await message.answer(t("invalid_inn", lang))
        return

    # Check conflict with other stores
    duplicates = await sheets_service.find_stores_by_inn(inn)
    if any(s.id != store_id for s in duplicates):
        await message.answer("⚠️ Bu INN boshqa do'konda mavjud! Iltimos, tekshirib qayta kiriting.")
        return

    await sheets_service.update_store_fields(
        store_id=store_id,
        updates={"inn": inn},
        updated_by_id=message.from_user.id,
        updated_by_name=message.from_user.full_name or "Agent",
    )
    await state.clear()
    await message.answer(f"✅ {t('edit_field_success', lang)}")
    text, kb = await render_records_page(message.from_user.id, page=1, lang=lang)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(EditRecordStates.editing_region)
async def process_edit_region(message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    store_id = data.get("editing_store_id")
    parts = [p.strip() for p in (message.text or "").split(",") if p.strip()]
    if len(parts) < 2:
        await message.answer("Iltimos, viloyat, tuman va mahallani vergul bilan ajratib yozing.")
        return

    state_name = parts[0]
    district_name = parts[1]
    mahalla_name = parts[2] if len(parts) > 2 else "Noma'lum"

    await sheets_service.update_store_fields(
        store_id=store_id,
        updates={"state": state_name, "district": district_name, "mahalla": mahalla_name},
        updated_by_id=message.from_user.id,
        updated_by_name=message.from_user.full_name or "Agent",
    )
    await state.clear()
    await message.answer(f"✅ {t('edit_field_success', lang)}")
    text, kb = await render_records_page(message.from_user.id, page=1, lang=lang)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(EditRecordStates.editing_photo, F.photo)
async def process_edit_photo(message: Message, state: FSMContext, lang: str):
    data = await state.get_data()
    store_id = data.get("editing_store_id")
    photo = message.photo[-1]

    status_msg = await message.answer("⏳ Rasm yangilanmoqda...")
    try:
        file_info = await message.bot.get_file(photo.file_id)
        buf = io.BytesIO()
        await message.bot.download_file(file_info.file_path, destination=buf)
        compressed = compress_image(buf.getvalue(), max_dimension=1600, quality=80)

        month_str = get_current_tashkent_time().strftime("%Y-%m")
        filename = f"store_{store_id}_updated_{get_current_tashkent_time().strftime('%Y%m%d_%H%M%S')}.jpg"

        uploaded_id, uploaded_url = await drive_service.upload_image(compressed, filename, month_str)

        await sheets_service.update_store_fields(
            store_id=store_id,
            updates={"photo1": uploaded_url, "photo1_id": uploaded_id},
            updated_by_id=message.from_user.id,
            updated_by_name=message.from_user.full_name or "Agent",
        )
        await status_msg.edit_text(f"✅ {t('edit_field_success', lang)}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {e}")

    await state.clear()
    text, kb = await render_records_page(message.from_user.id, page=1, lang=lang)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
