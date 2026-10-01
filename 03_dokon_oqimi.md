# PROMPT 3 / 5 — Bot: do'kon kiritish oqimi, hududni aniqlash, yozuvlar va statistika

Loyiha ildizidagi `SPEC.md` ni **to'liq qayta o'qi** (5, 6, 7, 8-bo'limlarga alohida e'tibor ber). 1- va 2-bosqichlar bajarilgan: servislar (`sheets`, `drive`, `images`), i18n, webhook, middleware'lar, ro'yxatdan o'tish va ruxsat tizimi mavjud. Ularni qayta yozma, ustiga qur. SPEC bilan zid ish qilma; tushunarsiz joyda to'xtab so'ra.

## Maqsad
Agentning asosiy ishi: yangi do'kon qo'shish (rasm → lokatsiya → hudud → INN → nom → telefon → xulosa → saqlash), shuningdek `Mening yozuvlarim`, tahrirlash, `Statistikam` va kunlik reja.

## Bajariladigan ishlar

1. **Geokodlash (`services/geocode.py`).** Nominatim reverse (SPEC 5.3): `httpx.AsyncClient`, timeout 8 s, so'rovlar orasida ≥1 s (global lock + oxirgi so'rov vaqti), `User-Agent=NOMINATIM_USER_AGENT`, natijani koordinatani 5 xonaga yaxlitlab xotira keshida saqlash (LRU, cheklangan hajm). Javobdan viloyat/tuman/mahallani SPEC'dagi kalit zanjirlari bo'yicha ajratadigan sof funksiya (`parse_address`) — uni haqiqiy javob namunalari (fixture) bilan test qil, jumladan: Toshkent shahri (viloyat o'rnida shahar), tuman o'rnida shahar, mahalla yo'q holat, bo'sh javob. Viloyat nomlarini bir xillashtir ("Toshkent shahri", "Toshkent viloyati", "Samarqand viloyati" va h.k.; "region", "oblast", "viloyati" qo'shimchalaridagi farqlarni normallashtir) — filtr va statistikada bir hudud turli yozilmasligi uchun. Xato bo'lsa `None` qaytaradi, oqim qo'lda kiritishga o'tadi.
2. **FSM holatlari (`states.py`) va oqim (`handlers/store_flow.py`).** SPEC 5-bo'limdagi 8 qadamni aynan bajar:
   - Rasm: 1 ta majburiy, keyin "Yana rasm (2 tagacha)" / "Davom etish". `file_id` lar FSM'da saqlanadi, haqiqiy yuklash faqat oxirida. Rasm sifatida yuborilgan `image/*` hujjat ham qabul qilinadi. Boshqa turdagi xabarga tushunarli javob.
   - Lokatsiya: faqat `request_location` tugmasi; forward qilingan (`forward_origin`), `venue`, matn orqali yozilgan koordinata rad etiladi, sababi aytiladi.
   - Hudud: geokodlash natijasi + `✅ To'g'ri` / `✏️ Mahallani yozish` / `✏️ Hammasini tuzatish`. Mahalla bo'sh bo'lsa, qo'lda kiritish majburiy. Qo'lda kiritilgan matn tozalanadi (ortiqcha bo'shliq, bosh harf), 2–80 belgi.
   - INN: faqat 9 xonali raqam. Dublikat bo'lsa SPEC'dagi 3 tugmali tanlov. `Yangi tashrif` tanlansa, nom/telefon so'ralmaydi: oqim darhol xulosaga o'tadi va `Tashriflar` ga yoziladi (eski do'konga bog'lanadi).
   - Nom: 2–100 belgi. Telefon: ixtiyoriy, `+998XXXXXXXXX` ga normallashtirish (`utils/validators.py` ichida, testlar bilan: `901234567`, `998901234567`, `+998 90 123-45-67`, `(90) 123 45 67` lar to'g'ri; harf aralash va noto'g'ri uzunlik rad).
   - Xulosa: rasm(lar) albomi (`send_media_group`) + matn, `✅ Saqlash` / `✏️ Tahrirlash` (qaysi maydon) / `❌ Bekor qilish`.
   - Har qadamda `⬅️ Orqaga` va `❌ Bekor qilish`. Menyu tugmasi yoki `/start` bosilsa, "Davom ettirish / Bekor qilish". Bir vaqtda faqat bitta jarayon.
3. **Saqlash.** `✅ Saqlash` bosilganda: tugmani darhol o'chir (ikki marta bosishdan himoya — idempotentlik kaliti FSM'da), "Saqlanmoqda…" holati, Telegram'dan rasmlarni yuklab olish → siqish → Drive'ga yuklash → `Do'konlar` (yoki `Tashriflar`) ga qator yozish → `Log` → agentga "Saqlandi ✅ №<ID>" + bugungi hisob ("Bugun: 7/20"). Drive/Sheets xatosi bo'lsa: hech narsa yarim yozilgan holda qolmasin (Drive'ga yuklangan fayllar yozuv muvaffaqiyatsiz bo'lsa o'chiriladi yoki keyingi urinishda qayta ishlatiladi), agentga xabar, ma'lumot FSM'da saqlanib turadi va "🔁 Qayta urinish" tugmasi chiqadi. Kunlik reja bajarilgan lahzada tabrik xabari (bir marta).
4. **Bildirishnoma (`services/notify.py`, hozircha faqat shu qism).** Yangi do'kon (va tashrif) saqlanganda SPEC 10-bo'limdagi 🔔 xabar: `admin_group_id` ga, bo'lmasa adminlarga. `Sozlamalar.notify_new_store=0` bo'lsa yuborilmaydi. Yuborish xatosi saqlashni to'xtatmasin (alohida `try/except`, fonda).
5. **`📋 Mening yozuvlarim` va tahrirlash (`handlers/my_records.py`).** Faqat o'zining `faol` yozuvlari, oxirgisi birinchi, 5 tadan sahifalab (inline `◀️ ▶️`). Yozuv kartochkasi: asosiy maydonlar + `✏️ Tahrirlash`. Tahrirlanadigan maydonlar: nom, telefon, INN (xuddi shu validatsiya; boshqa do'kon bilan to'qnashsa ogohlantirish), viloyat/tuman/mahalla, rasm almashtirish (eski fayl Drive'dan o'chirilmaydi, faqat havola yangilanadi). Agent boshqa agent yozuviga tegolmaydi (egalik tekshiruvi serverda, callback ma'lumotiga ishonma). Har tahrirda `Tahrirlangan vaqt`, `Tahrir qilgan` va `Log` yangilanadi.
6. **`📊 Statistikam` va `/top` (`handlers/stats.py`, `services/stats.py`).** Bugun / hafta (dushanbadan) / oy / jami; kunlik reja progressi ("12/20 ▓▓▓▓▓▓░░░░ 60%"); `/top` — kun/hafta/oy bo'yicha reyting, agentning o'z o'rni belgilangan (top 10 + o'zi). Hisoblash `Do'konlar` keshidan (qo'shimcha Sheets so'rovi yo'q), vaqt zonasi Toshkent. `Tashriflar` ham kunlik hisobga qo'shiladimi? — Yo'q: reja va reyting faqat YANGI do'konlarni sanaydi (tashrif alohida ko'rsatiladi: "Qayta tashriflar: N").
7. **Kunlik reja.** `Agentlar.Kunlik reja` bo'sh bo'lsa `Sozlamalar.daily_plan_default` olinadi.
8. **i18n.** Barcha yangi matnlar uch tilda; tenglik testi yashil.
9. **Testlar.** `parse_address` (fixture'lar), validatorlar (INN, telefon), forward/venue lokatsiyani rad etish, dublikat INN tarmoqlari (3 tugma), "tashrif" yo'li, ikki marta bosishdan himoya, Drive xatosida holat saqlanishi, egalik tekshiruvi (begona yozuvni tahrirlab bo'lmaydi), statistika hisoblari (chegara kunlar: yarim tun, hafta boshi, oy boshi; Toshkent vaqti).

## Qabul mezonlari
- [ ] `pytest` yashil, `ruff` toza.
- [ ] To'liq oqim mock'lar bilan boshdan oxirigacha o'tadi: rasm → lokatsiya → hudud → INN → nom → telefon → saqlash; `Do'konlar` varag'iga SPEC 7-bo'limdagi ustunlar tartibida to'g'ri qator tushadi (test qatorni tekshiradi, jumladan `Xarita` va `Rasm N` formulalari, `INN` matn sifatida).
- [ ] Foydalanuvchi matni formula bo'lib yozilmaydi (`=1+1` nomi bilan test).
- [ ] Hech bir holatda agent "qotib" qolmaydi: har qadamdan chiqish yo'li bor.
- [ ] Oxirida: nima qilindi, nima haqiqiy akkaunt/bot bilan tekshirilmadi haqida qisqa hisobot.

Mini App, kunlik hisobot, zaxira va deployni bu bosqichda YOZMA.
