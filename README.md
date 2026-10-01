# 🏪 Do'kon Skaut — Telegram Boti va Admin Mini App

"Do'kon Skaut" — savdo agentlari tomonidan do'konlarni xaritada ro'yxatga olish, INN, lokatsiya va rasmlarni kiritish hamda administratorlar uchun interaktiv xarita, statistik grafiklar, agentlar nazorati va Excel eksport imkoniyatini beruvchi to'liq tizim.

---

## 🌟 Asosiy Imkoniyatlar

- **Savdo Agentlari Oqimi (Telegram Bot):**
  - Do'konning tashqi ko'rinishi rasmlari (Pillow bilan siqiladi, Google Drive'ga yuklanadi).
  - Jonli lokatsiya yuborish (soxta yoki forward qilingan lokatsiyalar bloklanadi).
  - OpenStreetMap Nominatim orqali avtomatik viloyat, tuman va mahallani aniqlash.
  - 9 xonali INN tekshiruvi va dublikat do'konlarni qayta tashrif sifatida qayd etish.
  - Do'kon nomi va egasining telefon raqami (`+998...` formatida).
  - Agentning shaxsiy statistikasi (`/stats`) va umumiy reytingi (`/top`).
  - Kiritilgan do'konlarni ko'rish va tahrirlash (`Mening yozuvlarim`).

- **Administratorlar Mini App Paneli (Telegram WebApp):**
  - **Bosh sahifa:** 4 ta asosiy KPI ko'rsatkich, 30 kunlik do'konlar dinamikasi grafigi, Top hududlar taqqoslovi.
  - **Interaktiv Xarita:** OpenStreetMap + Leaflet marker cluster. Do'kon tanlanganda rasmlar, to'liq ma'lumotlar va Google Maps'da ochish tugmasi.
  - **Do'konlar Ro'yxati:** Tezkor qidiruv (Nom, INN, Telefon), hududiy filtrlar va o'chirish.
  - **Agentlar Nazorati:** Kutilayotgan arizalarni qabul qilish/rad etish, bloklash, agentga kunlik reja belgilash.
  - **Eksport va Hisobot:** Filtrlar bo'yicha to'liq formatlangan `.xlsx` faylni bevosita adminning Telegram chatiga yuborish.

- **Avtomatizatsiya va Xavfsizlik:**
  - Toshkent vaqti bilan har kuni soat 21:00 da adminlarga kunlik jamlama hisobot.
  - Har yakshanba soat 03:00 da spreadsheet'ning avtomatik zaxira nusxasi olinadi (oxirgi 8 tasi saqlanadi).
  - Barcha yozishlar poyga holatisiz (race-condition free) ketma-ket `asyncio.Queue` orqali bajariladi.
  - Google Sheets formula in'ektsiyasidan to'liq himoya.

---

## 📋 Qadamma-qadam Ishga Tushirish Yo'riqnomasi (Noldan)

### 1-qadam: Telegram Bot va Mini App yaratish
1. Telegram'da [@BotFather](https://t.me/BotFather) botiga kiring.
2. `/newbot` buyrug'ini bering, botga nom va username tanlang. Sizga berilgan `BOT_TOKEN` ni saqlab qo'ying.
3. BotFather'ga `/setdomain` buyrug'ini yuboring va botingizni tanlang. Kelgusida Render'da olinadigan domeningizni kiritasiz (masalan, `https://sizning-botingiz.onrender.com`).
4. O'zingizning Telegram ID raqamingizni bilish uchun [@userinfobot](https://t.me/userinfobot) botiga `/start` yozing. Chiqqan `Id` raqami bu sizning `SUPERADMIN_ID`ingiz.

---

### 2-qadam: Google Cloud Sozlash va Token Olish
1. [Google Cloud Console](https://console.cloud.google.com)ga kiring va yangi loyiha yarating (masalan, `Dokon-Scout`).
2. **APIs & Services -> Library** bo'limiga o'ting va quyidagi 2 ta API'ni yoqing:
   - **Google Sheets API**
   - **Google Drive API**
3. **APIs & Services -> OAuth consent screen** bo'limiga kiring:
   - User Type: **External** tanlang va "Create" bosing.
   - App name: `Dokon Scout`, emailingizni kiriting.
   - Test users bo'limiga o'zingizning Google emailingizni qo'shing.
   - **MUHIM:** Consent screen sahifasida **"Publish App"** tugmasini bosing! (Aks holda Google refresh tokeningizni 7 kundan keyin bekor qilib qo'yadi).
4. **APIs & Services -> Credentials** bo'limiga o'ting:
   - "Create Credentials" -> **OAuth client ID** ni tanlang.
   - Application type: **Desktop app** ni tanlang.
   - Sizga `Client ID` va `Client Secret` beriladi.
5. Loyiha ildizidagi `.env.example` dan nusxa olib `.env` fayl yarating:
   ```env
   GOOGLE_CLIENT_ID=sizning_client_id
   GOOGLE_CLIENT_SECRET=sizning_client_secret
   ```
6. Terminalda bir martalik OAuth skriptini ishga tushiring:
   ```bash
   python scripts/get_google_token.py
   ```
7. Brauzeringiz ochiladi, Google hisobingizga kiring va ruxsat bering.
8. Terminalda chiqqan `GOOGLE_REFRESH_TOKEN` qiymatini `.env` faylingizga ko'chirib yozing.

---

### 3-qadam: Google Drive Papka va Google Sheets Yaratish
1. [Google Drive](https://drive.google.com)ga kiring va bitta asosiy papka oching (masalan, `Dokon_Scout_Fayllar`).
   - Brauzer manzil satridagi papka ID raqamini oling: `drive.google.com/drive/folders/1xxxxxxxxxxxxxxxx` -> `DRIVE_ROOT_FOLDER_ID=1xxxxxxxxxxxxxxxx`.
2. O'sha yerda bitta yangi bo'sh **Google Sheets** yarating:
   - Manzil satridagi ID'ni oling: `docs.google.com/spreadsheets/d/1yyyyyyyyyyyyyyyy/edit` -> `SPREADSHEET_ID=1yyyyyyyyyyyyyyyy`.
3. Ushbu ID'larni `.env` faylingizga kiriting.
4. Jadvalni avtomatik bezatish va sozlash skriptini ishga tushiring:
   ```bash
   python scripts/init_sheets.py
   ```
   *Bu skript jadvalda 6 ta varaqni (`Do'konlar`, `Tashriflar`, `Agentlar`, `Log`, `Sozlamalar`, `Statistika`), to'q ko'k sarlavhalar, formulalar, filtrlar va dizaynni avtomatik o'rnatadi.*

---

### 4-qadam: Lokal Sinov (Development)
Loyihani lokal kompyuterda sinab ko'rish:
```bash
# Kutubxonalarni o'rnatish
pip install -r requirements.txt

# Testlarni tekshirish
pytest

# Serverni ishga tushirish
uvicorn app.main:app --reload
```
Brauzerda oching:
- Health check: `http://localhost:8000/healthz`
- Admin Mini App: `http://localhost:8000/app?debug_user_id=SIZNING_TELEGRAM_ID` (`.env` da `DEBUG=1` bo'lganda).

---

### 5-qadam: Render.com Bepul Serveriga Joylash (Deploy)

1. Loyihani GitHub shaxsiy omboringizga (repository) yuklang:
   ```bash
   git init
   git add .
   git commit -m "Initial Dokon Scout Release"
   git branch -M main
   git remote add origin https://github.com/SIZNING_USERNAME/dokon-bot.git
   git push -u origin main
   ```
   *(Eslatma: `.gitignore` sababli `.env` faylingiz GitHub'ga tushmaydi, xavfsizlik ta'minlangan).*

2. [Render.com](https://render.com)ga kiring va **New + -> Blueprint** ni bosing.
3. GitHub omboringizni tanlang. Render loyihangizdagi `render.yaml` faylini avtomatik o'qiydi.
4. So'ralgan barcha Environment Variables (Atrof-muhit o'zgaruvchilari)ni to'ldiring:
   - `BOT_TOKEN`
   - `SUPERADMIN_ID`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `GOOGLE_REFRESH_TOKEN`
   - `SPREADSHEET_ID`
   - `DRIVE_ROOT_FOLDER_ID`
   - `PUBLIC_BASE_URL` (masalan, `https://dokon-scout-bot.onrender.com`)
5. "Apply" tugmasini bosing. Render loyihani yig'adi va ishga tushiradi.
6. Deploy tugagach, Telegram botingiz webhook orqali avtomatik ulanadi.

---

### 6-qadam: Render Free Tier va Uptime Sozlash (Muhim!)
Render'ning bepul rejimi (Free Web Service) 15 daqiqa davomida so'rov kelmasa, avtomatik uxlab qoladi (spin down). Buni oldini olish va bot tezkor ishlashini ta'minlash uchun:
1. [UptimeRobot.com](https://uptimerobot.com) saytida bepul ro'yxatdan o'ting.
2. "Add New Monitor" bosing:
   - Monitor Type: `HTTP(s)`
   - Friendly Name: `Dokon Bot Ping`
   - URL (or IP): `https://sizning-ilovangiz.onrender.com/healthz`
   - Monitoring Interval: `5 minutes`
3. "Create Monitor" bosing. UptimeRobot har 5 daqiqada `/healthz` manziliga tezkor so'rov yuboradi va serveringiz doimo uyg'oq turishini ta'minlaydi.

---

### 7-qadam: Admin Guruhini Bog'lash
1. Telegram'da adminlar uchun alohida guruh oching.
2. Botingizni guruhga a'zo qilib qo'shing va unga administrator huquqini bering.
3. Superadmin akkauntingizdan guruh ichida `/setgroup` deb yozing.
4. Bot ushbu guruhni bildirishnomalar uchun asosiy kanal sifatida saqlab oladi. Endi har safar yangi do'kon qo'shilganda fotosurati va ma'lumotlari ushbu guruhga yuboriladi.

---

## 🛠 Admin Buyruqlari

| Buyruq | Kim uchun | Tavsifi |
|---|---|---|
| `/start` | Hamma | Botni ishga tushirish / Til tanlash / Asosiy menyu |
| `/lang` | Hamma | Muloqot tilini o'zgartirish (uz, uz_cyr, ru) |
| `/stats` | Agent/Admin | Shaxsiy natijalar va kunlik reja progressi |
| `/top` | Agent/Admin | Eng yaxshi natija ko'rsatgan agentlar reytingi |
| `/agents` | Admin | Tizimdagi agentlar ro'yxati (holat bo'yicha) |
| `/block <id>` | Admin | Agentni bloklash |
| `/unblock <id>` | Admin | Agentni blokdan chiqarish |
| `/addadmin <id>` | Superadmin | Agentga administratorlik maqomini berish |
| `/removeadmin <id>` | Superadmin | Administratorni oddiy agent qilish |
| `/setgroup` | Superadmin | Guruhni bildirishnomalar qabul qiluvchi qilib belgilash |
| `/report_now` | Superadmin | Kunlik hisobotni zudlik bilan barcha adminlarga jo'natish |
| `/backup_now` | Superadmin | Google Spreadsheet zaxira nusxasini zudlik bilan Drive'ga olish |

---

## 🔍 Keng Tarqalgan Muammolar va Yechimlari

1. **Google Refresh Token 7 kunda eskirib qolishi:**
   - Sababi: Google Cloud Console'da OAuth consent screen `Testing` rejimida qolgan.
   - Yechimi: Consent screen sahifasiga o'tib, **"Publish App"** tugmasini bosing.
2. **Webhook 403 xatosi:**
   - Sababi: `WEBHOOK_SECRET` mos kelmadi.
   - Yechimi: Render'dagi `WEBHOOK_SECRET` bilan Telegram webhook o'rnatishdagi secret bir xil ekanligiga ishonch hosil qiling.
3. **Mini App ochilmasligi yoki 401 xatosi:**
   - Mini App faqat `active` maqomidagi adminlar uchun ishlaydi. Oddiy agentlar yoki ro'yxatdan o'tmaganlar uchun ruxsat berilmaydi.
   - Brauzerda sinash uchun `.env` da `DEBUG=1` qilib, `?debug_user_id=SIZNING_ID` orqali kiring.
