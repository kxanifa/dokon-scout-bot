# PROMPT 2 / 5 — Bot: ro'yxatdan o'tish, tillar, ruxsat tizimi, admin buyruqlari

Loyiha ildizidagi `SPEC.md` ni **to'liq qayta o'qi** (1–4, 6 va 10-bo'limlarga alohida e'tibor ber). 1-bosqich bajarilgan: `config`, `sheets`, `drive`, `i18n` skeleti, FastAPI va `/healthz` mavjud. Shularni qayta yozma, ustiga qur. SPEC bilan zid ish qilma; tushunarsiz joyda to'xtab so'ra.

## Maqsad
Botni webhook rejimida ishga tushirish va foydalanuvchi kirishi/ruxsati/til/rol mantig'ini to'liq yakunlash. Do'kon kiritish oqimi (3-bosqich) bu yerda yozilmaydi.

## Bajariladigan ishlar

1. **Webhook integratsiyasi (`app/main.py`, `app/bot/dispatcher.py`).**
   - `lifespan` ichida `Bot` va `Dispatcher` yaratiladi, `set_webhook(PUBLIC_BASE_URL + "/tg/webhook", secret_token=WEBHOOK_SECRET, drop_pending_updates=True, allowed_updates=[...])`.
   - `POST /tg/webhook` `X-Telegram-Bot-Api-Secret-Token` ni tekshiradi (mos kelmasa 403), update'ni `dp.feed_update` ga uzatadi, tez 200 qaytaradi (og'ir ishlar ushlab turilmaydi).
   - FSM xotirasi: `REDIS_URL` berilgan bo'lsa `RedisStorage`, aks holda `MemoryStorage`.
2. **Middleware'lar (`middlewares.py`).**
   - `UserContextMiddleware`: har update'da foydalanuvchini `Agentlar` keshidan oladi (yo'q bo'lsa `None`), `lang`, `role`, `status` ni handlerga uzatadi. `Oxirgi faollik` ni 10 daqiqada bir martadan ko'p yozmaydi (kvotani tejash).
   - `AccessMiddleware`: `blocked` → jim yoki "Kirish cheklangan"; `pending` → "So'rovingiz ko'rib chiqilmoqda"; ro'yxatdan o'tmaganlar faqat `/start` va ro'yxatdan o'tish holatlariga kira oladi. Superadmin har doim `active` va `superadmin` (hatto `Agentlar` varag'ida bo'lmasa ham, birinchi `/start` da avtomatik yoziladi).
   - `ThrottleMiddleware`: foydalanuvchiga soniyasiga ≤3 xabar; ortig'i jim tashlanadi.
   - Global xato ushlovchi: foydalanuvchiga tushunarli ("Xatolik yuz berdi, qayta urinib ko'ring"), tafsilot logga va `Log` varag'iga.
3. **Ro'yxatdan o'tish (`handlers/start.py`, `handlers/registration.py`).**
   - `/start`: yangi foydalanuvchiga 3 tilli til tanlash (inline tugmalar: 🇺🇿 O'zbekcha, 🇺🇿 Ўзбекча, 🇷🇺 Русский). Til tanlangach ism so'raladi (2–60 belgi), keyin `request_contact=True` tugmasi bilan telefon. Faqat foydalanuvchining O'Z kontakti qabul qilinadi (`contact.user_id == from_user.id`), aks holda rad.
   - So'ng `Agentlar` ga `pending` holatida yoziladi (Telegram ID, ism, telefon, username, til, rol=`agent`, ro'yxatdan o'tgan vaqt).
   - Barcha adminlarga (rol `admin`/`superadmin`, `active`) so'rov xabari: ism, telefon, username, vaqt + inline `✅ Qabul qilish` / `❌ Rad etish`. Birinchi bosgan admin qaror qiladi; xabar tahrirlanib "Qaror: kim, qachon" ko'rsatiladi (ikkinchi admin qayta bosa olmaydi; poyga holatidan himoyalan).
   - Qabul qilinsa agentga o'z tilida xabar va asosiy menyu keladi; rad etilsa xabar keladi va qayta urinish mumkin bo'lmaydi (holat `blocked`, sababsiz). Admin keyin Mini App/buyruq orqali qayta qabul qila oladi.
   - Agent allaqachon ro'yxatda bo'lsa, `/start` uni asosiy menyuga qaytaradi (qayta ro'yxatdan o'tkazmaydi).
4. **Asosiy menyu (`keyboards.py`).** Reply klaviatura (SPEC 5): `➕ Yangi do'kon`, `📋 Mening yozuvlarim`, `📊 Statistikam`, `⚙️ Til`. Adminlarga qo'shimcha qator: `🛠 Admin panel` (`WebAppInfo(url=PUBLIC_BASE_URL + "/app")`). Tugma matnlari tanlangan tilga qarab. Hozircha `Yangi do'kon`, `Yozuvlarim`, `Statistikam` bosilganda "Tez orada" deb javob beradi (3-bosqichda to'ldiriladi), lekin handlerlar uchun joy (router) tayyor bo'lsin.
5. **Tilni almashtirish.** `⚙️ Til` va `/lang`: inline tanlov, `Agentlar` varag'ida yangilanadi, menyu yangi tilda qayta chiqadi.
6. **Admin buyruqlari (`handlers/admin.py`).** Faqat tegishli rol uchun (tekshiruv filtr orqali):
   - `/agents` — agentlar ro'yxati (holat bo'yicha guruhlangan, sahifalab).
   - `/block <id>`, `/unblock <id>` — admin. Superadminni va o'zini bloklab bo'lmaydi.
   - `/addadmin <id>`, `/removeadmin <id>` — faqat superadmin. Qo'shilayotgan foydalanuvchi `Agentlar` da bo'lishi kerak (yo'q bo'lsa, tushunarli xabar).
   - `/setgroup` — admin guruhida yozilsa, shu guruhning ID'sini `Sozlamalar.admin_group_id` ga yozadi (faqat superadmin).
   - Har bir o'zgarish `Log` varag'iga yoziladi (kim, amal, obyekt, tafsilot).
   - Bloklangan/rad etilgan va qabul qilingan agentlarga o'z tilida xabar boradi.
7. **i18n.** Yangi matnlarning hammasini uch tilga (uz lotin, uz kirill, ru) qo'sh. Kirill va rus tarjimalari tabiiy bo'lsin (mashina tarjimasiga o'xshamasin). Tenglik testi yashil bo'lsin.
8. **Testlar.** Ro'yxatdan o'tish oqimi (aiogram'ning test update'lari yoki handlerlarni to'g'ridan-to'g'ri chaqirish), kontakt egasi tekshiruvi, ikki admin bir vaqtda tugma bosganda faqat bittasi ishlashi, AccessMiddleware holatlari, rol cheklovlari (`addadmin` faqat superadmin), webhook secret tekshiruvi. Sheets servisi mock qilinadi.

## Qabul mezonlari
- [ ] `pytest` yashil, `ruff` toza.
- [ ] Lokal sinov uchun yo'riqnoma: `ngrok`/`cloudflared` tunnel orqali `PUBLIC_BASE_URL` ni berib botni ishga tushirish qadamlari README'ga qo'shilgan.
- [ ] Yangi foydalanuvchi: til → ism → kontakt → adminga so'rov → admin qabul → agent menyusi, butun zanjir ishlaydi (haqiqiy bot tokeni bilan tekshira olmasang, buni ochiq ayt va mock testlar bilan kafolatla).
- [ ] Noto'g'ri secret bilan webhook 403 qaytaradi.
- [ ] Hech qanday handler `blocked`/`pending` foydalanuvchi uchun ishlamaydi.
- [ ] Oxirida: nima qilindi, nima haqiqiy muhitda tekshirilmadi haqida qisqa hisobot.

Do'kon kiritish oqimi, Mini App va rejalashtirilgan vazifalarni bu bosqichda YOZMA.
