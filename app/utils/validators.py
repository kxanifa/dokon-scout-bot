import re


def validate_inn(inn_raw: str) -> tuple[bool, str]:
    """
    Validate 9-digit INN:
    - Removes whitespace and dashes
    - Must be exactly 9 digits
    """
    if not inn_raw:
        return False, ""
    cleaned = re.sub(r"[\s\-]", "", str(inn_raw).strip())
    if re.fullmatch(r"^\d{9}$", cleaned):
        return True, cleaned
    return False, ""


def normalize_phone(phone_raw: str | None) -> tuple[bool, str]:
    """
    Normalize Uzbek phone number to +998XXXXXXXXX:
    - Accepts 9 digits (e.g. 901234567) -> +998901234567
    - Accepts 12 digits without plus (998901234567) -> +998901234567
    - Accepts with spaces, dashes, parentheses: +998 (90) 123-45-67
    - Empty or None -> (True, "") since phone is optional
    - Non-numeric or wrong length -> (False, "")
    """
    if phone_raw is None:
        return True, ""
    s = str(phone_raw).strip()
    if not s:
        return True, ""

    # Remove all formatting characters except digits and plus
    digits = re.sub(r"\D", "", s)

    if len(digits) == 9:
        return True, f"+998{digits}"
    elif len(digits) == 12 and digits.startswith("998"):
        return True, f"+{digits}"

    return False, ""


def validate_store_name(name_raw: str) -> tuple[bool, str]:
    """Validate store name length: 2 to 100 characters."""
    if not name_raw:
        return False, ""
    cleaned = " ".join(name_raw.strip().split())
    if 2 <= len(cleaned) <= 100:
        return True, cleaned
    return False, ""


def clean_text(text: str, max_length: int = 100) -> str:
    """Strip extra whitespaces and truncate."""
    if not text:
        return ""
    cleaned = " ".join(text.strip().split())
    return cleaned[:max_length]
