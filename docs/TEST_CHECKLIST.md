# Test va Tekshiruv Qo'llanmasi (Test Checklist)

Ushbu hujjat loyihaning barcha funksiyalarini haqiqiy muhitda bosqichma-bosqich qo'lda tekshirish uchun mo'ljallangan.

---

## 1. Ro'yxatdan o'tish va Ruxsat Tizimi

- [ ] **/start buyrug'i (Yangi foydalanuvchi):**
  - Bot 3 ta tilda (🇺🇿 O'zbekcha, 🇺🇿 Ўзбекча, 🇷🇺 Русский) inline tugma chiqaradi.
  - Til tanlangach, ism va familiya so'raladi (kamida 2 ta belgi).
  - "📱 Kontaktni ulashish" tugmasi chiqadi.
- [ ] **Kontakt tekshiruvi (Anti-firibgarlik):**
  - O'z kontaktini yuborsa: arizasi `Agentlar` varag'iga `pending` holatida yoziladi va adminga so'rov boradi.
  - Boshqa birovning kontaktini ulashsa: rad etiladi ("Faqat o'zingizning kontaktingizni yuboring").
- [ ] **Admin qabul/rad qilish:**
  - Admin chatiga inline tugmali xabar keladi: `✅ Qabul qilish` / `❌ Rad etish`.
  - Birinchi bosgan admin tasdiqlaydi. Xabar `Qaror: Qabul qilindi (Admin Ismi)` ko'rinishida tahrirlanadi.
  - Ikkinchi admin bossa: "Bu so'rov allaqachon ko'rib chiqilgan!" ogohlantirishi chiqadi.
  - Tasdiqlanganda agentga uning tilida xush kelibsiz xabari va Asosiy Menyu keladi.
- [ ] **Bloklangan/Kutilayotgan foydalanuvchi:**
  - `pending` foydalanuvchi yozsa: "So'rovingiz ko'rib chiqilmoqda".
  - `blocked` foydalanuvchi yozsa: "Sizning hisobingiz bloklangan".

---

## 2. Do'kon Kiritish Oqimi (8 Bosqich)

- [ ] **1-qadam (Rasm):**
  - 1 ta rasm yuboriladi. "Yana rasm qo'shish (2 tagacha)" yoki "Davom etish" tugmasi chiqadi.
  - 3 ta rasm yuborilganda avtomatik keyingi bosqichga o'tadi.
  - Rasm bo'lmagan matn/fayl yuborilsa rad etiladi.
- [ ] **2-qadam (Lokatsiya):**
  - Faqat "📍 Lokatsiya yuborish" tugmasi orqali qabul qilinadi.
  - Forward qilingan yoki xarita qidiruvi nuqtasi rad etiladi.
- [ ] **3-qadam (Hudud):**
  - Nominatim avtomatik viloyat, tuman va mahallani aniqlaydi.
  - Mahalla bo'sh bo'lsa, agent qo'lda kiritadi.
  - `✅ To'g'ri`, `✏️ Mahallani yozish`, `✏️ Hammasini tuzatish` tugmalari to'g'ri ishlaydi.
- [ ] **4-qadam (INN):**
  - Faqat 9 xonali raqam qabul qilinadi.
  - Agar INN bazada bo'lsa: "Bu INN avval kiritilgan" ogohlantirishi chiqadi.
  - `🔁 Yangi tashrif sifatida qo'shish` tanlansa, nom/telefon so'ralmasdan tashrif sifatida saqlanadi.
  - `➕ Baribir yangi do'kon sifatida saqlash` tanlansa, keyingi bosqichga o'tadi.
- [ ] **5-qadam (Do'kon nomi):**
  - 2 dan 100 gacha belgi tekshiriladi.
- [ ] **6-qadam (Telefon):**
  - Ixtiyoriy: "⏭ O'tkazib yuborish" tugmasi ishlaydi.
  - Kiritilsa `+998XXXXXXXXX` formatiga o'tkaziladi.
- [ ] **7-qadam (Xulosa):**
  - Barcha maydonlar va rasm soni ko'rsatiladi.
- [ ] **8-qadam (Saqlash):**
  - "Saqlanmoqda..." xabari chiqadi, rasm siqiladi, Drive'ga yuklanadi, Sheets'ga yoziladi.
  - Agentga "Saqlandi ✅ №<ID>" va bugungi natija (masalan: 7/20) boradi.
  - Agar kunlik reja to'lgan bo'lsa, tabrik xabari keladi.
  - Admin guruhiga foto + caption bilan bildirishnoma boradi.

---

## 3. Mening Yozuvlarim va Statistika

- [ ] **📋 Mening yozuvlarim:**
  - Faqat agentning o'zi kiritgan do'konlar (5 tadan, sahifalab).
  - Tahrirlash: nom, telefon, INN, hudud, rasm.
  - Boshqa agentning yozuvini tahrirlab bo'lmaydi (xavfsizlik serverda tekshiriladi).
- [ ] **📊 Statistikam va /top:**
  - Bugun / Shu hafta / Shu oy / Jami va kunlik reja progressi (`▓▓▓░░░`).
  - `/top`: eng faol 10 agent va agentning o'z o'rni ko'rinadi.

---

## 4. Admin Mini App (Boshqaruv Paneli)

- [ ] **Kirish:** faqat admin va superadmin kira oladi.
- [ ] **1. Bosh sahifa:** 4 KPI kartochka, 30 kunlik dinamika grafigi, Top hududlar grafigi.
- [ ] **2. Xarita:** OpenStreetMap + Leaflet marker cluster. Do'kon bosilganda bottom sheet ochiladi, rasm va Google Maps havolasi ko'rinadi.
- [ ] **3. Do'konlar:** Qidiruv (nom, INN, tel bo'yicha) va o'chirish (soft delete).
- [ ] **4. Agentlar:** Faollar / Kutilmoqda / Bloklangan tablar. Tasdiqlash, bloklash, kunlik reja o'zgartirish.
- [ ] **5. Hisobot va Excel:** "📥 Excel yuklab olish" tugmasi bosilganda `.xlsx` fayl bot tomonidan adminning shaxsiy chatiga yuboriladi.

---

## 5. Rejalashtirilgan Vazifalar va Zaxira

- [ ] **Kunlik hisobot:** Sozlamalardagi `report_time` (21:00) da barcha adminlarga yuboriladi. Bir kunda ikki marta takrorlanmaydi.
- [ ] **Qo'lda hisobot:** `/report_now` buyrug'i bilan superadmin hisobotni istalgan payt chaqira oladi.
- [ ] **Haftalik zaxira:** Yakshanba 03:00 da `Zaxira/` papkasiga spreadsheet nusxasi olinadi, oxirgi 8 tasi saqlanadi.
- [ ] **Qo'lda zaxira:** `/backup_now` buyrug'i orqali tekshirish.
