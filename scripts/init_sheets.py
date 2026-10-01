"""
scripts/init_sheets.py
Idempotent script to format and initialize the Google Spreadsheet
according to SPEC section 7.
"""

import logging
import sys

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import get_settings
from app.services.sheets import (
    AGENTS_HEADERS,
    LOG_HEADERS,
    SCOPES,
    SETTINGS_HEADERS,
    SHEET_AGENTS,
    SHEET_LOG,
    SHEET_SETTINGS,
    SHEET_STATS,
    SHEET_STORES,
    SHEET_VISITS,
    STORES_HEADERS,
    VISITS_HEADERS,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def init_spreadsheet(spreadsheet_id: str, credentials: Credentials) -> None:
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    sheet_metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing_sheets = {s["properties"]["title"]: s["properties"]["sheetId"] for s in sheet_metadata.get("sheets", [])}

    requests = []

    # 1. Ensure all required sheets exist
    required_sheets = [
        SHEET_STORES,
        SHEET_VISITS,
        SHEET_AGENTS,
        SHEET_LOG,
        SHEET_SETTINGS,
        SHEET_STATS,
    ]

    for title in required_sheets:
        if title not in existing_sheets:
            logger.info(f"Adding sheet: {title}")
            res = service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
            ).execute()
            new_sheet_id = res["replies"][0]["addSheet"]["properties"]["sheetId"]
            existing_sheets[title] = new_sheet_id

    # 2. Set headers for sheets if empty
    headers_map = {
        SHEET_STORES: STORES_HEADERS,
        SHEET_VISITS: VISITS_HEADERS,
        SHEET_AGENTS: AGENTS_HEADERS,
        SHEET_LOG: LOG_HEADERS,
        SHEET_SETTINGS: SETTINGS_HEADERS,
    }

    for title, headers in headers_map.items():
        check_range = f"'{title}'!A1:Z1"
        res = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=check_range).execute()
        vals = res.get("values", [])
        if not vals or not vals[0]:
            logger.info(f"Writing headers for sheet: {title}")
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{title}'!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [headers]},
            ).execute()

    # 3. Default Settings in Sozlamalar if empty
    settings_range = f"'{SHEET_SETTINGS}'!A2:B10"
    res = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=settings_range).execute()
    if not res.get("values", []):
        logger.info("Initializing default settings...")
        default_settings = [
            ["admin_group_id", ""],
            ["daily_plan_default", "20"],
            ["report_time", "21:00"],
            ["notify_new_store", "1"],
            ["last_report_date", ""],
        ]
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{SHEET_SETTINGS}'!A2",
            valueInputOption="USER_ENTERED",
            body={"values": default_settings},
        ).execute()

    # 4. Formulations for Statistika sheet
    stats_check = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"'{SHEET_STATS}'!A1:B1").execute()
    if not stats_check.get("values", []):
        logger.info("Setting up formulas in Statistika sheet...")
        stats_data = [
            ["📊 AVTOMATIK STATISTIKA", ""],
            ["", ""],
            ["Top Viloyatlar", "Do'konlar Soni"],
            ["=IFERROR(QUERY('Do''konlar'!I2:I, \"SELECT I, count(I) WHERE I is not null and I != '' GROUP BY I ORDER BY count(I) desc LABEL I 'Viloyat', count(I) 'Soni'\"), \"Ma'lumot yo'q\")", ""],
            ["", ""],
            ["Top Agentlar", "Kiritgan Do'konlari"],
            ["=IFERROR(QUERY('Do''konlar'!E2:E, \"SELECT E, count(E) WHERE E is not null and E != '' GROUP BY E ORDER BY count(E) desc LABEL E 'Agent', count(E) 'Soni'\"), \"Ma'lumot yo'q\")", ""],
            ["", ""],
            ["Kunlik Dinamika", "Soni"],
            ["=IFERROR(QUERY('Do''konlar'!B2:B, \"SELECT B, count(B) WHERE B is not null and B != '' GROUP BY B ORDER BY B desc LIMIT 30 LABEL B 'Sana', count(B) 'Soni'\"), \"Ma'lumot yo'q\")", ""],
        ]
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{SHEET_STATS}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": stats_data},
        ).execute()

    # 5. Styling requests (Design system according to SPEC 7)
    # Header style: Dark navy blue background (#1A365D), white bold text, font Roboto
    navy_color = {"red": 0.102, "green": 0.212, "blue": 0.365}
    white_color = {"red": 1.0, "green": 1.0, "blue": 1.0}

    for title, headers in headers_map.items():
        sid = existing_sheets[title]
        num_cols = len(headers)

        # Freeze row 1 and columns 1-2 for Stores
        frozen_cols = 2 if title == SHEET_STORES else 1
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sid,
                    "gridProperties": {
                        "frozenRowCount": 1,
                        "frozenColumnCount": frozen_cols,
                    },
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        })

        # Header formatting
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sid,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": num_cols,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": navy_color,
                        "horizontalAlignment": "CENTER",
                        "textFormat": {
                            "foregroundColor": white_color,
                            "bold": True,
                            "fontSize": 10,
                            "fontFamily": "Roboto",
                        },
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        })

        # Auto-resize or set clean column dimensions
        requests.append({
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sid,
                    "dimension": "COLUMNS",
                    "startIndex": 0,
                    "endIndex": num_cols,
                }
            }
        })

    # Hide FileID columns in Do'konlar (Columns U, V, W -> indices 20, 21, 22)
    stores_sid = existing_sheets[SHEET_STORES]
    requests.append({
        "updateDimensionProperties": {
            "range": {
                "sheetId": stores_sid,
                "dimension": "COLUMNS",
                "startIndex": 20,
                "endIndex": 23,
            },
            "properties": {"hiddenByUser": True},
            "fields": "hiddenByUser",
        }
    })

    # Hide FileID columns in Tashriflar (Columns L, M, N -> indices 11, 12, 13)
    visits_sid = existing_sheets[SHEET_VISITS]
    requests.append({
        "updateDimensionProperties": {
            "range": {
                "sheetId": visits_sid,
                "dimension": "COLUMNS",
                "startIndex": 11,
                "endIndex": 14,
            },
            "properties": {"hiddenByUser": True},
            "fields": "hiddenByUser",
        }
    })

    # Set Basic Filter for Do'konlar
    requests.append({
        "setBasicFilter": {
            "filter": {
                "range": {
                    "sheetId": stores_sid,
                    "startRowIndex": 0,
                    "endRowIndex": 10000,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(STORES_HEADERS),
                }
            }
        }
    })

    logger.info(f"Applying {len(requests)} design & structure updates to spreadsheet...")
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": requests},
    ).execute()

    logger.info("Google Spreadsheet muvaffaqiyatli sozlandi!")


def main():
    settings = get_settings()
    if not settings.SPREADSHEET_ID:
        logger.error("SPREADSHEET_ID sozlanmagan. Iltimos, .env faylini to'ldiring.")
        sys.exit(1)

    creds = Credentials(
        token=None,
        refresh_token=settings.GOOGLE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=SCOPES,
    )

    try:
        init_spreadsheet(settings.SPREADSHEET_ID, creds)
    except Exception as e:
        logger.error(f"Xatolik yuz berdi: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
