from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    waiting_for_lang = State()
    waiting_for_name = State()
    waiting_for_contact = State()


class StoreFlowStates(StatesGroup):
    waiting_for_photos = State()
    waiting_for_location = State()
    confirm_region = State()
    manual_mahalla = State()
    manual_all_region = State()
    waiting_for_inn = State()
    duplicate_inn_decision = State()
    waiting_for_store_name = State()
    waiting_for_phone = State()
    summary_confirmation = State()
    saving = State()


class EditRecordStates(StatesGroup):
    selecting_field = State()
    editing_name = State()
    editing_phone = State()
    editing_inn = State()
    editing_region = State()
    editing_photo = State()
