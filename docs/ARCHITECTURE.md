# Loyiha Arxitekturasi va Ma'lumotlar Oqimi (Architecture)

Ushbu hujjat "Do'kon Skaut" tizimining to'liq arxitekturasini, ma'lumotlar oqimini va ma'lum cheklovlarini yoritadi.

---

## 1. Tizim Arxitekturasi

```
                   ┌──────────────────────────────────────────────┐
                   │               Telegram Cloud                 │
                   └──────┬────────────────────────────────┬──────┘
                          │ Webhook                        │ WebApp
                          ▼ Updates                        ▼ initData
             ┌────────────────────────────────────────────────────────┐
             │            Render.com (FastAPI Web Service)            │
             │                                                        │
             │  ┌───────────────────────┐  ┌───────────────────────┐  │
             │  │   aiogram 3.x (Bot)   │  │    Mini App API       │  │
             │  │  - Middlewares        │  │  - HMAC Auth          │  │
             │  │  - FSM Handlers       │  │  - REST Endpoints     │  │
             │  └───────────┬───────────┘  └───────────┬───────────┘  │
             │              │                          │              │
             │  ┌───────────▼──────────────────────────▼───────────┐  │
             │  │                 Services Qatlami                 │  │
             │  │  - sheets.py (Queue + TTL Cache + Sanitizer)     │  │
             │  │  - drive.py  (OAuth2 Refresh + Folder Hierarchy) │  │
             │  │  - geocode.py (Nominatim + 1s Rate-Limit)        │  │
             │  │  - images.py (Pillow Resizing 1600px + JPEG 80)  │  │
             │  │  - excel.py  (openpyxl 3 Sheets Generator)       │  │
             │  │  - notify.py (Admin Alerts & Daily Report)       │  │
             │  │  - backup.py (Weekly Rotation Keep 8)            │  │
             │  └───────────┬──────────────────────────┬───────────┘  │
             │              │                          │              │
             │  ┌───────────▼──────────┐    ┌──────────▼───────────┐  │
             │  │ APScheduler (Async)  │    │  app/webapp Static   │  │
             │  │ - 21:00 Daily Report │    │  - Leaflet Map       │  │
             │  │ - Sun 03:00 Backup   │    │  - Chart.js          │  │
             │  └──────────────────────┘    └──────────────────────┘  │
             └──────────────┬──────────────────────────┬──────────────┘
                            │                          │
                 OAuth2 API │                          │ Nominatim HTTP
                            ▼                          ▼
               ┌───────────────────────┐     ┌───────────────────┐
               │      Google Cloud     │     │   OpenStreetMap   │
               │ - Google Sheets API   │     │   Nominatim API   │
               │ - Google Drive API    │     └───────────────────┘
               └───────────────────────┘
```

---

## 2. Ma'lumotlar Oqimi

### A. Yangi Do'kon Qo'shish:
1. Agent Telegram botda rasm yuboradi -> Telegram `file_id` FSM'da saqlanadi.
2. Agent "📍 Lokatsiya yuborish" tugmasini bosadi -> Koordinatalar olinadi.
3. `geocode_service` Nominatim orqali viloyat, tuman, mahallani aniqlaydi (kesh va 1s rate-limit bilan).
4. Agent 9 xonali INN kiritadi -> `sheets_service.find_stores_by_inn` orqali tekshiriladi:
   - Dublikat bo'lsa: "Yangi tashrif" yoki "Baribir qo'shish" tanlanadi.
5. Do'kon nomi va ixtiyoriy telefon kiritiladi.
6. Xulosa tasdiqlangach:
   - Rasm yuklab olinadi va Pillow bilan siqiladi (uzun tomoni ≤1600px, JPEG sifat 80).
   - `drive_service` rasmni `Rasmlar/YYYY-MM/` papkasiga yuklaydi.
   - `sheets_service` navbati orqali `Do'konlar` (yoki `Tashriflar`) varag'iga yangi qator yoziladi.
   - Admin guruhiga foto va sarlavha bilan xabar ketadi.

### B. Admin Mini App Oqimi:
1. Admin botdagi "🛠 Admin panel" WebApp tugmasini bosadi.
2. Mini App Telegram `initData` ni har bir so'rovda `Authorization: tma <initData>` sarlavhasi bilan backend'ga yuboradi.
3. Backend HMAC-SHA256 yordamida autentifikatsiya qiladi va foydalanuvchining adminligini tekshiradi.
4. Xarita va ro'yxat keshdan juda tez yuklanadi.
5. "Excel yuklab olish" bosilganda: backend `.xlsx` fayl tayyorlaydi va bot orqali adminning shaxsiy Telegram chatiga yuboradi.

---

## 3. Ma'lum Cheklovlar va Yechimlar

1. **Telegram lokatsiya yolg'oni:**
   - Telegram attach menyusi orqali xaritada qo'lda nuqta tanlanganda Telegram API uni `request_location` kabi jo'natadi. Telegram platformasi buni 100% ajratish imkonini bermaydi. Shuning uchun forward qilingan va venue xabarlar qat'iy bloklangan.
2. **Nominatim qishloq hududlarida:**
   - O'zbekistonning ayrim chekka qishloqlarida Nominatim mahallani topa olmaydi. Shu sababli bot mahalla topilmagan holatda agentdan uni qo'lda kiritishni talab qiladi.
3. **Google Sheets API kvotasi (~60 so'rov/daqiqa):**
   - Kvotadan chiqib ketmaslik uchun:
     - Barcha o'qishlar xotirada 20–30 soniya TTL bilan keshlangan.
     - Barcha yozishlar bitta `asyncio.Queue` orqali ketma-ket bajariladi.
     - 429/5xx xatolarida eksponensial kutish (exponential backoff) bilan 5 martagacha qayta uriniladi.
     - Ushbu arxitektura ~100 ta savdo agenti faoliyati uchun bemalol yetarli.
4. **Render.com Free Tier xususiyatlari:**
   - Free rejimda server 15 daqiqa so'rovsiz tursa uxlaydi (sleep mode).
   - Birinchi so'rov kelganda 30–50 soniya kechikish bilan uyg'onadi.
   - Buni bartaraf etish uchun UptimeRobot orqali `/healthz` manziliga 5 daqiqalik bepul ping sozlash tavsiya etiladi.
   - Rejalashtirilgan vazifalar: server uyg'onganda `report_time` o'tgan bo'lsa, avtomatik ravishda kunlik hisobotni jo'natadi.
