import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import get_settings

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Sheet Names
SHEET_STORES = "Do'konlar"
SHEET_VISITS = "Tashriflar"
SHEET_AGENTS = "Agentlar"
SHEET_LOG = "Log"
SHEET_SETTINGS = "Sozlamalar"
SHEET_STATS = "Statistika"

# Column structures (1-based headers)
STORES_HEADERS = [
    "ID", "Sana", "Vaqt", "Agent ID", "Agent ismi", "Do'kon nomi", "INN", "Telefon",
    "Viloyat", "Tuman", "Mahalla", "Lat", "Lon", "Xarita", "Rasm 1", "Rasm 2", "Rasm 3",
    "Holat", "Tahrirlangan vaqt", "Tahrir qilgan", "Rasm1 FileID", "Rasm2 FileID", "Rasm3 FileID"
]

VISITS_HEADERS = [
    "ID", "Do'kon ID", "Sana", "Vaqt", "Agent ID", "Agent ismi", "Lat", "Lon",
    "Rasm 1", "Rasm 2", "Rasm 3", "Rasm1 FileID", "Rasm2 FileID", "Rasm3 FileID"
]

AGENTS_HEADERS = [
    "Telegram ID", "Ism", "Telefon", "Username", "Til", "Rol", "Holat",
    "Ro'yxatdan o'tgan vaqt", "Kunlik reja", "Oxirgi faollik"
]

LOG_HEADERS = ["Vaqt", "Kim (ID)", "Kim (ism)", "Amal", "Obyekt", "Tafsilot"]
SETTINGS_HEADERS = ["Kalit", "Qiymat"]


def sanitize_cell(value: Any) -> str:
    """Protect against Google Sheets formula injection."""
    if value is None:
        return ""
    s = str(value)
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s
    return s


def make_hyperlink(url: str, label: str) -> str:
    """Create a safe HYPERLINK formula."""
    if not url:
        return ""
    safe_url = url.replace('"', '""')
    safe_label = label.replace('"', '""')
    return f'=HYPERLINK("{safe_url}","{safe_label}")'


def get_current_tashkent_time() -> datetime:
    return datetime.now(ZoneInfo("Asia/Tashkent"))


@dataclass
class Store:
    id: int = 0
    date: str = ""
    time: str = ""
    agent_id: int = 0
    agent_name: str = ""
    name: str = ""
    inn: str = ""
    phone: str = ""
    state: str = ""
    district: str = ""
    mahalla: str = ""
    lat: float = 0.0
    lon: float = 0.0
    map_link: str = ""
    photo1: str = ""
    photo2: str = ""
    photo3: str = ""
    status: str = "faol"  # 'faol' or 'o\'chirilgan'
    updated_at: str = ""
    updated_by: str = ""
    photo1_id: str = ""
    photo2_id: str = ""
    photo3_id: str = ""

    def to_row(self) -> list[str]:
        map_formula = make_hyperlink(f"https://www.google.com/maps?q={self.lat},{self.lon}", "📍 Xaritada")
        p1_formula = make_hyperlink(self.photo1, "🖼 Rasm 1") if self.photo1 else ""
        p2_formula = make_hyperlink(self.photo2, "🖼 Rasm 2") if self.photo2 else ""
        p3_formula = make_hyperlink(self.photo3, "🖼 Rasm 3") if self.photo3 else ""

        return [
            str(self.id),
            sanitize_cell(self.date),
            sanitize_cell(self.time),
            str(self.agent_id),
            sanitize_cell(self.agent_name),
            sanitize_cell(self.name),
            f"'{self.inn}",  # text format with leading apostrophe
            sanitize_cell(self.phone),
            sanitize_cell(self.state),
            sanitize_cell(self.district),
            sanitize_cell(self.mahalla),
            f"{self.lat:.6f}",
            f"{self.lon:.6f}",
            map_formula,
            p1_formula,
            p2_formula,
            p3_formula,
            sanitize_cell(self.status),
            sanitize_cell(self.updated_at),
            sanitize_cell(self.updated_by),
            sanitize_cell(self.photo1_id),
            sanitize_cell(self.photo2_id),
            sanitize_cell(self.photo3_id),
        ]

    @classmethod
    def from_row(cls, row: list[Any]) -> "Store":
        def get(idx: int, default: str = "") -> str:
            if idx < len(row):
                val = str(row[idx]).strip()
                if val.startswith("'"):
                    val = val[1:]
                return val
            return default

        try:
            sid = int(get(0, "0"))
        except ValueError:
            sid = 0

        try:
            aid = int(get(3, "0"))
        except ValueError:
            aid = 0

        try:
            lat = float(get(11, "0.0"))
        except ValueError:
            lat = 0.0

        try:
            lon = float(get(12, "0.0"))
        except ValueError:
            lon = 0.0

        return cls(
            id=sid,
            date=get(1),
            time=get(2),
            agent_id=aid,
            agent_name=get(4),
            name=get(5),
            inn=get(6),
            phone=get(7),
            state=get(8),
            district=get(9),
            mahalla=get(10),
            lat=lat,
            lon=lon,
            map_link=get(13),
            photo1=get(14),
            photo2=get(15),
            photo3=get(16),
            status=get(17, "faol") or "faol",
            updated_at=get(18),
            updated_by=get(19),
            photo1_id=get(20),
            photo2_id=get(21),
            photo3_id=get(22),
        )


@dataclass
class Visit:
    id: int = 0
    store_id: int = 0
    date: str = ""
    time: str = ""
    agent_id: int = 0
    agent_name: str = ""
    lat: float = 0.0
    lon: float = 0.0
    photo1: str = ""
    photo2: str = ""
    photo3: str = ""
    photo1_id: str = ""
    photo2_id: str = ""
    photo3_id: str = ""

    def to_row(self) -> list[str]:
        p1_formula = make_hyperlink(self.photo1, "🖼 Rasm 1") if self.photo1 else ""
        p2_formula = make_hyperlink(self.photo2, "🖼 Rasm 2") if self.photo2 else ""
        p3_formula = make_hyperlink(self.photo3, "🖼 Rasm 3") if self.photo3 else ""

        return [
            str(self.id),
            str(self.store_id),
            sanitize_cell(self.date),
            sanitize_cell(self.time),
            str(self.agent_id),
            sanitize_cell(self.agent_name),
            f"{self.lat:.6f}",
            f"{self.lon:.6f}",
            p1_formula,
            p2_formula,
            p3_formula,
            sanitize_cell(self.photo1_id),
            sanitize_cell(self.photo2_id),
            sanitize_cell(self.photo3_id),
        ]

    @classmethod
    def from_row(cls, row: list[Any]) -> "Visit":
        def get(idx: int, default: str = "") -> str:
            if idx < len(row):
                val = str(row[idx]).strip()
                if val.startswith("'"):
                    val = val[1:]
                return val
            return default

        try:
            vid = int(get(0, "0"))
        except ValueError:
            vid = 0

        try:
            sid = int(get(1, "0"))
        except ValueError:
            sid = 0

        try:
            aid = int(get(4, "0"))
        except ValueError:
            aid = 0

        try:
            lat = float(get(6, "0.0"))
        except ValueError:
            lat = 0.0

        try:
            lon = float(get(7, "0.0"))
        except ValueError:
            lon = 0.0

        return cls(
            id=vid,
            store_id=sid,
            date=get(2),
            time=get(3),
            agent_id=aid,
            agent_name=get(5),
            lat=lat,
            lon=lon,
            photo1=get(8),
            photo2=get(9),
            photo3=get(10),
            photo1_id=get(11),
            photo2_id=get(12),
            photo3_id=get(13),
        )


@dataclass
class Agent:
    telegram_id: int
    name: str = ""
    phone: str = ""
    username: str = ""
    lang: str = "uz"
    role: str = "agent"  # 'superadmin', 'admin', 'agent'
    status: str = "pending"  # 'pending', 'active', 'blocked'
    registered_at: str = ""
    daily_plan: int = 20
    last_active: str = ""

    def to_row(self) -> list[str]:
        return [
            str(self.telegram_id),
            sanitize_cell(self.name),
            sanitize_cell(self.phone),
            sanitize_cell(self.username),
            sanitize_cell(self.lang),
            sanitize_cell(self.role),
            sanitize_cell(self.status),
            sanitize_cell(self.registered_at),
            str(self.daily_plan),
            sanitize_cell(self.last_active),
        ]

    @classmethod
    def from_row(cls, row: list[Any]) -> "Agent":
        def get(idx: int, default: str = "") -> str:
            if idx < len(row):
                val = str(row[idx]).strip()
                if val.startswith("'"):
                    val = val[1:]
                return val
            return default

        try:
            tid = int(get(0, "0"))
        except ValueError:
            tid = 0

        try:
            plan = int(get(8, "20"))
        except ValueError:
            plan = 20

        return cls(
            telegram_id=tid,
            name=get(1),
            phone=get(2),
            username=get(3),
            lang=get(4, "uz") or "uz",
            role=get(5, "agent") or "agent",
            status=get(6, "pending") or "pending",
            registered_at=get(7),
            daily_plan=plan,
            last_active=get(9),
        )


@dataclass
class LogEntry:
    time: str
    user_id: int
    user_name: str
    action: str
    target: str
    details: str

    def to_row(self) -> list[str]:
        return [
            sanitize_cell(self.time),
            str(self.user_id),
            sanitize_cell(self.user_name),
            sanitize_cell(self.action),
            sanitize_cell(self.target),
            sanitize_cell(self.details),
        ]


class SheetsService:
    def __init__(self, credentials: Credentials | None = None):
        self._credentials = credentials
        self._service = None
        self._api_lock = asyncio.Semaphore(10)

        # Caching
        self._cache_stores: list[Store] | None = None
        self._cache_stores_time: float = 0.0
        self._fetching_stores: bool = False

        self._cache_visits: list[Visit] | None = None
        self._cache_visits_time: float = 0.0
        self._fetching_visits: bool = False

        self._cache_agents: dict[int, Agent] | None = None
        self._cache_agents_time: float = 0.0
        self._fetching_agents: bool = False

        self._cache_settings: dict[str, str] | None = None
        self._cache_settings_time: float = 0.0
        self._fetching_settings: bool = False

        self._cache_ttl = 600.0  # 10 minutes cache to prevent frequent API calls

        # Activity throttle: user_id -> last_updated_epoch
        self._activity_throttle: dict[int, float] = {}

        # Queue for writes
        self._write_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._refresher_task: asyncio.Task | None = None

    def start_worker(self):
        """Start the single sequential write worker and background cache refresher."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._process_write_queue())
        if self._refresher_task is None or self._refresher_task.done():
            self._refresher_task = asyncio.create_task(self._periodic_cache_refresher())

    async def stop_worker(self):
        """Stop the background write worker and cache refresher."""
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._refresher_task and not self._refresher_task.done():
            self._refresher_task.cancel()
            try:
                await self._refresher_task
            except asyncio.CancelledError:
                pass

    async def _periodic_cache_refresher(self):
        """Keep caches 100% fresh in background and prevent dead sockets."""
        while True:
            await asyncio.sleep(180)  # Every 3 minutes
            try:
                await self.warm_cache()
            except Exception as e:
                logger.debug(f"Periodic cache refresh notice: {e}")

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
                import google_auth_httplib2
                http = httplib2.Http(timeout=5)
                authorized_http = google_auth_httplib2.AuthorizedHttp(credentials=creds, http=http)
                self._service = build("sheets", "v4", http=authorized_http, cache_discovery=False)
            except Exception as e:
                logger.warning(f"Fallback to default build for Sheets service: {e}")
                self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return self._service

    async def _execute_with_retry(self, func, *args, **kwargs):
        """Execute a blocking Sheets operation with serialization lock and exponential retry."""
        async with self._api_lock:
            delays = [0.5, 1.0]
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
                        or "connection" in err_msg.lower()
                    )
                    if is_retryable and attempt <= len(delays):
                        logger.warning(
                            f"Sheets API call failed (attempt {attempt}), retrying in {delay}s: {e}"
                        )
                        self._service = None  # Reconnect fresh socket
                        await asyncio.sleep(delay)
                    else:
                        raise

    # ------------------ Invalidation ------------------
    def invalidate_stores_cache(self):
        self._cache_stores = None
        self._cache_stores_time = 0.0

    def invalidate_visits_cache(self):
        self._cache_visits = None
        self._cache_visits_time = 0.0

    def invalidate_agents_cache(self):
        self._cache_agents = None
        self._cache_agents_time = 0.0

    def invalidate_settings_cache(self):
        self._cache_settings = None
        self._cache_settings_time = 0.0

    # ------------------ Low-Level Sync Calls ------------------
    def _read_sheet_sync(self, sheet_name: str) -> list[list[Any]]:
        settings = get_settings()
        service = self._get_service()
        range_name = f"'{sheet_name}'!A2:Z"
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.SPREADSHEET_ID,
            range=range_name,
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute()
        return result.get("values", [])

    def _append_row_sync(self, sheet_name: str, row_values: list[Any]) -> None:
        settings = get_settings()
        service = self._get_service()
        range_name = f"'{sheet_name}'!A:A"
        body = {"values": [row_values]}
        service.spreadsheets().values().append(
            spreadsheetId=settings.SPREADSHEET_ID,
            range=range_name,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        ).execute()

    def _update_row_sync(self, sheet_name: str, row_index: int, row_values: list[Any]) -> None:
        settings = get_settings()
        service = self._get_service()
        range_name = f"'{sheet_name}'!A{row_index}:W{row_index}"
        body = {"values": [row_values]}
        service.spreadsheets().values().update(
            spreadsheetId=settings.SPREADSHEET_ID,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()

    # ------------------ Background Queue Worker ------------------
    async def _process_write_queue(self):
        while True:
            item = await self._write_queue.get()
            op, args, kwargs, future = item
            try:
                result = await op(*args, **kwargs)
                if not future.done():
                    future.set_result(result)
            except Exception as e:
                logger.error(f"Error executing queued write operation {op}: {e}", exc_info=True)
                if not future.done():
                    future.set_exception(e)
            finally:
                self._write_queue.task_done()

    async def _queue_write(self, op, *args, **kwargs):
        """Enqueue a write operation to ensure sequential execution."""
        future = asyncio.get_running_loop().create_future()
        await self._write_queue.put((op, args, kwargs, future))
        return await future

    # ------------------ High Level Store Methods ------------------
    async def _fetch_stores(self) -> list[Store]:
        if self._fetching_stores:
            return self._cache_stores or []
        self._fetching_stores = True
        try:
            raw_rows = await self._execute_with_retry(self._read_sheet_sync, SHEET_STORES)
            stores = [Store.from_row(r) for r in raw_rows if r and any(r)]
            self._cache_stores = stores
            self._cache_stores_time = time.time()
            return stores
        except Exception as e:
            logger.warning(f"Background fetch stores failed: {e}")
            return self._cache_stores or []
        finally:
            self._fetching_stores = False

    async def get_stores(self, include_deleted: bool = False) -> list[Store]:
        now = time.time()
        if self._cache_stores is not None:
            # Stale-while-revalidate: return instant in-memory cache, refresh in background if expired
            if (now - self._cache_stores_time) >= self._cache_ttl and not self._fetching_stores:
                asyncio.create_task(self._fetch_stores())
            stores = self._cache_stores
        else:
            stores = await self._fetch_stores()

        if include_deleted:
            return list(stores)
        return [s for s in stores if s.status == "faol"]

    async def get_store_by_id(self, store_id: int) -> Store | None:
        stores = await self.get_stores(include_deleted=True)
        for s in stores:
            if s.id == store_id:
                return s
        return None

    async def find_stores_by_inn(self, inn: str) -> list[Store]:
        clean_inn = inn.strip()
        stores = await self.get_stores(include_deleted=False)
        return [s for s in stores if s.inn.strip() == clean_inn]

    async def _append_store_internal(self, store: Store) -> Store:
        # Determine next ID safely inside sequential worker
        if self._cache_stores is not None and len(self._cache_stores) > 0:
            max_id = max((s.id for s in self._cache_stores), default=0)
        else:
            raw_rows = await self._execute_with_retry(self._read_sheet_sync, SHEET_STORES)
            max_id = 0
            for r in raw_rows:
                if r and len(r) > 0:
                    try:
                        val = int(str(r[0]).strip().lstrip("'"))
                        if val > max_id:
                            max_id = val
                    except ValueError:
                        pass
        store.id = max_id + 1

        now_t = get_current_tashkent_time()
        if not store.date:
            store.date = now_t.strftime("%Y-%m-%d")
        if not store.time:
            store.time = now_t.strftime("%H:%M:%S")

        await self._execute_with_retry(self._append_row_sync, SHEET_STORES, store.to_row())

        # Update in-memory cache directly for instant subsequent queries
        if self._cache_stores is not None:
            self._cache_stores.append(store)
            self._cache_stores_time = time.time()
        else:
            self.invalidate_stores_cache()

        # Log
        await self._append_log_internal(
            LogEntry(
                time=f"{store.date} {store.time}",
                user_id=store.agent_id,
                user_name=store.agent_name,
                action="YANGI_DOKON",
                target=f"Do'kon #{store.id}",
                details=f"Nom: {store.name}, INN: {store.inn}, Hudud: {store.state}/{store.district}/{store.mahalla}",
            )
        )
        return store

    async def append_store(self, store: Store) -> Store:
        return await self._queue_write(self._append_store_internal, store)

    async def _append_visit_internal(self, visit: Visit) -> Visit:
        if self._cache_visits is not None and len(self._cache_visits) > 0:
            max_id = max((v.id for v in self._cache_visits), default=0)
        else:
            raw_rows = await self._execute_with_retry(self._read_sheet_sync, SHEET_VISITS)
            max_id = 0
            for r in raw_rows:
                if r and len(r) > 0:
                    try:
                        val = int(str(r[0]).strip().lstrip("'"))
                        if val > max_id:
                            max_id = val
                    except ValueError:
                        pass
        visit.id = max_id + 1

        now_t = get_current_tashkent_time()
        if not visit.date:
            visit.date = now_t.strftime("%Y-%m-%d")
        if not visit.time:
            visit.time = now_t.strftime("%H:%M:%S")

        await self._execute_with_retry(self._append_row_sync, SHEET_VISITS, visit.to_row())

        # Update in-memory cache directly for instant subsequent queries
        if self._cache_visits is not None:
            self._cache_visits.append(visit)
            self._cache_visits_time = time.time()
        else:
            self.invalidate_visits_cache()

        await self._append_log_internal(
            LogEntry(
                time=f"{visit.date} {visit.time}",
                user_id=visit.agent_id,
                user_name=visit.agent_name,
                action="YANGI_TASHRIF",
                target=f"Tashrif #{visit.id} (Do'kon #{visit.store_id})",
                details=f"Do'kon ID: {visit.store_id}, Lat: {visit.lat}, Lon: {visit.lon}",
            )
        )
        return visit

    async def append_visit(self, visit: Visit) -> Visit:
        return await self._queue_write(self._append_visit_internal, visit)

    async def _fetch_visits(self) -> list[Visit]:
        if self._fetching_visits:
            return self._cache_visits or []
        self._fetching_visits = True
        try:
            raw_rows = await self._execute_with_retry(self._read_sheet_sync, SHEET_VISITS)
            visits = [Visit.from_row(r) for r in raw_rows if r and any(r)]
            self._cache_visits = visits
            self._cache_visits_time = time.time()
            return visits
        except Exception as e:
            logger.warning(f"Background fetch visits failed: {e}")
            return self._cache_visits or []
        finally:
            self._fetching_visits = False

    async def get_visits(self, store_id: int | None = None) -> list[Visit]:
        now = time.time()
        if self._cache_visits is not None:
            if (now - self._cache_visits_time) >= self._cache_ttl and not self._fetching_visits:
                asyncio.create_task(self._fetch_visits())
            visits = self._cache_visits
        else:
            visits = await self._fetch_visits()

        if store_id is not None:
            return [v for v in visits if v.store_id == store_id]
        return list(visits)

    async def _update_store_internal(
        self,
        store_id: int,
        updates: dict[str, Any],
        updated_by_id: int,
        updated_by_name: str,
    ) -> bool:
        raw_rows = await self._execute_with_retry(self._read_sheet_sync, SHEET_STORES)
        target_row_idx = None
        target_store: Store | None = None

        for idx, r in enumerate(raw_rows, start=2):
            if r and len(r) > 0:
                try:
                    sid = int(str(r[0]).strip().lstrip("'"))
                    if sid == store_id:
                        target_row_idx = idx
                        target_store = Store.from_row(r)
                        break
                except ValueError:
                    pass

        if not target_store or target_row_idx is None:
            return False

        # Apply updates
        for k, v in updates.items():
            if hasattr(target_store, k):
                setattr(target_store, k, v)

        now_str = get_current_tashkent_time().strftime("%Y-%m-%d %H:%M:%S")
        target_store.updated_at = now_str
        target_store.updated_by = f"{updated_by_name} ({updated_by_id})"

        await self._execute_with_retry(
            self._update_row_sync, SHEET_STORES, target_row_idx, target_store.to_row()
        )
        if self._cache_stores is not None:
            for idx, s in enumerate(self._cache_stores):
                if s.id == store_id:
                    self._cache_stores[idx] = target_store
                    break
        else:
            self.invalidate_stores_cache()

        await self._append_log_internal(
            LogEntry(
                time=now_str,
                user_id=updated_by_id,
                user_name=updated_by_name,
                action="TAHRIRLANGAN_DOKON",
                target=f"Do'kon #{store_id}",
                details=f"O'zgarishlar: {updates}",
            )
        )
        return True

    async def update_store_fields(
        self,
        store_id: int,
        updates: dict[str, Any],
        updated_by_id: int,
        updated_by_name: str,
    ) -> bool:
        return await self._queue_write(
            self._update_store_internal, store_id, updates, updated_by_id, updated_by_name
        )

    async def soft_delete_store(self, store_id: int, user_id: int, user_name: str) -> bool:
        return await self.update_store_fields(
            store_id=store_id,
            updates={"status": "o'chirilgan"},
            updated_by_id=user_id,
            updated_by_name=user_name,
        )

    async def _fetch_agents(self) -> dict[int, Agent]:
        if self._fetching_agents:
            return self._cache_agents or {}
        self._fetching_agents = True
        try:
            raw_rows = await self._execute_with_retry(self._read_sheet_sync, SHEET_AGENTS)
            agents: dict[int, Agent] = {}
            for r in raw_rows:
                if r and any(r):
                    ag = Agent.from_row(r)
                    if ag.telegram_id:
                        agents[ag.telegram_id] = ag
            self._cache_agents = agents
            self._cache_agents_time = time.time()
            return agents
        except Exception as e:
            logger.warning(f"Background fetch agents failed: {e}")
            return self._cache_agents or {}
        finally:
            self._fetching_agents = False

    async def get_agents(self) -> dict[int, Agent]:
        now = time.time()
        if self._cache_agents is not None:
            if (now - self._cache_agents_time) >= self._cache_ttl and not self._fetching_agents:
                asyncio.create_task(self._fetch_agents())
            return dict(self._cache_agents)
        else:
            agents = await self._fetch_agents()
            return dict(agents)

    async def get_agent_by_id(self, telegram_id: int) -> Agent | None:
        agents = await self.get_agents()
        return agents.get(telegram_id)

    async def warm_cache(self) -> None:
        """Pre-warm all caches in the background so bot responses are instant."""
        try:
            logger.info("Google Sheets cache pre-warming boshlanmoqda...")
            await asyncio.gather(
                self._fetch_agents(),
                self._fetch_settings(),
                self._fetch_stores(),
                self._fetch_visits(),
                return_exceptions=True,
            )
            logger.info("Google Sheets cache muvaffaqiyatli xotiraga yuklandi (pre-warmed).")
        except Exception as e:
            logger.warning(f"Cache pre-warming paytida xatolik: {e}")

    async def _upsert_agent_internal(self, agent: Agent) -> Agent:
        raw_rows = await self._execute_with_retry(self._read_sheet_sync, SHEET_AGENTS)
        target_row_idx = None
        for idx, r in enumerate(raw_rows, start=2):
            if r and len(r) > 0:
                try:
                    tid = int(str(r[0]).strip().lstrip("'"))
                    if tid == agent.telegram_id:
                        target_row_idx = idx
                        break
                except ValueError:
                    pass

        if target_row_idx is not None:
            await self._execute_with_retry(
                self._update_row_sync, SHEET_AGENTS, target_row_idx, agent.to_row()
            )
        else:
            if not agent.registered_at:
                agent.registered_at = get_current_tashkent_time().strftime("%Y-%m-%d %H:%M:%S")
            await self._execute_with_retry(self._append_row_sync, SHEET_AGENTS, agent.to_row())

        # Update in-memory cache directly so next lookup is instantaneous
        if self._cache_agents is not None:
            self._cache_agents[agent.telegram_id] = agent
            self._cache_agents_time = time.time()
        else:
            self.invalidate_agents_cache()
        return agent

    async def upsert_agent(self, agent: Agent) -> Agent:
        return await self._queue_write(self._upsert_agent_internal, agent)

    async def set_agent_status(
        self, telegram_id: int, status: str, admin_id: int, admin_name: str
    ) -> bool:
        agent = await self.get_agent_by_id(telegram_id)
        if not agent:
            return False
        agent.status = status
        await self.upsert_agent(agent)
        now_str = get_current_tashkent_time().strftime("%Y-%m-%d %H:%M:%S")
        await self.append_log(
            LogEntry(
                time=now_str,
                user_id=admin_id,
                user_name=admin_name,
                action="AGENT_HOLATI",
                target=f"Agent #{telegram_id} ({agent.name})",
                details=f"Yangi holat: {status}",
            )
        )
        return True

    async def set_agent_role(
        self, telegram_id: int, role: str, admin_id: int, admin_name: str
    ) -> bool:
        agent = await self.get_agent_by_id(telegram_id)
        if not agent:
            return False
        agent.role = role
        await self.upsert_agent(agent)
        now_str = get_current_tashkent_time().strftime("%Y-%m-%d %H:%M:%S")
        await self.append_log(
            LogEntry(
                time=now_str,
                user_id=admin_id,
                user_name=admin_name,
                action="AGENT_ROLI",
                target=f"Agent #{telegram_id} ({agent.name})",
                details=f"Yangi rol: {role}",
            )
        )
        return True

    async def set_agent_daily_plan(self, telegram_id: int, daily_plan: int) -> bool:
        agent = await self.get_agent_by_id(telegram_id)
        if not agent:
            return False
        agent.daily_plan = daily_plan
        await self.upsert_agent(agent)
        return True

    async def update_agent_activity(self, telegram_id: int) -> None:
        """Update last_active timestamp in memory, throttled to 1 hour for sheet write."""
        now = time.time()
        now_str = get_current_tashkent_time().strftime("%Y-%m-%d %H:%M:%S")

        # Always update in-memory cache instantly
        if self._cache_agents and telegram_id in self._cache_agents:
            self._cache_agents[telegram_id].last_active = now_str

        last = self._activity_throttle.get(telegram_id, 0.0)
        if now - last < 3600.0:
            return
        self._activity_throttle[telegram_id] = now

        agent = await self.get_agent_by_id(telegram_id)
        if agent:
            agent.last_active = now_str
            asyncio.create_task(self.upsert_agent(agent))

    # ------------------ High Level Log & Settings Methods ------------------
    async def _append_log_internal(self, entry: LogEntry) -> None:
        await self._execute_with_retry(self._append_row_sync, SHEET_LOG, entry.to_row())

    async def append_log(self, entry: LogEntry) -> None:
        await self._queue_write(self._append_log_internal, entry)

    async def _fetch_settings(self) -> dict[str, str]:
        if self._fetching_settings:
            return self._cache_settings or {}
        self._fetching_settings = True
        try:
            raw_rows = await self._execute_with_retry(self._read_sheet_sync, SHEET_SETTINGS)
            settings: dict[str, str] = {
                "admin_group_id": "",
                "daily_plan_default": "20",
                "report_time": "21:00",
                "notify_new_store": "1",
            }
            for r in raw_rows:
                if r and len(r) >= 2:
                    key = str(r[0]).strip()
                    val = str(r[1]).strip()
                    if val.startswith("'"):
                        val = val[1:]
                    settings[key] = val

            self._cache_settings = settings
            self._cache_settings_time = time.time()
            return settings
        except Exception as e:
            logger.warning(f"Background fetch settings failed: {e}")
            return self._cache_settings or {}
        finally:
            self._fetching_settings = False

    async def get_settings(self) -> dict[str, str]:
        now = time.time()
        if self._cache_settings is not None:
            if (now - self._cache_settings_time) >= self._cache_ttl and not self._fetching_settings:
                asyncio.create_task(self._fetch_settings())
            return dict(self._cache_settings)
        else:
            return await self._fetch_settings()

    async def get_setting(self, key: str, default: str = "") -> str:
        s = await self.get_settings()
        return s.get(key, default)

    async def _set_setting_internal(self, key: str, value: str) -> None:
        raw_rows = await self._execute_with_retry(self._read_sheet_sync, SHEET_SETTINGS)
        target_row_idx = None
        for idx, r in enumerate(raw_rows, start=2):
            if r and len(r) > 0:
                k = str(r[0]).strip()
                if k == key:
                    target_row_idx = idx
                    break

        row_data = [sanitize_cell(key), sanitize_cell(value)]
        if target_row_idx is not None:
            await self._execute_with_retry(
                self._update_row_sync, SHEET_SETTINGS, target_row_idx, row_data
            )
        else:
            await self._execute_with_retry(self._append_row_sync, SHEET_SETTINGS, row_data)

        self.invalidate_settings_cache()

    async def set_setting(self, key: str, value: str) -> None:
        await self._queue_write(self._set_setting_internal, key, value)


# Global singleton instance
sheets_service = SheetsService()
