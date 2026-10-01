from app.i18n.ru import TEXTS as RU_TEXTS
from app.i18n.uz import TEXTS as UZ_TEXTS
from app.i18n.uz_cyr import TEXTS as UZ_CYR_TEXTS

LANGUAGES: dict[str, dict[str, str]] = {
    "uz": UZ_TEXTS,
    "uz_cyr": UZ_CYR_TEXTS,
    "ru": RU_TEXTS,
}

SUPPORTED_LANGUAGES = list(LANGUAGES.keys())


def t(key: str, lang: str = "uz", **kwargs) -> str:
    """Translate a key into target language with optional format kwargs."""
    if lang not in LANGUAGES:
        lang = "uz"

    dictionary = LANGUAGES.get(lang, UZ_TEXTS)
    template = dictionary.get(key)
    if template is None:
        template = UZ_TEXTS.get(key, f"[{key}]")

    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
