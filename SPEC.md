# SPEC — "Do'kon Skaut" Telegram boti (to'liq texnik topshiriq)

Bu fayl loyihaning yagona haqiqat manbai. Barcha bosqichlar shu faylga tayanadi. Loyiha ildizida `SPEC.md` nomi bilan turadi. Agar kod va SPEC bir-biriga zid bo'lsa, SPEC to'g'ri hisoblanadi (o'zgartirish kerak bo'lsa, avval foydalanuvchidan so'ra).

## 1. Maqsad

Savdo agentlari do'konlarga borib: do'konni tashqi tomondan rasmga oladi, turgan joyidan lokatsiya yuboradi, do'konning INN raqamini, nomini va (ixtiyoriy) egasining telefonini kiritadi. Ma'lumot Google Sheets'ga yoziladi, rasmlar Google Drive'ga tushadi. Adminlar Telegram Mini App orqali xarita, statistika, filtr va Excel eksportdan foydalanadi.

Ko'lam: ~100 ta agent, bir nechta admin. Hamma narsa tekin xizmatlarda ishlashi shart (Render free web service, Google Sheets/Drive, OpenStreetMap).

## 2. Texnologiyalar (o'zgartirma)

- Python 3.11+
- `aiogram` 3.x (bot), webhook rejimida
- `FastAPI` + `uvicorn` (bitta jarayonda: Telegram webhook, Mini App API, Mini App statik fayllari)
- Google API: `google-api-python-client`, `google-auth`, `google-auth-oauthlib` (OAuth2 **foydalanuvchi akkaunti** refresh token bilan; service account EMAS, chunki service account'ning Drive kvotasi yo'q va rasm yuklay olmaydi)
- `gspread` ishlatma, to'g'ridan-to'g'ri Sheets API v4 (`batchUpdate`, `values.append`, `values.batchGet`) ishlat: kvotani nazorat qilish oson
- `Pillow` (rasmni siqish), `openpyxl` (Excel), `httpx` (Nominatim), `APScheduler` (rejalashtirilgan vazifalar), `pydantic-settings` (konfiguratsiya), `pytest`, `pytest-asyncio`
- Mini App: oddiy HTML/CSS/vanilla JS (build bosqichi yo'q), `Leaflet` + `Leaflet.markercluster` (OpenStreetMap plitalari), `Chart.js`, hammasi CDN orqali. Mini App FastAPI tomonidan `/app` yo'lida xizmat qilinadi (alohida hosting kerak emas).
- Joylash: Render.com (free web service), `render.yaml` bilan

## 3. Rollar va kirish

Rollar: `superadmin` (bitta, `.env` dagi `SUPERADMIN_ID`), `admin`, `agent`.
Holatlar: `pending`, `active`, `blocked`.

- Yangi foydalanuvchi `/start` bosadi, tilni tanlaydi, ismini yozadi, telefon raqamini "Kontaktni ulashish" tugmasi bilan yuboradi. Holat `pending` bo'ladi va barcha adminlarga (superadmin ham) inline tugmali so'rov boradi: ✅ Agent sifatida qabul qilish / ❌ Rad etish.
- Faqat `active` foydalanuvchi asosiy funksiyalardan foydalana oladi. `pending` ga "So'rovingiz ko'rib chiqilmoqda" deb javob beriladi. `blocked` ga bot jim turadi yoki "Kirish cheklangan" deydi.
- Yangi adminni faqat superadmin tayinlaydi (Mini App yoki `/addadmin <telegram_id>`).
- Adminlar hamma hududlarni ko'radi; huquqlari bir xil (admin tayinlashdan tashqari).
- Admin agentlarni bloklay/blokdan chiqara oladi. Bloklangan agentning eski yozuvlari saqlanadi.

## 4. Tillar

Uchta til: `uz` (o'zbekcha lotin), `uz_cyr` (o'zbekcha kirill), `ru`. Barcha matnlar `i18n` modulida, kalit bo'yicha (`t(key, lang, **kwargs)`). Kalit yetishmasa, test yiqilishi kerak (3 til uchun kalitlar to'plami bir xil bo'lishi tekshiriladi). Tilni foydalanuvchi keyin `/lang` yoki "⚙️ Til" tugmasi bilan o'zgartira oladi. Mini App ham shu uch tilni qo'llab-quvvatlaydi (til foydalanuvchi profilidan olinadi).

## 5. Agent oqimi: yangi do'kon qo'shish

Asosiy menyu (reply keyboard): `➕ Yangi do'kon`, `📋 Mening yozuvlarim`, `📊 Statistikam`, `⚙️ Til`. Adminlarga qo'shimcha: `🛠 Admin panel` (WebApp tugma).

Holatlar ketma-ketligi (FSM):
1. **Rasm.** 1 ta majburiy (do'kon tashqarisi), keyin "Yana rasm qo'shish (2 tagacha)" yoki "Davom etish". Kamera va galereyadan qabul qilinadi. Faqat `photo` qabul qilinadi (hujjat sifatida kelgan rasm ham `image/*` bo'lsa qabul qilinsin). Eng katta o'lchamdagi `PhotoSize` olinadi.
2. **Lokatsiya.** Faqat `📍 Lokatsiya yuborish` (`request_location=True`) tugmasi orqali. Rad etiladi: forward qilingan lokatsiya (`forward_origin` bor), `venue`, matn orqali yozilgan koordinata. Rad etilganda tushuntirish va tugmani qayta ko'rsatish. Jonli lokatsiya (`live_period`) qabul qilinadi, birinchi koordinata olinadi. Eslatma: Telegram attach-menyu orqali qo'lda tanlangan nuqtani 100% ajratib bo'lmaydi; bu cheklov hujjatlashtiriladi.
3. **Hududni aniqlash.** Koordinata bo'yicha Nominatim reverse geocoding (`zoom=18`, `addressdetails=1`, `accept-language=uz,ru`). Viloyat (`state`), tuman (`county`/`city_district`/`district`/`city`), mahalla (`neighbourhood`/`quarter`/`suburb`/`village`/`hamlet`) ajratib olinadi. Natija agentga ko'rsatiladi: "Viloyat: …, Tuman: …, Mahalla: …" va tugmalar `✅ To'g'ri`, `✏️ Mahallani yozish`, `✏️ Hammasini tuzatish`. Mahalla aniqlanmasa, agent qo'lda yozadi (majburiy). Nominatim xatolik bersa yoki sekin bo'lsa (timeout 8 s), agent hududni qo'lda kiritadi. Nominatim qoidalari: so'rovlar orasida kamida 1 s, aniq `User-Agent`, natijalarni (koordinata 4-6 xona yaxlitlab) keshda saqlash.
4. **INN.** Faqat 9 xonali raqam (`^\d{9}$`). Bo'shliq va tire olib tashlanadi. Xato bo'lsa, qayta so'raladi. Agar INN `Do'konlar` varag'ida mavjud bo'lsa: "Bu INN avval kiritilgan (Do'kon nomi, agent, sana). Nima qilamiz?" → `🔁 Yangi tashrif sifatida qo'shish` (eski do'konga bog'lanadi, `Tashriflar` varag'iga yoziladi, nom/telefon qayta so'ralmaydi), `➕ Baribir yangi do'kon sifatida saqlash`, `❌ Bekor qilish`.
5. **Do'kon nomi.** Matn, 2–100 belgi.
6. **Egasining telefoni.** Ixtiyoriy. `⏭ O'tkazib yuborish` tugmasi. Kiritilsa, `+998XXXXXXXXX` formatiga normallashtiriladi (9, 12 xonali variantlar, bo'shliq/tire/qavs olib tashlanadi), noto'g'ri bo'lsa qayta so'raladi.
7. **Xulosa.** Rasm(lar) va barcha maydonlar ko'rsatiladi: `✅ Saqlash`, `✏️ Tahrirlash` (qaysi maydon), `❌ Bekor qilish`.
8. **Saqlash.** Rasmlar siqiladi va Drive'ga yuklanadi, so'ng Sheets'ga qator yoziladi, agentga "Saqlandi ✅ №<ID>" xabari boradi, admin guruhiga bildirishnoma ketadi.

Har qadamda `❌ Bekor qilish` va `⬅️ Orqaga` mavjud. Yarim yo'lda qolgan jarayon uchun `/start` yoki menyu bosilganda "Davom ettirish / Bekor qilish" taklif qilinadi. Bir foydalanuvchi bir vaqtda faqat bitta jarayon yuritadi.

## 6. Agent uchun boshqa funksiyalar

- **📊 Statistikam:** bugun / shu hafta / shu oy kiritilgan do'konlar soni, kunlik reja bo'yicha bajarilish ("12/20" va progress satri), umumiy soni.
- **📋 Mening yozuvlarim:** oxirgi yozuvlar (sahifalab, 5 tadan), har biriga `✏️ Tahrirlash`. Agent faqat O'ZI kiritgan yozuvni tahrirlay oladi (nom, telefon, INN, mahalla/hudud, rasm almashtirish). Har tahrirda `Tahrirlangan vaqt` va `Tahrir qilgan` ustunlari yangilanadi va `Log` ga yoziladi. O'chirish agentga yo'q.
- **Kunlik reja:** sukut bo'yicha 20 (`Sozlamalar` varag'ida `daily_plan_default`, admin Mini App orqali o'zgartiradi, agent bo'yicha alohida ham qo'yish mumkin). Rejaga erishilganda tabrik xabari.

## 7. Ma'lumotlar tuzilmasi (Google Sheets = baza)

Bitta spreadsheet (`SPREADSHEET_ID`). Barcha vaqtlar Toshkent vaqti (`Asia/Tashkent`, UTC+5). Sana formati `YYYY-MM-DD`, vaqt `HH:MM:SS`. Birinchi qator sarlavha (qotirilgan, qalin, rangli). Sarlavhalar o'zbekcha lotinda.

**`Do'konlar`** (har bir do'kon bitta qator):
`ID`, `Sana`, `Vaqt`, `Agent ID`, `Agent ismi`, `Do'kon nomi`, `INN`, `Telefon`, `Viloyat`, `Tuman`, `Mahalla`, `Lat`, `Lon`, `Xarita`, `Rasm 1`, `Rasm 2`, `Rasm 3`, `Holat`, `Tahrirlangan vaqt`, `Tahrir qilgan`
- `ID` — ketma-ket butun son (1 dan). `Xarita` — `=HYPERLINK("https://www.google.com/maps?q=lat,lon","📍 Xaritada")`. `Rasm N` — `=HYPERLINK("<drive_url>","🖼 Rasm N")`; Drive fayl ID'si alohida yashirin ustunlarda saqlanadi: `Rasm1 FileID`, `Rasm2 FileID`, `Rasm3 FileID` (oxirgi ustunlar, yashirin).
- `Holat`: `faol` yoki `o'chirilgan` (o'chirish yumshoq: qator o'chirilmaydi, holat o'zgaradi; filtrlar va statistikalar faqat `faol` ni sanaydi).

**`Tashriflar`**: `ID`, `Do'kon ID`, `Sana`, `Vaqt`, `Agent ID`, `Agent ismi`, `Lat`, `Lon`, `Rasm 1`, `Rasm 2`, `Rasm 3`, yashirin `FileID` ustunlari.

**`Agentlar`**: `Telegram ID`, `Ism`, `Telefon`, `Username`, `Til`, `Rol`, `Holat`, `Ro'yxatdan o'tgan vaqt`, `Kunlik reja`, `Oxirgi faollik`.

**`Log`** (faqat qo'shiladi): `Vaqt`, `Kim (ID)`, `Kim (ism)`, `Amal`, `Obyekt`, `Tafsilot`.

**`Sozlamalar`**: `Kalit`, `Qiymat` (`admin_group_id`, `daily_plan_default`, `report_time` = `21:00`, `notify_new_store` = `1`).

**`Statistika`**: formulalar bilan avtomatik: viloyat → tuman → mahalla bo'yicha do'konlar soni (`QUERY`/`COUNTIFS`), agentlar bo'yicha son, kunlar bo'yicha son. Mavjud ma'lumotga qarab o'zi yangilanadi.

Sheets dizayni (professional): shrift Roboto/Inter, sarlavha to'q ko'k fon + oq matn, navbat bilan qator ranglari (banding), qotirilgan sarlavha va birinchi 2 ustun, `Sana`/`Viloyat`/`Tuman`/`Mahalla`/`Agent ismi` ustunlarida filtr (`setBasicFilter`) yoqilgan, ustun kengliklari to'g'rilangan, `Holat` uchun shartli format, `INN` matn sifatida (boshidagi nol yo'qolmasin), lat/lon 6 xonali.

**Kvota va unumdorlik:** Sheets API cheklovlari bor (daqiqada ~60 o'qish/yozish so'rovi). Shuning uchun: (a) o'qishlar xotira keshida (TTL 20–30 s, yozishdan keyin tegishli kesh bekor qilinadi); (b) yozishlar bitta `asyncio.Queue` orqali ketma-ket bajariladi; (c) 429/5xx da eksponensial kutish bilan qayta urinish (max 5); (d) `values.append` ishlatiladi, butun varaqni qayta yozmaydi; (e) `ID` ni oluvchi qismda poyga holati (race condition) bo'lmasligi uchun navbat ichida hisoblanadi.

## 8. Google Drive

- `DRIVE_ROOT_FOLDER_ID` ichida: `Rasmlar/<YYYY-MM>/` papkalari avtomatik yaratiladi, `Zaxira/` papkasi zaxira nusxalar uchun.
- Fayl nomi: `<do'kon ID>_<n>_<YYYYMMDD_HHMMSS>.jpg`.
- Rasm yuklashdan oldin Pillow bilan siqiladi: uzun tomoni ≤ 1600 px, JPEG sifat 80, EXIF yo'naltirishi to'g'rilanadi (`ImageOps.exif_transpose`).
- Fayllar sukut bo'yicha "havola bilan hamma ko'ra oladi" qilinMAYDI. Sheets'dagi havola Drive egasining akkaunti bilan ochiladi. Mini App rasmlarni backend proxy orqali ko'rsatadi (`/api/photo/{file_id}`, faqat admin uchun, `Cache-Control` bilan).
- OAuth: bir marta ishga tushiriladigan `scripts/get_google_token.py` (loopback oqim) `GOOGLE_REFRESH_TOKEN` ni chiqaradi. Scope'lar: `drive` (yoki `drive.file` + papka), `spreadsheets`.

## 9. Mini App (admin paneli)

Kirish: faqat `admin`/`superadmin`. Autentifikatsiya: Telegram `initData` HMAC-SHA256 bilan serverda tekshiriladi (`auth_date` ≤ 24 soat), har API so'rovda `Authorization: tma <initData>`. Frontendga ishonilmaydi.

Bo'limlar (pastki navigatsiya paneli):
1. **Bosh sahifa:** KPI kartalari (jami do'konlar, bugun, shu hafta, faol agentlar), kunlik dinamika grafigi (oxirgi 30 kun), hududlar bo'yicha taqqoslash grafigi (top 10).
2. **Xarita:** Leaflet + markercluster, hamma do'konlar. Marker bosilsa pastdan "bottom sheet" ochiladi: rasmlar (karusel), nom, INN, telefon, hudud, agent, sana/vaqt, "Google Maps'da ochish" tugmasi. Filtrlar: viloyat → tuman → mahalla (bog'liq ro'yxatlar), sana oralig'i, agent.
3. **Do'konlar:** jadval/kartalar ro'yxati, qidiruv (nom, INN, telefon), o'sha filtrlar, sahifalash, tafsilot oynasi, admin uchun `🗑 O'chirish` (yumshoq, tasdiq bilan).
4. **Agentlar:** ro'yxat (holat, kiritgan soni), reyting (kun/hafta/oy), `✅ Qabul`, `🚫 Bloklash`, `♻️ Blokdan chiqarish`, kunlik rejani o'zgartirish. Superadmin uchun: admin tayinlash/olib tashlash.
5. **Hisobot:** joriy filtr bo'yicha `📥 Excel yuklab olish` (backend `.xlsx` yaratadi va botdan adminning chatiga hujjat sifatida yuboradi, chunki Telegram webview'da to'g'ridan-to'g'ri yuklab olish ishonchsiz), `📄 Google Sheets'ni ochish` (`openLink`), mahalla bo'yicha statistika jadvali.

Excel: varaqlar — `Do'konlar` (filtrga mos), `Hududlar bo'yicha` (viloyat/tuman/mahalla/son), `Agentlar bo'yicha`. Sarlavha formatlangan, filtr yoqilgan, ustun kengligi to'g'rilangan, qotirilgan sarlavha.

UI/UX talablari (professional daraja):
- Mobil-birinchi (360–430 px), Telegram mavzu o'zgaruvchilari (`--tg-theme-*`) orqali yorug'/qorong'i rejimga avtomatik moslashadi.
- Aniq tipografik ierarxiya, 8 px grid, yumaloq burchaklar (12–16 px), yengil soyalar, bitta aksent rang, bo'sh holat (empty state), yuklanish skeletonlari, xato holatlari, tegishli joyda mikro-animatsiyalar (150–250 ms), haptic feedback (`Telegram.WebApp.HapticFeedback`).
- Tugmalar kamida 44 px balandlikda, `MainButton`/`BackButton` Telegram API orqali.
- 3 til (uz, uz_cyr, ru).
- Ruxsat/xavfsizlik: barcha `<` `>` `&` kiritilgan matnlar ekranga chiqarilganda escape qilinadi (XSS yo'q).

## 10. Bildirishnomalar va fon vazifalari

- 🔔 Yangi do'kon saqlanganda `admin_group_id` guruhiga: rasm (1-chi) + sarlavha (nom, INN, hudud, agent, vaqt, xarita havolasi). Guruh sozlanmagan bo'lsa, shaxsan adminlarga yuboriladi.
- 📊 Har kuni `report_time` da (Toshkent vaqti) adminlarga hisobot: bugun jami, agentlar bo'yicha (kamayish tartibida), eng yaxshi agent, kunlik reja bajarilishi.
- 💾 Har yakshanba 03:00 da spreadsheet'ning nusxasi `Zaxira/` ga olinadi (`Drive files.copy`), oxirgi 8 ta saqlanadi, eskilari o'chiriladi.
- 🏆 Reyting Mini App'da; agent botda ham `/top` bilan o'z o'rnini ko'ra oladi (kun/hafta/oy).
- Render free uxlab qolmasligi uchun `GET /healthz` (tez, Sheets'ga tegmaydi) mavjud; foydalanuvchiga tashqi ping xizmati (UptimeRobot, 5 daqiqa) sozlash yo'riqnomasi beriladi. Bundan tashqari ichki scheduler uxlagan holda ishlamasligi mumkinligi hujjatlashtiriladi.

## 11. Konfiguratsiya (`.env`, hech qachon commit qilinmaydi)

`BOT_TOKEN`, `WEBHOOK_SECRET` (tasodifiy satr, Telegram `secret_token`), `PUBLIC_BASE_URL` (Render URL), `SUPERADMIN_ID`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN`, `SPREADSHEET_ID`, `DRIVE_ROOT_FOLDER_ID`, `ADMIN_GROUP_ID` (ixtiyoriy), `TZ=Asia/Tashkent`, `NOMINATIM_USER_AGENT` (aloqa emailli), `REDIS_URL` (ixtiyoriy; bo'lmasa FSM xotirada). `.env.example` mavjud bo'lishi shart.

## 12. Xavfsizlik va sifat

- Sirlar faqat env'da; loglarda token, refresh token, initData chiqmaydi.
- Webhook faqat to'g'ri `X-Telegram-Bot-Api-Secret-Token` bilan qabul qilinadi.
- Barcha foydalanuvchi matni validatsiya qilinadi; Sheets formula in'ektsiyasidan himoya: `=`, `+`, `-`, `@` bilan boshlanadigan matnlar oldidan `'` qo'shiladi (HYPERLINK formulalarini o'zimiz yozamiz, foydalanuvchi matnini formulaga to'g'ridan-to'g'ri qo'shmaymiz, `"` ni ikkilantiramiz).
- Har bir handler `try/except` bilan; foydalanuvchiga tushunarli xabar, adminga (yoki logga) texnik tafsilot. Ishlov berilmagan xatolar `Log`/stdout'ga yoziladi.
- Rate-limit: bir foydalanuvchidan soniyasiga ko'pi bilan 3 ta xabar (oddiy middleware).
- Testlar: INN/telefon validatsiyasi, i18n kalitlar tengligi, Nominatim javobini ajratish (fixture), initData HMAC tekshiruvi, Sheets qator xaritalash, formula in'ektsiyasidan himoya, Excel generatsiyasi.
- Kod toza: tiplar (type hints), `ruff` bilan lint, modul tuzilmasi quyidagicha:

```
app/
  main.py            # FastAPI + webhook + lifespan (scheduler, queue)
  config.py
  bot/
    __init__.py, dispatcher.py, middlewares.py, keyboards.py
    handlers/ (start.py, registration.py, store_flow.py, my_records.py, stats.py, admin.py, common.py)
    states.py
  i18n/ (__init__.py, uz.py, uz_cyr.py, ru.py)
  services/
    sheets.py, drive.py, geocode.py, images.py, excel.py, notify.py, stats.py, backup.py, auth.py
  api/ (router.py, deps.py, routes_*.py)
  webapp/ (index.html, css/, js/, assets/)
scripts/get_google_token.py, scripts/init_sheets.py
tests/
render.yaml, requirements.txt, .env.example, README.md, SPEC.md
```

## 13. Qamrab olinmaydigan narsalar (hozircha)

Offline rejim, agent yo'li xaritasi, "ish kuni" tugmasi, lokatsiya bo'yicha dublikat aniqlash, do'kon turi, audit tarixi interfeysi (Log varag'i yoziladi, lekin Mini App'da ko'rsatilmaydi), ommaviy xabar yuborish. Rasmning GPS ma'lumoti bo'yicha tekshiruv ham yo'q: Telegram rasmdan EXIF'ni olib tashlaydi.
