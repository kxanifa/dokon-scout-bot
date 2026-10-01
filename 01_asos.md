# PROMPT 1 / 5 — Loyiha asosi, Google Sheets va Drive ulanishi

Sen tajribali Python backend dasturchisisan. Loyiha ildizida `SPEC.md` bor. **Avval uni boshidan oxirigacha to'liq o'qi**, keyin ishni boshla. SPEC bilan zid ish qilma. Tushunarsiz yoki zid joy topsang, taxmin qilma, to'xtab menga savol ber.

## Maqsad
Botning poydevorini qur: loyiha tuzilmasi, konfiguratsiya, Google Sheets va Drive servislari, i18n skeleti, FastAPI ilovasi (hozircha faqat `/healthz`) va ishga tushirish skriptlari. Bot handlerlari va Mini App bu bosqichda yozilmaydi.

## Bajariladigan ishlar

1. **Tuzilma.** SPEC 12-bo'limdagi papka tuzilmasini yarat (bo'sh modullar `__init__.py` bilan). `requirements.txt` (versiyalarni aniq yoz), `.env.example`, `.gitignore` (`.env`, `*.json` token fayllari, `__pycache__`, `.venv`), `ruff` va `pytest` sozlamalari (`pyproject.toml`).
2. **`app/config.py`.** `pydantic-settings` bilan SPEC 11-bo'limdagi barcha o'zgaruvchilar. Majburiylari yo'q bo'lsa, aniq xato xabari bilan ishga tushmasin.
3. **`app/services/sheets.py`.** Asinxron interfeys (Google kutubxonasi sinxron bo'lgani uchun `asyncio.to_thread` yoki executor):
   - Varaqlarni o'qish/yozish uchun yuqori darajali metodlar: `append_store`, `append_visit`, `get_stores`, `get_store_by_id`, `find_stores_by_inn`, `update_store_fields`, `soft_delete_store`, `get_agents`, `upsert_agent`, `set_agent_status`, `set_agent_role`, `append_log`, `get_settings`, `set_setting`.
   - SPEC 7-bo'limdagi kvota qoidalari: xotira keshi (TTL), yagona yozish navbati (`asyncio.Queue` + bitta worker), 429/5xx da eksponensial kutish bilan qayta urinish, `ID` ni navbat ichida hisoblash.
   - Formula in'ektsiyasidan himoya funksiyasi (`sanitize_cell`) va HYPERLINK formulani xavfsiz yig'uvchi yordamchi funksiya.
   - Qatorlar va Python obyektlari (dataclass yoki pydantic model) orasida aniq xaritalash. Ustun nomlari bitta joyda (konstantalar) turadi.
4. **`scripts/init_sheets.py`.** Idempotent skript: spreadsheet'da kerakli varaqlar bo'lmasa yaratadi, sarlavhalarni yozadi va SPEC 7-bo'limdagi dizaynni qo'llaydi (qotirilgan sarlavha, ranglar, banding, filtr, ustun kengliklari, shartli format, yashirin FileID ustunlari, `INN` matn formati). `Statistika` varag'iga viloyat/tuman/mahalla/agent/kun bo'yicha formulalarni qo'yadi. `Sozlamalar` ga sukut qiymatlarni yozadi. Qayta ishga tushirilsa hech narsani buzmaydi va mavjud ma'lumotni o'chirmaydi.
5. **`app/services/drive.py`.** `ensure_folder`, `upload_image(bytes, name, month)` (papka tuzilmasi SPEC 8-bo'lim), `get_file_bytes(file_id)`, `copy_file`, `delete_old_backups`. Sinxron chaqiruvlar threadga o'raladi, xatolarda qayta urinish.
6. **`app/services/images.py`.** SPEC 8-bo'limdagi siqish: EXIF transpose, uzun tomon ≤1600 px, JPEG sifat 80, RGB ga o'tkazish. Yaroqsiz rasmda aniq xato.
7. **`scripts/get_google_token.py`.** Bir martalik OAuth (loopback oqim): `GOOGLE_CLIENT_ID`/`SECRET` dan foydalanib brauzer ochadi va `GOOGLE_REFRESH_TOKEN` ni terminalga chiqaradi. Skript boshida Google Cloud Console'da nima qilish kerakligi (Sheets API va Drive API'ni yoqish, OAuth consent screen, "Desktop app" turidagi OAuth client yaratish, o'zingni test foydalanuvchi sifatida qo'shish va `Publish app` qilish — aks holda refresh token 7 kundan keyin tugaydi) izoh sifatida yozilsin.
8. **`app/i18n`.** `t(key, lang, **kwargs)` funksiyasi, `uz.py`, `uz_cyr.py`, `ru.py` lug'atlari. Hozircha umumiy kalitlar (tugma nomlari, xatolar, menyu). Keyingi bosqichlarda kalit qo'shiladi. Uch tilda kalitlar to'plami tengligini tekshiruvchi test.
9. **`app/main.py`.** FastAPI ilovasi, `lifespan` ichida yozish navbati workerini ishga tushirish/to'xtatish, `GET /healthz` (Sheets'ga tegmaydi, `{"ok": true}`), tuzilgan logging (sirlarsiz).
10. **`README.md`.** Nol dan ishga tushirish yo'riqnomasi (Google Cloud sozlash, token olish, `init_sheets` ishga tushirish, lokal ishga tushirish `uvicorn app.main:app --reload`). Oddiy tilda, qadamma-qadam, skrinshotsiz ham tushunarli bo'lsin.
11. **Testlar.** `sanitize_cell`, HYPERLINK yig'uvchi, qator ⇄ model xaritalash, i18n tenglik, rasm siqish (kichik sintetik rasm bilan), kesh TTL mantig'i. Google API chaqiruvlari mock qilinadi; tarmoqsiz o'tishi shart.

## Qabul mezonlari (hammasi bajarilmaguncha "tayyor" dema)
- [ ] `pytest` hammasi yashil, `ruff check` xatosiz.
- [ ] `python scripts/init_sheets.py` bo'sh spreadsheet'ni to'liq tayyor holatga keltiradi va ikkinchi marta ishga tushirilganda hech narsani buzmaydi (mock yoki haqiqiy kalitlar bilan tekshir; haqiqiy kalit bo'lmasa, nima tekshirilmaganini ochiq ayt).
- [ ] `uvicorn app.main:app` ishga tushadi va `/healthz` 200 qaytaradi.
- [ ] Hech bir faylda sir/token qattiq yozilmagan.
- [ ] Oxirida: nima qilindi, nima haqiqiy akkauntda tekshirilmadi, menga qanday qadamlar (Google sozlash) kerakligi haqida qisqa hisobot.

Bu bosqichda bot handlerlari, Mini App, Render sozlamalari yozilmaydi. Kengaytirib yuborma.
