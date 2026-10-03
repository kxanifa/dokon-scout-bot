import hashlib
import hmac
import json
import time
import urllib.parse
from typing import Any

from app.config import get_settings
from app.services.sheets import Agent, sheets_service


class AuthError(Exception):
    """Authentication or authorization failure."""
    pass


def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict[str, Any]:
    """
    Validate Telegram WebApp initData string using HMAC-SHA256 according to Telegram specs:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    if not init_data:
        raise AuthError("initData berilmagan.")

    parsed = urllib.parse.parse_qsl(init_data, keep_blank_values=True)
    params = dict(parsed)

    received_hash = params.pop("hash", None)
    if not received_hash:
        raise AuthError("initData ichida 'hash' parametri yo'q.")

    # Sort remaining parameters alphabetically and join with '\n'
    sorted_pairs = [f"{k}={v}" for k, v in sorted(params.items())]
    data_check_string = "\n".join(sorted_pairs)

    # secret_key = HMAC_SHA256("WebAppData", bot_token)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()

    # calculated_hash = HMAC_SHA256(secret_key, data_check_string).hexdigest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise AuthError("initData xesh tekshiruvi muvaffaqiyatsiz bo'ldi.")

    # Check auth_date expiration
    auth_date_str = params.get("auth_date")
    if not auth_date_str:
        raise AuthError("initData ichida 'auth_date' topilmadi.")

    try:
        auth_date = int(auth_date_str)
        now = int(time.time())
        if abs(now - auth_date) > max_age_seconds:
            raise AuthError("initData muddati o'tgan (24 soatdan ortiq).")
    except ValueError as err:
        raise AuthError("Noto'g'ri 'auth_date' formati.") from err

    # Parse user JSON
    user_str = params.get("user")
    if user_str:
        try:
            params["user_obj"] = json.loads(user_str)
        except Exception:
            params["user_obj"] = {}

    return params


def create_admin_token(user_id: int, role: str = "superadmin", expires_in: int = 86400 * 30) -> str:
    """Creates a secure HMAC-SHA256 signed session token for web browser access."""
    settings = get_settings()
    expire_time = int(time.time()) + expires_in
    data = f"{user_id}:{expire_time}:{role}"
    secret = (settings.BOT_TOKEN or settings.WEBHOOK_SECRET).encode("utf-8")
    sig = hmac.new(secret, data.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{user_id}.{expire_time}.{role}.{sig}"


def verify_admin_token(token: str) -> dict[str, Any] | None:
    """Verifies a session token string. Returns dict with user_id and role if valid."""
    if not token or "." not in token:
        return None
    parts = token.split(".")
    if len(parts) != 4:
        return None
    user_id_str, expire_str, role, sig = parts
    try:
        user_id = int(user_id_str)
        expire_time = int(expire_str)
    except ValueError:
        return None

    if time.time() > expire_time:
        return None

    settings = get_settings()
    data = f"{user_id}:{expire_time}:{role}"
    secret = (settings.BOT_TOKEN or settings.WEBHOOK_SECRET).encode("utf-8")
    expected_sig = hmac.new(secret, data.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        return None

    return {"user_id": user_id, "role": role}


async def authenticate_admin_user(auth_header: str | None, debug_user_id: int | None = None) -> Agent:
    """
    Authenticate an admin or superadmin from:
    1. "Authorization: Bearer <session_token>" (Browser, direct login link)
    2. "Authorization: tma <initData>" (Telegram WebApp)
    3. Debug user ID in dev mode
    """
    settings = get_settings()

    # Dev/Debug mode support outside Telegram
    if debug_user_id:
        if settings.DEBUG or debug_user_id == settings.SUPERADMIN_ID:
            agent = await sheets_service.get_agent_by_id(debug_user_id)
            if agent:
                return agent
            if debug_user_id == settings.SUPERADMIN_ID:
                return Agent(telegram_id=debug_user_id, name="SuperAdmin", role="superadmin", status="active")

    if not auth_header:
        raise AuthError("Avtorizatsiya ma'lumotlari kiritilmagan.")

    # 1. Bearer Token Authentication (Browser & Direct links)
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        payload = verify_admin_token(token)
        if not payload:
            raise AuthError("Sessiya muddati tugagan yoki token yaroqsiz.")
        user_id = payload["user_id"]
        if user_id == settings.SUPERADMIN_ID:
            agent = await sheets_service.get_agent_by_id(user_id)
            if not agent:
                agent = Agent(
                    telegram_id=user_id,
                    name="SuperAdmin",
                    role="superadmin",
                    status="active",
                )
            return agent
        agent = await sheets_service.get_agent_by_id(user_id)
        if not agent:
            raise AuthError("Foydalanuvchi tizimda topilmadi.")
        if agent.status != "active":
            raise AuthError("Foydalanuvchi faol holatda emas.")
        if agent.role not in ("admin", "superadmin"):
            raise AuthError("Faqat administratorlar uchun ruxsat berilgan.")
        return agent

    # 2. Telegram WebApp initData (tma <initData>)
    if auth_header.startswith("tma "):
        init_data = auth_header[4:].strip()
        validated = validate_telegram_init_data(init_data, settings.BOT_TOKEN)

        user_obj = validated.get("user_obj", {})
        user_id = user_obj.get("id")
        if not user_id:
            raise AuthError("Telegram foydalanuvchi ID si topilmadi.")

        # Check if superadmin
        if user_id == settings.SUPERADMIN_ID:
            agent = await sheets_service.get_agent_by_id(user_id)
            if not agent:
                name = f"{user_obj.get('first_name', '')} {user_obj.get('last_name', '')}".strip() or "SuperAdmin"
                agent = Agent(
                    telegram_id=user_id,
                    name=name,
                    username=user_obj.get("username", ""),
                    role="superadmin",
                    status="active",
                )
                await sheets_service.upsert_agent(agent)
            return agent

        # Fetch agent and verify admin role & active status
        agent = await sheets_service.get_agent_by_id(user_id)
        if not agent:
            raise AuthError("Foydalanuvchi tizimda ro'yxatdan o'tmagan.")

        if agent.status != "active":
            raise AuthError("Foydalanuvchi holati faol emas.")

        if agent.role not in ("admin", "superadmin"):
            raise AuthError("Mini App faqat administratorlar uchun mo'ljallangan.")

        return agent

    raise AuthError("Yaroqsiz avtorizatsiya formati (kutilmoqda: Bearer yoki tma).")
