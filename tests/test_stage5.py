from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import Chat, Message, User

from app.bot.handlers.admin import cmd_backup_now, cmd_report_now
from app.config import get_settings
from app.services.backup import create_weekly_backup
from app.services.notify import send_daily_report
from app.services.sheets import Agent, Store, Visit, sheets_service


@pytest.fixture
def sample_data():
    stores = [
        Store(id=1, name="Do'kon 1", date="2026-10-01", agent_id=10, agent_name="Ali", status="faol"),
        Store(id=2, name="Do'kon 2", date="2026-10-01", agent_id=10, agent_name="Ali", status="faol"),
        Store(id=3, name="Do'kon 3", date="2026-10-01", agent_id=20, agent_name="Vali", status="faol"),
    ]
    visits = [
        Visit(id=1, store_id=1, date="2026-10-01", agent_id=10, agent_name="Ali"),
    ]
    agents = {
        10: Agent(telegram_id=10, name="Ali", role="agent", status="active", daily_plan=20),
        20: Agent(telegram_id=20, name="Vali", role="agent", status="active", daily_plan=20),
        99: Agent(telegram_id=99, name="Admin Sherali", role="admin", status="active", lang="uz"),
    }
    settings_dict = {
        "report_time": "21:00",
        "last_report_date": "",
    }
    return stores, visits, agents, settings_dict


@pytest.mark.asyncio
async def test_send_daily_report_and_duplicate_prevention(sample_data):
    stores, visits, agents, settings_dict = sample_data
    mock_bot = AsyncMock()

    async def mock_get_setting(k, default=""):
        return settings_dict.get(k, default)

    async def mock_set_setting(k, v):
        settings_dict[k] = v

    with (
        patch.object(sheets_service, "get_stores", return_value=stores),
        patch.object(sheets_service, "get_visits", return_value=visits),
        patch.object(sheets_service, "get_agents", return_value=agents),
        patch.object(sheets_service, "get_setting", side_effect=mock_get_setting),
        patch.object(sheets_service, "set_setting", side_effect=mock_set_setting),
    ):
        # 1. First run -> sends successfully
        success = await send_daily_report(mock_bot, force=False)
        assert success is True
        mock_bot.send_message.assert_called()
        assert settings_dict["last_report_date"] != ""

        # 2. Second run without force -> skipped (duplicate prevention)
        mock_bot.send_message.reset_mock()
        second_run = await send_daily_report(mock_bot, force=False)
        assert second_run is False
        mock_bot.send_message.assert_not_called()

        # 3. Third run with force=True -> sends again
        force_run = await send_daily_report(mock_bot, force=True)
        assert force_run is True
        mock_bot.send_message.assert_called()


@pytest.mark.asyncio
async def test_create_weekly_backup():
    with (
        patch("app.services.drive.drive_service.ensure_folder", return_value="folder_zaxira_id"),
        patch("app.services.drive.drive_service.copy_file", return_value="backup_copy_id_123"),
        patch("app.services.drive.drive_service.delete_old_backups", return_value=2),
        patch.object(sheets_service, "append_log", new_callable=AsyncMock) as mock_log,
    ):
        file_id = await create_weekly_backup("sheet_123", "root_folder_123")
        assert file_id == "backup_copy_id_123"
        mock_log.assert_called_once()
        assert mock_log.call_args[0][0].action == "ZAXIRA_YARATILDI"


@pytest.mark.asyncio
async def test_manual_admin_commands():
    settings = get_settings()
    superadmin_id = settings.SUPERADMIN_ID

    chat = Chat(id=superadmin_id, type="private")
    user = User(id=superadmin_id, is_bot=False, first_name="SuperAdmin")

    msg_report = Message(message_id=1, date=1000, chat=chat, from_user=user, text="/report_now")
    msg_backup = Message(message_id=2, date=1000, chat=chat, from_user=user, text="/backup_now")

    with (
        patch.object(Message, "bot", new_callable=AsyncMock),
        patch("app.bot.handlers.admin.send_daily_report", return_value=True),
        patch("app.bot.handlers.admin.run_backup_job", return_value=True),
        patch.object(Message, "answer", new_callable=AsyncMock) as mock_ans,
    ):
        await cmd_report_now(msg_report)
        assert any("yuborildi" in call[0][0] for call in mock_ans.call_args_list)

        mock_ans.reset_mock()
        await cmd_backup_now(msg_backup)
        assert any("Zaxira nusxasi" in call[0][0] for call in mock_ans.call_args_list)


def test_sheets_time_and_date_normalization():
    from app.services.sheets import normalize_date_str, normalize_time_str

    # Test time normalization (fractions from Google Sheets vs HH:MM)
    assert normalize_time_str("0.875") == "21:00"
    assert normalize_time_str("0.5") == "12:00"
    assert normalize_time_str("21:00") == "21:00"
    assert normalize_time_str("9:30") == "09:30"
    assert normalize_time_str(None) == "21:00"

    # Test date normalization (serial days from Google Sheets vs YYYY-MM-DD)
    assert normalize_date_str("46298") == "2026-10-03"
    assert normalize_date_str("2026-10-03") == "2026-10-03"
    assert normalize_date_str("") == ""

