from unittest.mock import AsyncMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Chat, Contact, Message, User
from fastapi.testclient import TestClient

from app.bot.handlers.registration import callback_approve_agent, process_contact
from app.bot.middlewares import AccessMiddleware
from app.config import get_settings
from app.main import app
from app.services.sheets import Agent, sheets_service


@pytest.fixture
def mock_sheets():
    agents_store: dict[int, Agent] = {}

    async def mock_get_agents():
        return dict(agents_store)

    async def mock_get_agent_by_id(tid: int):
        return agents_store.get(tid)

    async def mock_upsert_agent(ag: Agent):
        agents_store[ag.telegram_id] = ag
        return ag

    async def mock_set_agent_status(telegram_id: int, status: str, admin_id: int, admin_name: str):
        if telegram_id in agents_store:
            agents_store[telegram_id].status = status
            return True
        return False

    async def mock_set_agent_role(telegram_id: int, role: str, admin_id: int, admin_name: str):
        if telegram_id in agents_store:
            agents_store[telegram_id].role = role
            return True
        return False

    async def mock_append_log(entry):
        pass

    with (
        patch.object(sheets_service, "get_agents", side_effect=mock_get_agents),
        patch.object(sheets_service, "get_agent_by_id", side_effect=mock_get_agent_by_id),
        patch.object(sheets_service, "upsert_agent", side_effect=mock_upsert_agent),
        patch.object(sheets_service, "set_agent_status", side_effect=mock_set_agent_status),
        patch.object(sheets_service, "set_agent_role", side_effect=mock_set_agent_role),
        patch.object(sheets_service, "append_log", side_effect=mock_append_log),
    ):
        yield agents_store


def test_webhook_secret_verification():
    settings = get_settings()
    client = TestClient(app)

    # Valid secret
    response = client.post(
        "/tg/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": settings.WEBHOOK_SECRET},
        json={"update_id": 1, "message": {"message_id": 1, "date": 12345, "chat": {"id": 123, "type": "private"}}},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    # Invalid secret
    bad_response = client.post(
        "/tg/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong_secret"},
        json={"update_id": 1},
    )
    assert bad_response.status_code == 403


@pytest.mark.asyncio
async def test_access_middleware_rules(mock_sheets):
    middleware = AccessMiddleware()
    handler = AsyncMock(return_value="OK")

    user = User(id=111, is_bot=False, first_name="Test")
    chat = Chat(id=111, type="private")
    msg = Message(message_id=1, date=1000, chat=chat, from_user=user, text="/other")

    # 1. Blocked user
    data_blocked = {
        "event_from_user": user,
        "role": "agent",
        "status": "blocked",
        "lang": "uz",
        "state": None,
    }
    with patch.object(Message, "answer", new_callable=AsyncMock) as mock_ans:
        res = await middleware(handler, msg, data_blocked)
        assert res is None
        mock_ans.assert_called_once()
        assert "bloklangan" in mock_ans.call_args[0][0]

    # 2. Pending user
    data_pending = {
        "event_from_user": user,
        "role": "agent",
        "status": "pending",
        "lang": "uz",
        "state": None,
    }
    with patch.object(Message, "answer", new_callable=AsyncMock) as mock_ans:
        res = await middleware(handler, msg, data_pending)
        assert res is None
        mock_ans.assert_called_once()
        assert "ko'rib chiqilmoqda" in mock_ans.call_args[0][0]

    # 3. Superadmin always passes
    data_superadmin = {
        "event_from_user": user,
        "role": "superadmin",
        "status": "active",
        "lang": "uz",
        "state": None,
    }
    res = await middleware(handler, msg, data_superadmin)
    assert res == "OK"


@pytest.mark.asyncio
async def test_registration_contact_verification(mock_sheets):
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=123, user_id=123)
    state = FSMContext(storage=storage, key=key)
    await state.update_data(chosen_lang="uz", full_name="Vali Aliyev")

    user = User(id=123, is_bot=False, first_name="Vali")
    chat = Chat(id=123, type="private")

    # 1. Foreign contact (fraud)
    foreign_contact = Contact(phone_number="+998901112233", first_name="Boshqa", user_id=999)
    fraud_msg = Message(
        message_id=10,
        date=1000,
        chat=chat,
        from_user=user,
        contact=foreign_contact,
    )

    with patch.object(Message, "answer", new_callable=AsyncMock) as mock_ans:
        await process_contact(fraud_msg, state)
        mock_ans.assert_called_once()
        assert "faqat o'zingizning" in mock_ans.call_args[0][0]
        assert 123 not in mock_sheets

    # 2. Own contact
    own_contact = Contact(phone_number="+998901234567", first_name="Vali", user_id=123)
    own_msg = Message(
        message_id=11,
        date=1000,
        chat=chat,
        from_user=user,
        contact=own_contact,
    )
    with (
        patch.object(Message, "answer", new_callable=AsyncMock) as mock_ans,
        patch.object(Message, "bot", new_callable=AsyncMock),
    ):
        await process_contact(own_msg, state)
        mock_ans.assert_called_once()
        assert "muvaffaqiyatli" in mock_ans.call_args[0][0]
        assert 123 in mock_sheets
        assert mock_sheets[123].status == "active"
        assert mock_sheets[123].phone == "+998901234567"


@pytest.mark.asyncio
async def test_admin_race_condition_approval(mock_sheets):
    # Create pending agent
    mock_sheets[555] = Agent(telegram_id=555, name="Agent 555", status="pending", lang="uz")

    admin1 = User(id=1, is_bot=False, first_name="Admin One")
    chat = Chat(id=1, type="private")
    inner_msg = Message(message_id=100, date=1000, chat=chat, text="Yangi so'rov")

    cb1 = CallbackQuery(
        id="cb1",
        from_user=admin1,
        chat_instance="1",
        data="approve_agent:555",
        message=inner_msg,
    )

    with (
        patch.object(CallbackQuery, "answer", new_callable=AsyncMock) as ans1,
        patch.object(Message, "edit_text", new_callable=AsyncMock) as edit1,
        patch.object(CallbackQuery, "bot", new_callable=AsyncMock),
    ):
        await callback_approve_agent(cb1, role="admin")
        ans1.assert_called_with("Agent tasdiqlandi!")
        assert mock_sheets[555].status == "active"
        edit1.assert_called_once()

    # Second admin tries to approve the already approved agent
    admin2 = User(id=2, is_bot=False, first_name="Admin Two")
    cb2 = CallbackQuery(
        id="cb2",
        from_user=admin2,
        chat_instance="2",
        data="approve_agent:555",
        message=inner_msg,
    )

    with (
        patch.object(CallbackQuery, "answer", new_callable=AsyncMock) as ans2,
        patch.object(CallbackQuery, "bot", new_callable=AsyncMock),
    ):
        await callback_approve_agent(cb2, role="admin")
        ans2.assert_called_with("Bu so'rov allaqachon ko'rib chiqilgan!", show_alert=True)


@pytest.mark.asyncio
async def test_agent_vs_admin_keyboards_and_stats():
    from app.bot.handlers.stats import cmd_stats, cmd_top
    from app.bot.keyboards import get_main_menu

    # 1. Agent main menu must NOT contain statistics or admin panel
    agent_kb = get_main_menu(lang="uz", role="agent", webapp_url="https://example-live.com/app")
    all_buttons = [btn.text for row in agent_kb.keyboard for btn in row]
    assert "➕ Yangi do'kon" in all_buttons
    assert "📋 Mening yozuvlarim" in all_buttons
    assert "⚙️ Til" in all_buttons
    assert "📊 Statistika" not in all_buttons
    assert "🛠 Admin panel" not in all_buttons

    # 2. Superadmin/Admin main menu MUST contain statistics and admin panel
    admin_kb = get_main_menu(lang="uz", role="superadmin", webapp_url="https://example-live.com/app")
    admin_buttons = [btn.text for row in admin_kb.keyboard for btn in row]
    assert "📊 Statistika" in admin_buttons
    assert "🛠 Admin panel" in admin_buttons

    # 3. Agent calling /stats or /top gets restricted
    agent_user = User(id=777, is_bot=False, first_name="Agent User")
    chat = Chat(id=777, type="private")
    msg = Message(message_id=99, date=1000, chat=chat, from_user=agent_user, text="/stats")

    with patch.object(Message, "answer", new_callable=AsyncMock) as mock_ans:
        await cmd_stats(msg, role="agent", lang="uz")
        mock_ans.assert_called_once()
        assert "faqat Superadmin uchun" in mock_ans.call_args[0][0]

    with patch.object(Message, "answer", new_callable=AsyncMock) as mock_ans:
        await cmd_top(msg, role="agent", lang="uz")
        mock_ans.assert_called_once()
        assert "faqat Superadmin uchun" in mock_ans.call_args[0][0]


@pytest.mark.asyncio
async def test_unregistered_user_auto_prompt():
    from app.bot.middlewares import AccessMiddleware

    middleware = AccessMiddleware()
    handler = AsyncMock()

    user = User(id=888, is_bot=False, first_name="New User")
    chat = Chat(id=888, type="private")
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=888, user_id=888)
    state = FSMContext(storage=storage, key=key)

    msg = Message(message_id=1, date=1000, chat=chat, from_user=user, text="Salom")

    data = {
        "event_from_user": user,
        "role": "guest",
        "status": "unregistered",
        "lang": "uz",
        "state": state,
    }

    with patch.object(Message, "answer", new_callable=AsyncMock) as mock_ans:
        await middleware(handler, msg, data)
        # Should prompt with language selection directly
        mock_ans.assert_called_once()
        assert "tilni tanlang" in mock_ans.call_args[0][0].lower()
        current_state = await state.get_state()
        assert current_state == "RegistrationStates:waiting_for_lang"

