# PROMPT 5 / 5 — Rejalashtirilgan vazifalar, zaxira, mustahkamlash va Render'ga joylash

Loyiha ildizidagi `SPEC.md` ni **to'liq qayta o'qi** (8, 10, 11, 12-bo'limlarga alohida e'tibor ber). 1–4 bosqichlar bajarilgan. Mavjud kodni qayta yozma, ustiga qur. SPEC bilan zid ish qilma; tushunarsiz joyda to'xtab so'ra.

## Maqsad
Qolgan avtomatik funksiyalarni (kunlik hisobot, haftalik zaxira), loyihani mustahkamlash (xavfsizlik, xatolar, unumdorlik) va Render free'da barqaror joylashni yakunlash.

## Bajariladigan ishlar

1. **Rejalashtiruvchi (`app/main.py` lifespan + `services/backup.py`, `services/notify.py`).** `APScheduler` (`AsyncIOScheduler`, tz `Asia/Tashkent`):
   - 📊 **Kunlik hisobot**: `Sozlamalar.report_time` (sukut `21:00`) da barcha adminlarga: bugungi jami yangi do'konlar, qayta tashriflar, agentlar bo'yicha ro'yxat (kamayish tartibida, har biri "ism — N / reja"), eng yaxshi agent 🏆, jami faol agentlar va bugun ish qilmaganlar soni. Uch tilda (har admin o'z tilida). `report_time` o'zgarsa, qayta ishga tushirmasdan qo'llanadi (har daqiqada tekshiruvchi yoki jobni qayta rejalashtirish). Bir kunda ikki marta ketmasligi uchun "oxirgi yuborilgan sana" `Sozlamalar` da saqlanadi (Render qayta ishga tushsa ham takrorlanmaydi). Ilova uxlab qolib, vaqtdan keyin uyg'onsa, o'sha kunning hisoboti hali yuborilmagan bo'lsa, ishga tushishdan keyin 5 daqiqa ichida yuboriladi (misfire/coalesce sozlamalari).
   - 💾 **Haftalik zaxira**: yakshanba 03:00, `Drive files.copy` bilan spreadsheet nusxasi `Zaxira/` ga `Zaxira_YYYY-MM-DD` nomi bilan; 8 tadan eskilari o'chiriladi (faqat nomi shu andozaga mos va `Zaxira/` ichidagilar; boshqa fayllarga tegilmaydi). Natija `Log` ga, xato bo'lsa superadminga xabar.
   - Ikkala vazifa ham xatoda ilovani yiqitmaydi.
   - Qo'lda ishga tushirish: superadmin uchun `/report_now` va `/backup_now`.
2. **Mustahkamlash.**
   - Barcha tashqi chaqiruvlarda (Telegram yuklab olish, Drive, Sheets, Nominatim) timeout va cheklangan qayta urinish borligini tekshir, yetishmaganini qo'sh.
   - Bot qayta ishga tushganda (Render uxlab-uyg'onishi) FSM yo'qolsa, foydalanuvchi qotib qolmasin: holati yo'q foydalanuvchi callback bosganda "Sessiya tugagan, qaytadan boshlang" va menyu.
   - Katta rasmlar va ko'p odam bir vaqtda yuklaganda xotira: rasm baytlari qayta ishlangach darhol bo'shatiladi, bir vaqtda ishlanadigan yuklashlar soni cheklangan (semafor, masalan 4).
   - Webhook va API endpointlarida so'rov hajmi cheklovlari; `CORS` yopiq (Mini App bir xil origin).
   - Loglarda sirlar yo'qligini grep bilan tekshir (`BOT_TOKEN`, refresh token, `initData`).
   - Mavjud `ruff`, `pytest` ni CI'ga tayyor holga keltir; `.github/workflows/ci.yml` (lint + test) qo'sh.
3. **Joylash (`render.yaml`, `README.md`).**
   - `render.yaml`: `web` xizmat, `plan: free`, Python runtime, `buildCommand: pip install -r requirements.txt`, `startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT`, `healthCheckPath: /healthz`, `envVars` ro'yxati (sirlar `sync: false`), `TZ=Asia/Tashkent`.
   - `README.md` ga **nol dan** to'liq yo'riqnoma (oddiy tilda, nomaxsus odam bajara oladigan): 1) BotFather'da bot yaratish va `/setdomain` / Mini App tugmasi, 2) Telegram ID'ni bilish (@userinfobot), 3) Google Cloud sozlash va `get_google_token.py`, 4) Drive papkasi va spreadsheet yaratish, ID'larni topish, 5) `init_sheets.py` ishga tushirish, 6) GitHub'ga yuklash (sirlarsiz!), 7) Render'da `New + → Blueprint` yoki `Web Service` yaratish va env o'zgaruvchilarni kiritish, 8) `PUBLIC_BASE_URL` ni to'g'rilab qayta deploy qilish, 9) botni sinash ro'yxati, 10) UptimeRobot'da `GET https://<url>/healthz` ni 5 daqiqada pinglash (Render free 15 daqiqa so'rovsiz qolsa uxlaydi, birinchi so'rov 30–60 s kechikadi; ping buni kamaytiradi, lekin kafolatlamaydi — bu cheklovni rost yoz), 11) admin guruhini ulash (`/setgroup`), 12) keng tarqalgan muammolar va yechimlari (token 7 kunda tugashi — OAuth app'ni `Production` ga o'tkazish, Sheets kvotasi, webhook 403, Mini App ochilmasligi).
   - **Render free cheklovlari bo'limi** (halol): diskda saqlanmaydi (hamma narsa Sheets/Drive'da), xizmat uxlaydi, rejalashtirilgan vazifalar faqat xizmat uyg'oq paytda ishlaydi (shuning uchun ping tavsiya etiladi), oyiga ~750 soat bepul limiti.
4. **Yakuniy tekshiruv va hujjatlar.**
   - `docs/TEST_CHECKLIST.md`: qo'lda sinov ro'yxati (ro'yxatdan o'tish, rad/qabul, bloklash, har til, do'kon kiritish barcha tarmoqlari: dublikat INN, forward lokatsiya, mahalla qo'lda, tashrif; tahrirlash, statistika, Mini App ekranlari, Excel, kunlik hisobot, zaxira).
   - `docs/ARCHITECTURE.md`: bir sahifalik arxitektura sxemasi (matn/ASCII), ma'lumotlar oqimi, ma'lum cheklovlar (Telegram lokatsiya yolg'onini 100% to'sib bo'lmasligi, Nominatim mahallani topa olmasligi, Sheets kvotasi ~100 agentgacha mo'ljallangani, Render uxlashi).
   - Butun loyiha bo'yicha **yakuniy audit**: SPEC bandlarini birma-bir tekshirib chiq va jadval qil: "bajarildi / qisman / bajarilmadi" va sababi. Bajarilmagan yoki qisman bo'lganini yashirma.

## Qabul mezonlari
- [ ] `pytest` yashil, `ruff` toza, CI fayli bor.
- [ ] Kunlik hisobot va zaxira funksiyalari qo'lda buyruq bilan ishga tushadi (mock testlar bilan kafolatlangan), takroriy yuborishdan himoyalangan.
- [ ] `render.yaml` va README bo'yicha yangi odam nol dan joylay oladi (yo'riqnomani bosqichma-bosqich o'zing "quruq" tekshirib chiq).
- [ ] Loglarda sir yo'q; `.env` va token fayllari git'ga tushmaydi (`git ls-files` bilan tekshir).
- [ ] SPEC bo'yicha yakuniy audit jadvali berilgan.
- [ ] Oxirida: nima qilindi, nima haqiqiy muhitda (Render, Telegram, Google) tekshirilmaganini aniq ayt.

Yangi funksiya qo'shma. SPEC'dagi 13-bo'lim (qamrab olinmaydiganlar) ga rioya qil.
