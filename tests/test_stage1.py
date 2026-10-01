import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.i18n import t
from app.i18n.ru import TEXTS as RU_TEXTS
from app.i18n.uz import TEXTS as UZ_TEXTS
from app.i18n.uz_cyr import TEXTS as UZ_CYR_TEXTS
from app.main import app
from app.services.images import InvalidImageError, compress_image, create_thumbnail
from app.services.sheets import (
    Agent,
    Store,
    Visit,
    make_hyperlink,
    sanitize_cell,
)


def test_sanitize_cell():
    # Dangerous formula characters must be prefixed with apostrophe
    assert sanitize_cell("=1+1") == "'=1+1"
    assert sanitize_cell("+SUM(A1:A10)") == "'+SUM(A1:A10)"
    assert sanitize_cell("-5+2") == "'-5+2"
    assert sanitize_cell("@dangerous") == "'@dangerous"

    # Normal strings and numbers remain unchanged
    assert sanitize_cell("Normal store") == "Normal store"
    assert sanitize_cell("123456789") == "123456789"
    assert sanitize_cell("") == ""
    assert sanitize_cell(None) == ""


def test_make_hyperlink():
    formula = make_hyperlink("https://example.com/item?id=1", "Ko'rish")
    assert formula == '=HYPERLINK("https://example.com/item?id=1","Ko\'rish")'

    # Double quotes in label or url must be escaped
    formula2 = make_hyperlink('https://example.com/foo"bar', 'Do\'kon "Al-Baraka"')
    assert '""Al-Baraka""' in formula2
    assert '""bar' in formula2

    # Empty url returns empty string
    assert make_hyperlink("", "Label") == ""


def test_i18n_keys_equality():
    uz_keys = set(UZ_TEXTS.keys())
    uz_cyr_keys = set(UZ_CYR_TEXTS.keys())
    ru_keys = set(RU_TEXTS.keys())

    assert uz_keys == uz_cyr_keys, f"Diff UZ vs UZ_CYR: {uz_keys ^ uz_cyr_keys}"
    assert uz_keys == ru_keys, f"Diff UZ vs RU: {uz_keys ^ ru_keys}"

    # Test t() function
    assert "Yangi do'kon" in t("btn_new_store", "uz")
    assert "Янги дўкон" in t("btn_new_store", "uz_cyr")
    assert "Новый магазин" in t("btn_new_store", "ru")


def test_store_model_row_roundtrip():
    store = Store(
        id=42,
        date="2026-10-01",
        time="12:00:00",
        agent_id=12345,
        agent_name="Ali Valiyev",
        name="Baraka Market",
        inn="123456789",
        phone="+998901234567",
        state="Toshkent shahri",
        district="Chilonzor tumani",
        mahalla="1-mavze",
        lat=41.2858,
        lon=69.2036,
        photo1="https://drive.google.com/file1",
        photo2="",
        photo3="",
        status="faol",
        updated_at="",
        updated_by="",
        photo1_id="fid_123",
        photo2_id="",
        photo3_id="",
    )

    row = store.to_row()
    assert len(row) == 23
    assert row[0] == "42"
    assert row[6] == "'123456789"  # text formatted INN

    parsed = Store.from_row(row)
    assert parsed.id == 42
    assert parsed.agent_id == 12345
    assert parsed.name == "Baraka Market"
    assert parsed.inn == "123456789"
    assert parsed.state == "Toshkent shahri"
    assert parsed.district == "Chilonzor tumani"
    assert parsed.status == "faol"
    assert parsed.photo1_id == "fid_123"


def test_visit_model_row_roundtrip():
    visit = Visit(
        id=7,
        store_id=42,
        date="2026-10-01",
        time="14:30:00",
        agent_id=12345,
        agent_name="Ali Valiyev",
        lat=41.2858,
        lon=69.2036,
        photo1="https://drive.google.com/visit1",
        photo1_id="vid_111",
    )
    row = visit.to_row()
    assert len(row) == 14
    parsed = Visit.from_row(row)
    assert parsed.id == 7
    assert parsed.store_id == 42
    assert parsed.agent_id == 12345
    assert parsed.photo1_id == "vid_111"


def test_agent_model_row_roundtrip():
    agent = Agent(
        telegram_id=999888,
        name="Husan Karimov",
        phone="+998971112233",
        username="husan_k",
        lang="uz",
        role="agent",
        status="active",
        registered_at="2026-10-01 10:00:00",
        daily_plan=25,
        last_active="2026-10-01 12:15:00",
    )
    row = agent.to_row()
    parsed = Agent.from_row(row)
    assert parsed.telegram_id == 999888
    assert parsed.name == "Husan Karimov"
    assert parsed.phone == "+998971112233"
    assert parsed.daily_plan == 25
    assert parsed.status == "active"


def test_image_compression():
    # Create synthetic high-res image
    img = Image.new("RGBA", (2400, 1800), color=(255, 100, 50, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    compressed = compress_image(raw_bytes, max_dimension=1600, quality=80)
    assert len(compressed) < len(raw_bytes)

    with Image.open(io.BytesIO(compressed)) as out_img:
        assert out_img.format == "JPEG"
        assert max(out_img.size) <= 1600
        assert out_img.mode == "RGB"

    thumb = create_thumbnail(raw_bytes, max_width=300)
    with Image.open(io.BytesIO(thumb)) as thumb_img:
        assert max(thumb_img.size) <= 300

    # Invalid image bytes should raise InvalidImageError
    with pytest.raises(InvalidImageError):
        compress_image(b"invalid image data")


def test_healthz_endpoint():
    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"ok": True}
