import logging

from app.config import get_settings
from app.services.drive import drive_service
from app.services.sheets import LogEntry, get_current_tashkent_time, sheets_service

logger = logging.getLogger(__name__)


async def create_weekly_backup(spreadsheet_id: str, drive_root_folder_id: str) -> str:
    """
    Create a backup copy of the Google Spreadsheet in 'Zaxira/' folder:
    - Named 'Zaxira_YYYY-MM-DD'
    - Deletes older backups keeping the most recent 8 copies
    - Logs to Log sheet
    """
    now_t = get_current_tashkent_time()
    backup_name = f"Zaxira_{now_t.strftime('%Y-%m-%d')}"

    # Ensure 'Zaxira' folder inside root
    zaxira_folder_id = await drive_service.ensure_folder(drive_root_folder_id, "Zaxira")

    # Copy spreadsheet file
    new_file_id = await drive_service.copy_file(
        file_id=spreadsheet_id,
        new_name=backup_name,
        parent_folder_id=zaxira_folder_id,
    )

    # Clean up old backups (keep 8)
    deleted_count = await drive_service.delete_old_backups(zaxira_folder_id, keep_count=8)

    now_str = now_t.strftime("%Y-%m-%d %H:%M:%S")
    await sheets_service.append_log(
        LogEntry(
            time=now_str,
            user_id=0,
            user_name="SISTEMA",
            action="ZAXIRA_YARATILDI",
            target=backup_name,
            details=f"Fayl ID: {new_file_id}, Eskilar o'chirildi: {deleted_count} ta",
        )
    )

    logger.info(f"Spreadsheet zaxira nusxasi yaratildi: {backup_name} (ID: {new_file_id})")
    return new_file_id


async def run_backup_job(bot=None) -> bool:
    """Scheduled or manual trigger for backup job."""
    settings = get_settings()
    if not settings.SPREADSHEET_ID or not settings.DRIVE_ROOT_FOLDER_ID:
        logger.warning("Zaxira olinmadi: SPREADSHEET_ID yoki DRIVE_ROOT_FOLDER_ID sozlanmagan.")
        return False

    try:
        new_file_id = await create_weekly_backup(
            spreadsheet_id=settings.SPREADSHEET_ID,
            drive_root_folder_id=settings.DRIVE_ROOT_FOLDER_ID,
        )
        return bool(new_file_id)
    except Exception as e:
        logger.error(f"Zaxira olishda xatolik: {e}", exc_info=True)
        if bot and settings.SUPERADMIN_ID:
            try:
                await bot.send_message(
                    chat_id=settings.SUPERADMIN_ID,
                    text=f"⚠️ <b>Haftalik zaxira olishda xatolik yuz berdi:</b>\n\n<code>{str(e)[:200]}</code>",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        return False
