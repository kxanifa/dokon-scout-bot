import asyncio
import logging
import time
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Standard region mappings for Uzbekistan
REGION_ALIASES = {
    "toshkent shahri": "Toshkent shahri",
    "tashkent": "Toshkent shahri",
    "город ташкент": "Toshkent shahri",
    "г. ташкент": "Toshkent shahri",
    "toshkent viloyati": "Toshkent viloyati",
    "ташкентская область": "Toshkent viloyati",
    "samarqand viloyati": "Samarqand viloyati",
    "самаркандская область": "Samarqand viloyati",
    "andijon viloyati": "Andijon viloyati",
    "андижанская область": "Andijon viloyati",
    "buxoro viloyati": "Buxoro viloyati",
    "бухарская область": "Buxoro viloyati",
    "farg'ona viloyati": "Farg'ona viloyati",
    "fergana": "Farg'ona viloyati",
    "ферганская область": "Farg'ona viloyati",
    "jizzax viloyati": "Jizzax viloyati",
    "джизакская область": "Jizzax viloyati",
    "xorazm viloyati": "Xorazm viloyati",
    "хорезмская область": "Xorazm viloyati",
    "namangan viloyati": "Namangan viloyati",
    "наманганская область": "Namangan viloyati",
    "navoiy viloyati": "Navoiy viloyati",
    "навоийская область": "Navoiy viloyati",
    "qashqadaryo viloyati": "Qashqadaryo viloyati",
    "кашкадарьинская область": "Qashqadaryo viloyati",
    "qoraqalpog'iston respublikasi": "Qoraqalpog'iston Respublikasi",
    "республика каракалпакстан": "Qoraqalpog'iston Respublikasi",
    "surxondaryo viloyati": "Surxondaryo viloyati",
    "сурхандарьинская область": "Surxondaryo viloyati",
    "sirdaryo viloyati": "Sirdaryo viloyati",
    "сырдарьинская область": "Sirdaryo viloyati",
}


def normalize_region_name(raw_name: str) -> str:
    """Standardize Uzbekistan region names."""
    if not raw_name:
        return ""
    clean = raw_name.strip().lower()
    for alias, standard in REGION_ALIASES.items():
        if alias in clean:
            return standard
    # Capitalize words if not in predefined list
    return raw_name.strip()


def parse_address(raw_data: dict[str, Any]) -> dict[str, str]:
    """
    Parse Nominatim reverse geocoding address into:
    state (viloyat), district (tuman), mahalla.
    """
    if not raw_data or not isinstance(raw_data, dict):
        return {"state": "", "district": "", "mahalla": ""}

    addr = raw_data.get("address", {})
    if not addr:
        return {"state": "", "district": "", "mahalla": ""}

    # 1. State / Viloyat
    raw_state = addr.get("state") or addr.get("province") or addr.get("region") or ""
    city = addr.get("city") or ""

    # Special handling for Tashkent city: Nominatim often sets city="Tashkent" and state="Tashkent" or none
    if "tashkent" in city.lower() or "toshkent" in city.lower():
        if "viloyati" in raw_state.lower() or "область" in raw_state.lower():
            state = "Toshkent viloyati"
        else:
            state = "Toshkent shahri"
    else:
        state = normalize_region_name(raw_state)
        if not state and city:
            state = normalize_region_name(city)

    # 2. District / Tuman
    # Common keys: county, city_district, district, town, municipality
    district = (
        addr.get("county")
        or addr.get("city_district")
        or addr.get("district")
        or addr.get("subdistrict")
        or addr.get("town")
        or ""
    )

    if not district and state != "Toshkent shahri" and city:
        district = city

    # 3. Mahalla / Neighborhood
    # Common keys: neighbourhood, quarter, suburb, village, hamlet, residential
    mahalla = (
        addr.get("neighbourhood")
        or addr.get("quarter")
        or addr.get("suburb")
        or addr.get("village")
        or addr.get("hamlet")
        or addr.get("residential")
        or ""
    )

    return {
        "state": state.strip(),
        "district": district.strip(),
        "mahalla": mahalla.strip(),
    }


class GeocodeService:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._last_request_time: float = 0.0
        self._cache: dict[tuple[float, float], dict[str, str]] = {}
        self._cache_limit = 1000
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=3.5,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def reverse_geocode(self, lat: float, lon: float) -> dict[str, str] | None:
        """
        Reverse geocode latitude and longitude using Nominatim.
        Rate-limited to 1 request per second.
        """
        coord_key = (round(lat, 5), round(lon, 5))
        if coord_key in self._cache:
            return self._cache[coord_key]

        settings = get_settings()
        user_agent = settings.NOMINATIM_USER_AGENT

        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "jsonv2",
            "zoom": 18,
            "addressdetails": 1,
            "accept-language": "uz,ru",
        }
        headers = {"User-Agent": user_agent}

        async with self._lock:
            # Enforce at least 1.0 second between requests per Nominatim usage policy
            elapsed = time.time() - self._last_request_time
            if elapsed < 1.0:
                await asyncio.sleep(1.0 - elapsed)
            self._last_request_time = time.time()

            try:
                client = self._get_client()
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    parsed = parse_address(data)

                    # Store in cache
                    if len(self._cache) >= self._cache_limit:
                        # Pop oldest
                        self._cache.pop(next(iter(self._cache)))
                    self._cache[coord_key] = parsed
                    return parsed
                else:
                    logger.warning(f"Nominatim returned status {resp.status_code}")
                    return None
            except Exception as e:
                logger.warning(f"Nominatim reverse geocoding failed: {e}")
                return None


geocode_service = GeocodeService()
