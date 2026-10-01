# PROMPT 4 / 5 — Admin Mini App (API + professional UI) va Excel eksport

Loyiha ildizidagi `SPEC.md` ni **to'liq qayta o'qi** (3, 7, 9-bo'limlarga alohida e'tibor ber). 1–3 bosqichlar bajarilgan: servislar, bot, ro'yxatdan o'tish, do'kon oqimi, statistika mavjud. Ularni qayta yozma, ustiga qur. SPEC bilan zid ish qilma; tushunarsiz joyda to'xtab so'ra.

## Maqsad
Adminlar uchun Telegram Mini App: xarita, filtrlar, statistika, agentlarni boshqarish va Excel eksport. Backend API (FastAPI) va frontend (build'siz HTML/CSS/JS), ikkalasi bitta Render xizmatida.

## A. Backend API (`app/api`)

1. **Autentifikatsiya (`services/auth.py`, `api/deps.py`).** `Authorization: tma <initData>`: HMAC-SHA256 (`WebAppData` kaliti bilan) tekshiruvi, `auth_date` ≤ 24 soat, `hash` ni vaqt-doimiy solishtirish (`hmac.compare_digest`). Foydalanuvchi `Agentlar` dan olinadi: faqat `admin`/`superadmin` va `active`. Aks holda 401/403. `superadmin_only` bog'liqligi alohida. Til foydalanuvchi profilidan.
2. **Endpointlar** (hammasi JSON, `Sheets` keshidan o'qiydi, qo'shimcha Sheets so'rovi minimal):
   - `GET /api/me` — ism, rol, til, sozlamalar (reja, `Sheets` havolasi).
   - `GET /api/meta/regions` — viloyat → tuman → mahalla daraxti (faqat `faol` do'konlardan, har tugunda soni).
   - `GET /api/stats/summary` — jami, bugun, hafta, oy, faol agentlar, qayta tashriflar.
   - `GET /api/stats/daily?days=30`, `GET /api/stats/regions?level=viloyat|tuman|mahalla&parent=…&limit=…`.
   - `GET /api/stores` — filtrlar: `viloyat`, `tuman`, `mahalla`, `agent_id`, `date_from`, `date_to`, `q` (nom/INN/telefon bo'yicha qidiruv, katta-kichik harfga befarq), sahifalash (`page`, `page_size` ≤100), tartib. Javob: ro'yxat + jami soni.
   - `GET /api/stores/map` — xarita uchun yengil ro'yxat (`id, lat, lon, nom, mahalla`), shu filtrlar bilan, hajmi cheklangan va gzip.
   - `GET /api/stores/{id}` — to'liq ma'lumot + tashriflar tarixi + rasm URL'lari (`/api/photo/{file_id}`).
   - `DELETE /api/stores/{id}` — yumshoq o'chirish (`Holat=o'chirilgan`), `Log` ga yoziladi.
   - `GET /api/photo/{file_id}` — Drive'dan oqim bilan, faqat admin, fayl ID'si haqiqatan `Do'konlar`/`Tashriflar` dagi ID'lardan biri bo'lishi shart (ixtiyoriy Drive faylini o'qib bo'lmasin!), `Cache-Control: private, max-age=86400`. Katta rasm uchun `?w=` bilan kichraytirilgan variant (Pillow, keshda).
   - `GET /api/agents` — ro'yxat + kiritgan soni (bugun/hafta/oy/jami), `GET /api/agents/ranking?period=day|week|month`.
   - `POST /api/agents/{id}/approve|block|unblock`, `POST /api/agents/{id}/plan` (kunlik reja). Superadmin: `POST /api/admins/{id}` / `DELETE /api/admins/{id}`. Cheklovlar 2-bosqichdagidek (superadmin/o'zini bloklab bo'lmaydi). Hammasi `Log` ga.
   - `POST /api/export/excel` — joriy filtr bilan `.xlsx` yaratadi (SPEC 9: `Do'konlar`, `Hududlar bo'yicha`, `Agentlar bo'yicha` varaqlari, formatlangan sarlavha, filtr, qotirilgan qator, ustun kengligi, `INN` matn) va botdan adminning chatiga hujjat qilib yuboradi; javob: `{ok:true}`. Fayl nomi `dokonlar_YYYY-MM-DD_HHMM.xlsx`. 50 000 qatordan oshmasin, katta bo'lsa tushunarli xato. Bir adminga daqiqada ≤3 eksport.
3. **Statik fayllar.** `/app` ostida `app/webapp` xizmat qilinadi (`StaticFiles(html=True)`), `index.html` keshlanmaydi, `css/js` versiya parametri bilan.
4. Xatolar bir xil formatda: `{ "error": "kod", "message": "…" }`, ichki xatolar tafsilotsiz.

## B. Frontend (`app/webapp`) — professional UI/UX

Vanilla JS (ES modullar), hash-routing, kichik komponentlar. CDN: Leaflet, Leaflet.markercluster, Chart.js (versiyalarni qat'iy ko'rsat, SRI imkon bo'lsa). Telegram WebApp SDK.

**Dizayn tizimi (`css/tokens.css` + `css/app.css`):** `--tg-theme-*` o'zgaruvchilariga tayanadigan token'lar (rang, radius 12/16, 8 px grid, soyalar, tipografiya shkalasi: 12/14/16/20/28, shrift tizimniki), yorug'/qorong'i rejim avtomatik, bitta aksent rang. Komponentlar: kartalar, KPI plitkalari, chip-filtrlar, bottom sheet (tortib yopiladi), segmentli kontrol, ro'yxat elementlari, badge'lar (holat ranglari), skeleton yuklanish, bo'sh holat (ikonka + matn + harakat tugmasi), toast, tasdiq dialogi. Animatsiya 150–250 ms, `prefers-reduced-motion` hurmat qilinadi. Tugmalar ≥44 px. Haptic feedback, `BackButton`, kerak joyda `MainButton`. Xavfsiz-zona (safe-area) hisobga olinadi.

**Ekranlar** (pastki navigatsiya, 5 ta):
1. **Bosh sahifa:** salomlashish, 4 ta KPI (jami, bugun, hafta, faol agentlar), 30 kunlik dinamika (chiziqli grafik), top-10 hudud (gorizontal bar), "Eng faol agentlar" (top 3 bugun).
2. **Xarita:** to'liq ekran xarita, markercluster, yuqorida filtr chiplari (Viloyat / Tuman / Mahalla / Sana / Agent) — bosilganda bottom sheet'da bog'liq tanlov (viloyat tanlansa tumanlar yangilanadi va h.k.), "Filtrni tozalash". Marker bosilganda bottom sheet: rasm karuseli (surish), nom, INN, telefon (bosilsa qo'ng'iroq), hudud, agent, sana/vaqt, `📍 Google Maps'da ochish`, `Tafsilot`. Filtr o'zgarsa xarita chegaralari shu natijaga moslashadi (`fitBounds`). Ko'rinadigan do'kon soni hisoblagichi. "Mening joyim" tugmasi.
3. **Do'konlar:** qidiruv satri (debounce 300 ms), filtrlar (xarita bilan bir xil komponent), cheksiz skroll yoki "Yana yuklash", kartochkalar (kichik rasm, nom, INN, mahalla, agent, vaqt). Tafsilot ekrani: katta rasmlar (bosilsa to'liq ekran ko'rish), barcha maydonlar, tashriflar tarixi, `🗑 O'chirish` (tasdiq bilan).
4. **Agentlar:** segmentlar `Faol / Kutilmoqda / Bloklangan`, reyting (`Bugun/Hafta/Oy` segmenti, 🥇🥈🥉), har agent kartochkasida amallar: qabul qilish / bloklash / blokdan chiqarish / reja o'zgartirish. Superadminga "Admin qilish/olib tashlash".
5. **Hisobot:** joriy filtr xulosasi (necha do'kon), `📥 Excel yuklab olish` (tugma holati: yuborilmoqda → "Chatga yuborildi ✅"), `📄 Google Sheets'da ochish`, mahalla bo'yicha statistika jadvali (viloyat → tuman → mahalla ochiladigan daraxt, sonlar bilan).

**Umumiy:** 3 til (`i18n.js`, uz/uz_cyr/ru, kalitlar tengligi uchun tekshiruv skripti), barcha dinamik matn escape qilinadi (XSS yo'q; `innerHTML` ga xom ma'lumot qo'yilmaydi), tarmoq xatosida "Qayta urinish" holati, 401 bo'lsa "Kirish uchun botni qayta oching". Lazy-load rasmlar, grafiklar ko'rinishga kelganda chiziladi. Ilova 360 px dan 430 px gacha va planshetda yaxshi ko'rinsin, gorizontal skroll bo'lmasin.

## C. Testlar va sifat
- `initData` tekshiruvi: to'g'ri, buzilgan hash, eskirgan `auth_date`, begona foydalanuvchi.
- Rol cheklovlari: oddiy agent `/api/*` ga kira olmaydi; faqat superadmin admin tayinlaydi.
- `/api/photo`: ro'yxatda yo'q fayl ID → 404.
- Filtrlar (hudud, sana oralig'i, qidiruv, agent), sahifalash, chegara qiymatlar.
- Excel: varaqlar, sarlavhalar, qatorlar soni filtrga mosligi, `INN` matn.
- Frontend uchun: `i18n` kalitlar tengligi skripti va asosiy yordamchi funksiyalar (formatlash, escape) uchun yengil testlar.
- Brauzerda tekshirish: lokal serverni ishga tushirib, Mini App'ni mobil o'lchamda (375×812) va qorong'i/yorug' mavzuda ko'zdan kechir; skrinshotlar bilan nuqsonlarni top va tuzat. Telegram tashqarisida sinash uchun faqat `DEBUG=1` da ishlaydigan, `initData` ni o'tkazib yuboruvchi dev rejimi qo'sh (productionda butunlay o'chiq, buni test bilan kafolatla).

## Qabul mezonlari
- [ ] `pytest` yashil, `ruff` toza.
- [ ] Mini App'ning 5 ekrani ishlaydi; filtrlar bog'liq (viloyat → tuman → mahalla); xarita va ro'yxat bir xil filtrni ishlatadi.
- [ ] Excel chatga keladi va filtrga mos.
- [ ] Hech bir admin bo'lmagan foydalanuvchi API'dan ma'lumot ololmaydi; ixtiyoriy Drive faylini o'qib bo'lmaydi.
- [ ] Mobil ko'rinish, qorong'i rejim va bo'sh/xato holatlari ko'zdan kechirilgan (skrinshot asosida).
- [ ] Oxirida: nima qilindi, nima haqiqiy Telegram ichida tekshirilmadi haqida qisqa hisobot.

Rejalashtirilgan vazifalar (kunlik hisobot, zaxira) va deployni bu bosqichda YOZMA.
