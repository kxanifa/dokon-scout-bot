import asyncio
import io
import logging

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from app.config import get_settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


class DriveService:
    def __init__(self, credentials: Credentials | None = None):
        self._credentials = credentials
        self._service = None
        self._folder_cache: dict[str, str] = {}  # "parent_id/name" -> folder_id
        self._api_lock = asyncio.Lock()

    def _get_credentials(self) -> Credentials:
        if self._credentials:
            return self._credentials
        settings = get_settings()
        return Credentials(
            token=None,
            refresh_token=settings.GOOGLE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=SCOPES,
        )

    def _get_service(self):
        if self._service is None:
            creds = self._get_credentials()
            try:
                import httplib2
                http = httplib2.Http(timeout=20)
                http = creds.authorize(http)
                self._service = build("drive", "v3", http=http, cache_discovery=False)
            except Exception:
                self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    async def _execute_with_retry(self, func, *args, **kwargs):
        """Execute a blocking Drive operation with serialization lock and exponential retry."""
        async with self._api_lock:
            delays = [1, 2, 4]
            for attempt, delay in enumerate(delays, start=1):
                try:
                    return await asyncio.to_thread(func, *args, **kwargs)
                except Exception as e:
                    err_msg = str(e)
                    is_retryable = (
                        "429" in err_msg
                        or "500" in err_msg
                        or "503" in err_msg
                        or "timed out" in err_msg.lower()
                    )
                    if is_retryable and attempt < len(delays):
                        logger.warning(
                            f"Drive API call failed (attempt {attempt}), retrying in {delay}s: {e}"
                        )
                        if "timed out" in err_msg.lower():
                            self._service = None
                        await asyncio.sleep(delay)
                    else:
                        raise

    def _ensure_folder_sync(self, parent_id: str, folder_name: str) -> str:
        cache_key = f"{parent_id}/{folder_name}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        service = self._get_service()
        # Search existing folder
        q = f"'{parent_id}' in parents and name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        response = service.files().list(q=q, spaces="drive", fields="files(id, name)").execute()
        files = response.get("files", [])
        if files:
            folder_id = files[0]["id"]
            self._folder_cache[cache_key] = folder_id
            return folder_id

        # Create folder
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        folder = service.files().create(body=file_metadata, fields="id").execute()
        folder_id = folder.get("id")
        self._folder_cache[cache_key] = folder_id
        return folder_id

    async def ensure_folder(self, parent_id: str, folder_name: str) -> str:
        return await self._execute_with_retry(self._ensure_folder_sync, parent_id, folder_name)

    def _upload_image_sync(self, image_bytes: bytes, filename: str, month_str: str | None = None) -> tuple[str, str]:
        settings = get_settings()
        root_folder = settings.DRIVE_ROOT_FOLDER_ID
        if not root_folder:
            raise ValueError("DRIVE_ROOT_FOLDER_ID sozlanmagan.")

        # Ensure Rasmlar folder
        rasmlar_folder_id = self._ensure_folder_sync(root_folder, "Rasmlar")
        target_folder_id = rasmlar_folder_id
        if month_str:
            target_folder_id = self._ensure_folder_sync(rasmlar_folder_id, month_str)

        file_metadata = {
            "name": filename,
            "parents": [target_folder_id],
        }
        media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype="image/jpeg", resumable=True)
        service = self._get_service()
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink, webContentLink",
        ).execute()

        file_id = file.get("id")
        web_link = file.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")
        return file_id, web_link

    async def upload_image(self, image_bytes: bytes, filename: str, month_str: str | None = None) -> tuple[str, str]:
        return await self._execute_with_retry(self._upload_image_sync, image_bytes, filename, month_str)

    def _get_file_bytes_sync(self, file_id: str) -> bytes:
        service = self._get_service()
        request = service.files().get_media(fileId=file_id)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return file_buffer.getvalue()

    async def get_file_bytes(self, file_id: str) -> bytes:
        return await self._execute_with_retry(self._get_file_bytes_sync, file_id)

    def _copy_file_sync(self, file_id: str, new_name: str, parent_folder_id: str) -> str:
        service = self._get_service()
        copied_file = {"name": new_name, "parents": [parent_folder_id]}
        result = service.files().copy(fileId=file_id, body=copied_file, fields="id").execute()
        return result.get("id")

    async def copy_file(self, file_id: str, new_name: str, parent_folder_id: str) -> str:
        return await self._execute_with_retry(self._copy_file_sync, file_id, new_name, parent_folder_id)

    def _delete_old_backups_sync(self, backup_folder_id: str, keep_count: int = 8) -> int:
        service = self._get_service()
        q = f"'{backup_folder_id}' in parents and name contains 'Zaxira_' and trashed = false"
        response = service.files().list(
            q=q,
            spaces="drive",
            fields="files(id, name, createdTime)",
            orderBy="createdTime desc",
        ).execute()
        files = response.get("files", [])
        deleted = 0
        if len(files) > keep_count:
            to_delete = files[keep_count:]
            for item in to_delete:
                try:
                    service.files().delete(fileId=item["id"]).execute()
                    deleted += 1
                except Exception as e:
                    logger.warning(f"Error deleting old backup {item['name']}: {e}")
        return deleted

    async def delete_old_backups(self, backup_folder_id: str, keep_count: int = 8) -> int:
        return await self._execute_with_retry(self._delete_old_backups_sync, backup_folder_id, keep_count)


# Global singleton instance
drive_service = DriveService()
