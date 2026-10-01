"""
scripts/get_google_token.py
Bir martalik Google OAuth2 Refresh Token olish skripti.

QADAMMA-QADAM YO'RIQNOMA (Google Cloud Console):
------------------------------------------------
1. https://console.cloud.google.com ga kiring va yangi loyiha (Project) yarating (masalan, "Dokon Scout").
2. "APIs & Services" -> "Library" bo'limiga o'ting va ikkita API'ni yoqing (Enable qiling):
   - Google Sheets API
   - Google Drive API
3. "APIs & Services" -> "OAuth consent screen" bo'limiga kiring:
   - User Type: "External" ni tanlang va "Create" tugmasini bosing.
   - App name: "Dokon Scout", User support email va Developer contact email kiriting.
   - Scopes: ".../auth/drive" va ".../auth/spreadsheets" scope'larini tanlang.
   - Test users: O'zingizning Google emailingizni test foydalanuvchi sifatida qo'shing.
   - MUHIM: "Publish App" tugmasini bosib ilovani Production holatiga o'tkazing!
     (Aks holda Testing rejimida refresh token 7 kundan keyin eskirib, ishlamay qoladi).
4. "APIs & Services" -> "Credentials" bo'limiga o'ting:
   - "Create Credentials" -> "OAuth client ID" ni tanlang.
   - Application type: "Desktop app" (Desktop ilovasi) ni tanlang.
   - Nomi: masalan "Dokon Client" va "Create" bosing.
   - Sizga Client ID va Client Secret beriladi.
5. .env fayliga GOOGLE_CLIENT_ID va GOOGLE_CLIENT_SECRET ni yozing.
6. Ushbu skriptni ishga tushiring:
   python scripts/get_google_token.py
7. Brauzeringizda ochilgan sahifada Google hisobingizga kiring va ruxsat bering.
8. Terminalda paydo bo'lgan GOOGLE_REFRESH_TOKEN qiymatini nusxalab, .env faylingizga qo'ying!
"""

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import get_settings
from app.services.sheets import SCOPES


def main():
    settings = get_settings()
    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET

    if not client_id or not client_secret:
        print("\n❌ Xatolik: GOOGLE_CLIENT_ID yoki GOOGLE_CLIENT_SECRET .env faylida topilmadi!")
        print("Iltimos, avval .env faylini to'ldiring.\n")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    print("\n🌐 Brauzer ochilmoqda, Google akkauntingizga ruxsat bering...\n")
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    print("=" * 60)
    print("✅ MUVAFFAQITYATLI! Sizning GOOGLE_REFRESH_TOKEN:")
    print("=" * 60)
    print(creds.refresh_token)
    print("=" * 60)
    print("\nUshbu tokenni nusxalab, .env faylidagi GOOGLE_REFRESH_TOKEN o'zgaruvchisiga qo'ying.\n")


if __name__ == "__main__":
    main()
