from unittest.mock import AsyncMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage, StorageKey
from aiogram.types import CallbackQuery, Chat, Location, Message, User

from app.bot.handlers.my_records import callback_edit_store
from app.bot.handlers.store_flow import process_inn, process_location
from app.bot.states import StoreFlowStates
from app.services.geocode import parse_address
from app.services.sheets import Agent, Store, sheets_service
from app.services.stats import (
    generate_progress_bar,
    get_agent_stats,
    get_tashkent_now,
    get_top_ranking,
)
from app.utils.validators import normalize_phone, validate_inn, validate_store_name


def test_parse_address_fixtures():
    # 1. Tashkent city fixture
    tashkent_data = {
        "address": {
            "city": "Tashkent",
            "county": "Chilonzor tumani",
            "suburb": "1-mavze",
            "country": "Uzbekistan",
        }
    }
    parsed = parse_address(tashkent_data)
    assert parsed["state"] == "Toshkent shahri"
    assert parsed["district"] == "Chilonzor tumani"
    assert parsed["mahalla"] == "1-mavze"

    # 2. Tashkent region with district
    tashkent_region_data = {
        "address": {
            "state": "Ташкентская область",
            "county": "Bo'stonliq tumani",
            "village": "G'azalkent",
            "country": "Uzbekistan",
        }
    }
    parsed2 = parse_address(tashkent_region_data)
    assert parsed2["state"] == "Toshkent viloyati"
    assert parsed2["district"] == "Bo'stonliq tumani"
    assert parsed2["mahalla"] == "G'azalkent"

    # 3. Missing mahalla
    no_mahalla_data = {
        "address": {
            "state": "Samarqand viloyati",
            "county": "Urgut tumani",
        }
    }
    parsed3 = parse_address(no_mahalla_data)
    assert parsed3["state"] == "Samarqand viloyati"
    assert parsed3["district"] == "Urgut tumani"
    assert parsed3["mahalla"] == ""

    # 4. Empty / corrupted data
    assert parse_address({}) == {"state": "", "district": "", "mahalla": ""}
    assert parse_address(None) == {"state": "", "district": "", "mahalla": ""}


def test_validators():
    # INN
    assert validate_inn("123456789") == (True, "123456789")
    assert validate_inn(" 123 456 789 ") == (True, "123456789")
    assert validate_inn("123-456-789") == (True, "123456789")
    assert validate_inn("12345") == (False, "")
    assert validate_inn("1234567890") == (False, "")
    assert validate_inn("abcdefghi") == (False, "")

    # Phone normalization
    assert normalize_phone("901234567") == (True, "+998901234567")
    assert normalize_phone("998901234567") == (True, "+998901234567")
    assert normalize_phone("+998 90 123-45-67") == (True, "+998901234567")
    assert normalize_phone("(90) 123 45 67") == (True, "+998901234567")
    assert normalize_phone("") == (True, "")
    assert normalize_phone(None) == (True, "")
    assert normalize_phone("123") == (False, "")
    assert normalize_phone("invalid_phone") == (False, "")

    # Store name
    assert validate_store_name("Al-Baraka") == (True, "Al-Baraka")
    assert validate_store_name("A") == (False, "")
    assert validate_store_name("A" * 101) == (False, "")


def test_progress_bar():
    assert generate_progress_bar(0, 20) == "░░░░░░░░░░"
    assert generate_progress_bar(10, 20) == "▓▓▓▓▓░░░░░"
    assert generate_progress_bar(20, 20) == "▓▓▓▓▓▓▓▓▓▓"
    assert generate_progress_bar(25, 20) == "▓▓▓▓▓▓▓▓▓▓"


@pytest.mark.asyncio
async def test_forwarded_location_rejected():
    chat = Chat(id=1, type="private")
    user = User(id=1, is_bot=False, first_name="Agent")
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    state = FSMContext(storage=storage, key=key)

    msg = Message(
        message_id=1,
        date=1000,
        chat=chat,
        from_user=user,
        location=Location(latitude=41.28, longitude=69.20),
        forward_date=999,
    )

    with patch.object(Message, "answer", new_callable=AsyncMock) as mock_ans:
        await process_location(msg, state, lang="uz")
        mock_ans.assert_called_once()
        assert "Forward qilingan" in mock_ans.call_args[0][0]


@pytest.mark.asyncio
async def test_duplicate_inn_flow():
    existing_store = Store(
        id=15,
        name="Mavjud Do'kon",
        inn="987654321",
        date="2026-10-01",
        time="10:00:00",
        agent_name="Eski Agent",
    )

    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=1, user_id=1)
    state = FSMContext(storage=storage, key=key)

    chat = Chat(id=1, type="private")
    user = User(id=1, is_bot=False, first_name="Agent")
    msg = Message(message_id=2, date=1000, chat=chat, from_user=user, text="987654321")

    with (
        patch.object(sheets_service, "find_stores_by_inn", return_value=[existing_store]),
        patch.object(Message, "answer", new_callable=AsyncMock) as mock_ans,
    ):
        await process_inn(msg, state, lang="uz")
        mock_ans.assert_called_once()
        assert "Bu INN avval kiritilgan" in mock_ans.call_args[0][0]
        current_state = await state.get_state()
        assert current_state == StoreFlowStates.duplicate_inn_decision.state


@pytest.mark.asyncio
async def test_records_ownership_security():
    other_store = Store(
        id=99,
        agent_id=888,  # Different agent
        name="Begona Do'kon",
    )

    chat = Chat(id=1, type="private")
    user = User(id=777, is_bot=False, first_name="Attacker")
    cb = CallbackQuery(
        id="cb_test",
        from_user=user,
        chat_instance="1",
        data="edit_store:99",
        message=Message(message_id=5, date=1000, chat=chat, text="Card"),
    )

    with (
        patch.object(sheets_service, "get_store_by_id", return_value=other_store),
        patch.object(CallbackQuery, "answer", new_callable=AsyncMock) as mock_ans,
    ):
        await callback_edit_store(cb, lang="uz")
        mock_ans.assert_called_once()
        assert "faqat o'zingiz kiritgan" in mock_ans.call_args[0][0]


@pytest.mark.asyncio
async def test_stats_and_ranking():
    today_str = get_tashkent_now().strftime("%Y-%m-%d")
    stores = [
        Store(id=1, agent_id=10, agent_name="Agent 10", date=today_str, status="faol"),
        Store(id=2, agent_id=10, agent_name="Agent 10", date=today_str, status="faol"),
        Store(id=3, agent_id=20, agent_name="Agent 20", date=today_str, status="faol"),
    ]
    agents = {
        10: Agent(telegram_id=10, name="Agent 10", daily_plan=20),
        20: Agent(telegram_id=20, name="Agent 20", daily_plan=20),
    }

    with (
        patch.object(sheets_service, "get_stores", return_value=stores),
        patch.object(sheets_service, "get_visits", return_value=[]),
        patch.object(sheets_service, "get_agents", return_value=agents),
    ):
        stats_10 = await get_agent_stats(10, daily_plan=20)
        assert stats_10["today"] == 2
        assert stats_10["total"] == 2

        ranking = await get_top_ranking(period="day", my_agent_id=10)
        assert ranking["my_rank"] == 1
        assert ranking["my_count"] == 2
        assert "🥇 Agent 10: 2 ta" in ranking["ranking_text"]
