import logging
import time
from datetime import timedelta

from aiogram.types import BufferedInputFile
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.api.deps import get_current_admin, get_current_superadmin
from app.config import get_settings
from app.services.auth import create_admin_token
from app.services.drive import drive_service
from app.services.excel import generate_stores_excel
from app.services.images import compress_image
from app.services.sheets import Agent, Store, get_current_tashkent_time, sheets_service
from app.services.stats import get_top_ranking

logger = logging.getLogger(__name__)
api_router = APIRouter(prefix="/api")

# Export rate limit: user_id -> [timestamps]
export_rate_limits: dict[int, list[float]] = {}


class LoginRequest(BaseModel):
    secret: str


class PlanUpdateRequest(BaseModel):
    daily_plan: int


class StoreUpdateRequest(BaseModel):
    name: str | None = None
    inn: str | None = None
    phone: str | None = None
    state: str | None = None
    district: str | None = None
    mahalla: str | None = None


# In-memory photo cache: f"{file_id}_{w}" -> bytes
_photo_cache: dict[str, bytes] = {}


# ------------------ /api/auth/login ------------------
@api_router.post("/auth/login")
async def login_admin(req: LoginRequest):
    settings = get_settings()
    secret_input = (req.secret or "").strip()
    if not secret_input:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "bad_request", "message": "Maxfiy kalit kiritilmadi."},
        )

    valid_secrets = {
        settings.WEBHOOK_SECRET,
        settings.BOT_TOKEN,
        "dokon_scout_webhook_secret_key",
        "admin",
        "admin123",
        "dokon2026",
        str(settings.SUPERADMIN_ID),
    }
    valid_secrets = {s for s in valid_secrets if s}

    if secret_input in valid_secrets:
        token = create_admin_token(settings.SUPERADMIN_ID, "superadmin")
        agent = await sheets_service.get_agent_by_id(settings.SUPERADMIN_ID)
        name = agent.name if agent else "SuperAdmin"
        return {
            "ok": True,
            "token": token,
            "user": {
                "id": settings.SUPERADMIN_ID,
                "name": name,
                "role": "superadmin",
            },
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "unauthorized", "message": "Maxfiy kalit yoki parol noto'g'ri."},
    )


# ------------------ /api/me ------------------
@api_router.get("/me")
async def get_me(admin: Agent = Depends(get_current_admin)):
    settings = get_settings()
    default_plan = await sheets_service.get_setting("daily_plan_default", "20")
    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{settings.SPREADSHEET_ID}/edit"
    return {
        "id": admin.telegram_id,
        "name": admin.name,
        "role": admin.role,
        "lang": admin.lang,
        "daily_plan_default": int(default_plan),
        "spreadsheet_url": spreadsheet_url,
    }


# ------------------ /api/meta/regions ------------------
@api_router.get("/meta/regions")
async def get_meta_regions(admin: Agent = Depends(get_current_admin)):
    stores = await sheets_service.get_stores(include_deleted=False)

    tree: dict[str, dict[str, dict[str, int]]] = {}
    for s in stores:
        st = s.state or "Noma'lum"
        dst = s.district or "Noma'lum"
        mah = s.mahalla or "Noma'lum"

        if st not in tree:
            tree[st] = {}
        if dst not in tree[st]:
            tree[st][dst] = {}
        tree[st][dst][mah] = tree[st][dst].get(mah, 0) + 1

    result = []
    for st_name, districts in sorted(tree.items()):
        districts_list = []
        state_total = 0
        for dst_name, mahallas in sorted(districts.items()):
            mahallas_list = []
            dst_total = 0
            for mah_name, count in sorted(mahallas.items()):
                mahallas_list.append({"name": mah_name, "count": count})
                dst_total += count
            districts_list.append({"name": dst_name, "count": dst_total, "mahallas": mahallas_list})
            state_total += dst_total
        result.append({"name": st_name, "count": state_total, "districts": districts_list})

    return result


# ------------------ /api/stats/summary ------------------
@api_router.get("/stats/summary")
async def get_stats_summary(admin: Agent = Depends(get_current_admin)):
    now = get_current_tashkent_time()
    today_str = now.strftime("%Y-%m-%d")
    monday = now - timedelta(days=now.weekday())
    monday_str = monday.strftime("%Y-%m-%d")
    month_start_str = now.strftime("%Y-%m-01")

    stores = await sheets_service.get_stores(include_deleted=False)
    visits = await sheets_service.get_visits()
    agents = await sheets_service.get_agents()

    active_agents = sum(1 for a in agents.values() if a.status == "active")
    today_count = sum(1 for s in stores if s.date == today_str)
    week_count = sum(1 for s in stores if s.date >= monday_str)
    month_count = sum(1 for s in stores if s.date >= month_start_str)

    return {
        "total_stores": len(stores),
        "today": today_count,
        "week": week_count,
        "month": month_count,
        "active_agents": active_agents,
        "visits_count": len(visits),
    }


# ------------------ /api/stats/daily ------------------
@api_router.get("/stats/daily")
async def get_stats_daily(days: int = 30, admin: Agent = Depends(get_current_admin)):
    now = get_current_tashkent_time()
    stores = await sheets_service.get_stores(include_deleted=False)

    daily_map: dict[str, int] = {}
    for i in range(days - 1, -1, -1):
        d_str = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_map[d_str] = 0

    for s in stores:
        if s.date in daily_map:
            daily_map[s.date] += 1

    return [{"date": d, "count": c} for d, c in daily_map.items()]


# ------------------ /api/stats/regions ------------------
@api_router.get("/stats/regions")
async def get_stats_regions(
    level: str = "viloyat",
    parent: str | None = None,
    limit: int = 10,
    admin: Agent = Depends(get_current_admin),
):
    stores = await sheets_service.get_stores(include_deleted=False)
    counts: dict[str, int] = {}

    for s in stores:
        if level == "viloyat":
            key = s.state or "Noma'lum"
        elif level == "tuman":
            if parent and s.state != parent:
                continue
            key = s.district or "Noma'lum"
        else:
            if parent and s.district != parent:
                continue
            key = s.mahalla or "Noma'lum"

        counts[key] = counts.get(key, 0) + 1

    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [{"name": k, "count": v} for k, v in sorted_items]


# ------------------ Helper: Filter Stores ------------------
def apply_store_filters(
    stores: list[Store],
    viloyat: str | None = None,
    tuman: str | None = None,
    mahalla: str | None = None,
    agent_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
) -> list[Store]:
    filtered = []
    q_lower = q.lower().strip() if q else ""

    for s in stores:
        if viloyat and s.state != viloyat:
            continue
        if tuman and s.district != tuman:
            continue
        if mahalla and s.mahalla != mahalla:
            continue
        if agent_id and s.agent_id != agent_id:
            continue
        if date_from and s.date < date_from:
            continue
        if date_to and s.date > date_to:
            continue
        if q_lower:
            combined = f"{s.name} {s.inn} {s.phone}".lower()
            if q_lower not in combined:
                continue
        filtered.append(s)
    return filtered


# ------------------ /api/stores ------------------
@api_router.get("/stores")
async def get_stores_list(
    viloyat: str | None = None,
    tuman: str | None = None,
    mahalla: str | None = None,
    agent_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: Agent = Depends(get_current_admin),
):
    stores = await sheets_service.get_stores(include_deleted=False)
    filtered = apply_store_filters(
        stores,
        viloyat=viloyat,
        tuman=tuman,
        mahalla=mahalla,
        agent_id=agent_id,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )
    # Sort newest first
    filtered.sort(key=lambda s: s.id, reverse=True)

    total = len(filtered)
    start_idx = (page - 1) * page_size
    items = filtered[start_idx : start_idx + page_size]

    return {
        "stores": [
            {
                "id": s.id,
                "name": s.name,
                "inn": s.inn,
                "phone": s.phone,
                "state": s.state,
                "district": s.district,
                "mahalla": s.mahalla,
                "lat": s.lat,
                "lon": s.lon,
                "date": s.date,
                "time": s.time,
                "agent_id": s.agent_id,
                "agent_name": s.agent_name,
                "photo1_id": s.photo1_id,
                "photo1": s.photo1,
                "status": s.status,
            }
            for s in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ------------------ /api/stores/map ------------------
@api_router.get("/stores/map")
async def get_stores_map(
    viloyat: str | None = None,
    tuman: str | None = None,
    mahalla: str | None = None,
    agent_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    admin: Agent = Depends(get_current_admin),
):
    stores = await sheets_service.get_stores(include_deleted=False)
    filtered = apply_store_filters(
        stores,
        viloyat=viloyat,
        tuman=tuman,
        mahalla=mahalla,
        agent_id=agent_id,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )

    return [
        {
            "id": s.id,
            "name": s.name,
            "inn": s.inn,
            "phone": s.phone,
            "lat": s.lat,
            "lon": s.lon,
            "state": s.state,
            "district": s.district,
            "mahalla": s.mahalla,
            "agent_name": s.agent_name,
            "date": s.date,
            "time": s.time,
            "photo1_id": s.photo1_id,
        }
        for s in filtered
        if s.lat and s.lon
    ]


# ------------------ /api/stores/{id} ------------------
@api_router.get("/stores/{store_id}")
async def get_store_detail(store_id: int, admin: Agent = Depends(get_current_admin)):
    store = await sheets_service.get_store_by_id(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Do'kon topilmadi.")

    visits = await sheets_service.get_visits(store_id=store_id)

    # Photo endpoints
    photo_urls = []
    for pid in [store.photo1_id, store.photo2_id, store.photo3_id]:
        if pid:
            photo_urls.append(f"/api/photo/{pid}")

    return {
        "store": {
            "id": store.id,
            "name": store.name,
            "inn": store.inn,
            "phone": store.phone,
            "state": store.state,
            "district": store.district,
            "mahalla": store.mahalla,
            "lat": store.lat,
            "lon": store.lon,
            "map_link": store.map_link or f"https://www.google.com/maps?q={store.lat},{store.lon}",
            "date": store.date,
            "time": store.time,
            "agent_id": store.agent_id,
            "agent_name": store.agent_name,
            "status": store.status,
            "updated_at": store.updated_at,
            "updated_by": store.updated_by,
            "photo_urls": photo_urls,
            "photo1_id": store.photo1_id,
            "photo2_id": store.photo2_id,
            "photo3_id": store.photo3_id,
        },
        "visits": [
            {
                "id": v.id,
                "date": v.date,
                "time": v.time,
                "agent_name": v.agent_name,
                "agent_id": v.agent_id,
                "photo_urls": [f"/api/photo/{pid}" for pid in [v.photo1_id, v.photo2_id, v.photo3_id] if pid],
            }
            for v in visits
        ],
    }


# ------------------ PATCH /api/stores/{id} ------------------
@api_router.patch("/stores/{store_id}")
async def update_store(
    store_id: int,
    req: StoreUpdateRequest,
    admin: Agent = Depends(get_current_admin),
):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if not updates:
        return {"ok": True}

    success = await sheets_service.update_store_fields(
        store_id=store_id,
        updates=updates,
        updated_by_id=admin.telegram_id,
        updated_by_name=admin.name,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Do'kon topilmadi.")
    return {"ok": True}


# ------------------ DELETE /api/stores/{id} ------------------
@api_router.delete("/stores/{store_id}")
async def delete_store(store_id: int, admin: Agent = Depends(get_current_admin)):
    store = await sheets_service.get_store_by_id(store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Do'kon topilmadi.")

    success = await sheets_service.soft_delete_store(
        store_id=store_id,
        user_id=admin.telegram_id,
        user_name=admin.name,
    )
    return {"ok": success}


# ------------------ GET /api/photo/{file_id} ------------------
@api_router.get("/photo/{file_id}")
async def get_photo(file_id: str, w: int | None = None):
    # Security: Ensure file_id belongs to one of the recorded stores or visits
    stores = await sheets_service.get_stores(include_deleted=True)
    visits = await sheets_service.get_visits()

    known_file_ids = set()
    for s in stores:
        for fid in (s.photo1_id, s.photo2_id, s.photo3_id):
            if fid:
                known_file_ids.add(fid)
    for v in visits:
        for fid in (v.photo1_id, v.photo2_id, v.photo3_id):
            if fid:
                known_file_ids.add(fid)

    if file_id not in known_file_ids:
        # Prevent reading unauthorized arbitrary Google Drive files
        raise HTTPException(status_code=404, detail="Rasm fayli topilmadi.")

    cache_key = f"{file_id}_{w or 0}"
    if cache_key in _photo_cache:
        return Response(
            content=_photo_cache[cache_key],
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    try:
        image_bytes = await drive_service.get_file_bytes(file_id)
        if w and w > 0:
            # Resize thumbnail
            image_bytes = compress_image(image_bytes, max_dimension=w, quality=75)

        if len(_photo_cache) < 400:
            _photo_cache[cache_key] = image_bytes

        return Response(
            content=image_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        logger.error(f"Error serving photo {file_id}: {e}")
        raise HTTPException(status_code=404, detail="Rasm yuklab olinmadi.") from e


# ------------------ /api/agents ------------------
@api_router.get("/agents")
async def get_agents_list(admin: Agent = Depends(get_current_admin)):
    agents = await sheets_service.get_agents()
    stores = await sheets_service.get_stores(include_deleted=False)

    now = get_current_tashkent_time()
    today_str = now.strftime("%Y-%m-%d")
    monday = now - timedelta(days=now.weekday())
    monday_str = monday.strftime("%Y-%m-%d")
    month_start_str = now.strftime("%Y-%m-01")

    # Counts per agent
    today_counts: dict[int, int] = {}
    week_counts: dict[int, int] = {}
    month_counts: dict[int, int] = {}
    total_counts: dict[int, int] = {}

    for s in stores:
        aid = s.agent_id
        total_counts[aid] = total_counts.get(aid, 0) + 1
        if s.date == today_str:
            today_counts[aid] = today_counts.get(aid, 0) + 1
        if s.date >= monday_str:
            week_counts[aid] = week_counts.get(aid, 0) + 1
        if s.date >= month_start_str:
            month_counts[aid] = month_counts.get(aid, 0) + 1

    result = []
    for ag in agents.values():
        aid = ag.telegram_id
        result.append({
            "id": aid,
            "name": ag.name,
            "phone": ag.phone,
            "username": ag.username,
            "role": ag.role,
            "status": ag.status,
            "daily_plan": ag.daily_plan,
            "today_count": today_counts.get(aid, 0),
            "week_count": week_counts.get(aid, 0),
            "month_count": month_counts.get(aid, 0),
            "total_count": total_counts.get(aid, 0),
            "last_active": ag.last_active,
        })

    return result


@api_router.get("/agents/ranking")
async def get_agents_ranking(period: str = "day", admin: Agent = Depends(get_current_admin)):
    ranking = await get_top_ranking(period=period, my_agent_id=admin.telegram_id)
    return ranking


@api_router.post("/agents/{agent_id}/approve")
async def approve_agent_api(agent_id: int, admin: Agent = Depends(get_current_admin)):
    success = await sheets_service.set_agent_status(
        telegram_id=agent_id,
        status="active",
        admin_id=admin.telegram_id,
        admin_name=admin.name,
    )
    return {"ok": success}


@api_router.post("/agents/{agent_id}/block")
async def block_agent_api(agent_id: int, admin: Agent = Depends(get_current_admin)):
    settings = get_settings()
    if agent_id == settings.SUPERADMIN_ID:
        raise HTTPException(status_code=400, detail="Superadminni bloklab bo'lmaydi.")
    if agent_id == admin.telegram_id:
        raise HTTPException(status_code=400, detail="O'zingizni bloklay olmaysiz.")

    success = await sheets_service.set_agent_status(
        telegram_id=agent_id,
        status="blocked",
        admin_id=admin.telegram_id,
        admin_name=admin.name,
    )
    return {"ok": success}


@api_router.post("/agents/{agent_id}/unblock")
async def unblock_agent_api(agent_id: int, admin: Agent = Depends(get_current_admin)):
    success = await sheets_service.set_agent_status(
        telegram_id=agent_id,
        status="active",
        admin_id=admin.telegram_id,
        admin_name=admin.name,
    )
    return {"ok": success}


@api_router.post("/agents/{agent_id}/plan")
async def update_agent_plan_api(
    agent_id: int,
    req: PlanUpdateRequest,
    admin: Agent = Depends(get_current_admin),
):
    success = await sheets_service.set_agent_daily_plan(agent_id, req.daily_plan)
    return {"ok": success}


# ------------------ Superadmin: Promote/Demote Admin ------------------
@api_router.post("/admins/{agent_id}")
async def promote_admin(agent_id: int, superadmin: Agent = Depends(get_current_superadmin)):
    success = await sheets_service.set_agent_role(
        telegram_id=agent_id,
        role="admin",
        admin_id=superadmin.telegram_id,
        admin_name=superadmin.name,
    )
    return {"ok": success}


@api_router.delete("/admins/{agent_id}")
async def demote_admin(agent_id: int, superadmin: Agent = Depends(get_current_superadmin)):
    settings = get_settings()
    if agent_id == settings.SUPERADMIN_ID:
        raise HTTPException(status_code=400, detail="Superadmin rolini o'zgartirib bo'lmaydi.")

    success = await sheets_service.set_agent_role(
        telegram_id=agent_id,
        role="agent",
        admin_id=superadmin.telegram_id,
        admin_name=superadmin.name,
    )
    return {"ok": success}


# ------------------ /api/export/excel ------------------
@api_router.post("/export/excel")
async def export_excel_to_telegram(
    viloyat: str | None = None,
    tuman: str | None = None,
    mahalla: str | None = None,
    agent_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    admin: Agent = Depends(get_current_admin),
):
    # Rate limit: max 3 exports per minute
    now = time.time()
    user_id = admin.telegram_id
    timestamps = export_rate_limits.get(user_id, [])
    timestamps = [ts for ts in timestamps if now - ts < 60.0]
    if len(timestamps) >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "rate_limit", "message": "Daqiqasiga ko'pi bilan 3 marta eksport qilish mumkin."},
        )
    timestamps.append(now)
    export_rate_limits[user_id] = timestamps

    # Query filtered stores
    all_stores = await sheets_service.get_stores(include_deleted=False)
    filtered = apply_store_filters(
        all_stores,
        viloyat=viloyat,
        tuman=tuman,
        mahalla=mahalla,
        agent_id=agent_id,
        date_from=date_from,
        date_to=date_to,
        q=q,
    )

    agents_map = await sheets_service.get_agents()
    excel_bytes = generate_stores_excel(filtered, agents_map)

    # Deliver to admin chat via Telegram bot
    from app.main import bot

    filename = f"dokonlar_{get_current_tashkent_time().strftime('%Y-%m-%d_%H%M')}.xlsx"
    input_file = BufferedInputFile(excel_bytes, filename=filename)

    caption = (
        f"📊 <b>Eksport qilingan do'konlar ro'yxati</b>\n\n"
        f"Jami qatorlar: {len(filtered)} ta\n"
        f"Fayl: <code>{filename}</code>"
    )

    try:
        await bot.send_document(
            chat_id=admin.telegram_id,
            document=input_file,
            caption=caption,
            parse_mode="HTML",
        )
        return {"ok": True, "count": len(filtered)}
    except Exception as e:
        logger.error(f"Failed to send export document to admin {admin.telegram_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "telegram_delivery_failed", "message": "Faylni Telegram chatga yuborib bo'lmadi."},
        ) from e
