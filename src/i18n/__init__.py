"""Internationalization (i18n) module for AccreditAI.

Provides translation loading and lookup with fallback to en-US.
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, List

# Default and supported locales
DEFAULT_LOCALE = "en-US"
SUPPORTED_LOCALES = ["en-US", "es-PR"]

# Locale display names (in their own language)
LOCALE_NAMES = {
    "en-US": "English (US)",
    "es-PR": "Español (Puerto Rico)",
}

# Cache for loaded translations
_translations: Dict[str, Dict[str, Any]] = {}

# Path to i18n JSON files
I18N_DIR = Path(__file__).parent


def load_locale(locale: str) -> Dict[str, Any]:
    """Load translation strings for a locale.

    Args:
        locale: BCP 47 locale tag (e.g., 'en-US', 'es-PR')

    Returns:
        Dictionary of translation strings
    """
    if locale in _translations:
        return _translations[locale]

    json_path = I18N_DIR / f"{locale}.json"
    if not json_path.exists():
        # Fall back to default locale
        if locale != DEFAULT_LOCALE:
            return load_locale(DEFAULT_LOCALE)
        return {}

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            _translations[locale] = json.load(f)
    except (json.JSONDecodeError, IOError):
        _translations[locale] = {}

    return _translations[locale]


def get_nested(data: Dict[str, Any], key: str) -> Optional[str]:
    """Get a nested value from a dictionary using dot notation.

    Args:
        data: Dictionary to search
        key: Dot-separated key (e.g., 'nav.dashboard')

    Returns:
        Value if found, None otherwise
    """
    parts = key.split('.')
    current = data

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current if isinstance(current, str) else None


def t(key: str, locale: str = None, params: Dict[str, Any] = None) -> str:
    """Translate a key to the specified locale.

    Args:
        key: Dot-separated translation key (e.g., 'nav.dashboard')
        locale: Target locale (defaults to DEFAULT_LOCALE)
        params: Parameters for string interpolation (e.g., {language: 'Spanish'})

    Returns:
        Translated string, or the key if not found
    """
    if locale is None:
        locale = DEFAULT_LOCALE

    # Load translations for the locale
    translations = load_locale(locale)

    # Try to get the translation
    value = get_nested(translations, key)

    # Fall back to default locale if not found
    if value is None and locale != DEFAULT_LOCALE:
        default_translations = load_locale(DEFAULT_LOCALE)
        value = get_nested(default_translations, key)

    # If still not found, return the key
    if value is None:
        return key

    # Apply parameter interpolation
    if params:
        for param_key, param_value in params.items():
            value = value.replace(f"{{{param_key}}}", str(param_value))

    return value


def get_all_strings(locale: str = None) -> Dict[str, Any]:
    """Get all translation strings for a locale.

    Useful for sending to frontend JavaScript.

    Args:
        locale: Target locale

    Returns:
        Dictionary of all translation strings
    """
    if locale is None:
        locale = DEFAULT_LOCALE

    return load_locale(locale)


def get_supported_locales() -> List[Dict[str, str]]:
    """Get list of supported locales with display names.

    Returns:
        List of {code, name} dictionaries
    """
    return [
        {"code": code, "name": LOCALE_NAMES.get(code, code)}
        for code in SUPPORTED_LOCALES
    ]


def clear_cache() -> None:
    """Clear the translation cache.

    Useful for development when translation files are updated.
    """
    _translations.clear()


# Preload default locale
load_locale(DEFAULT_LOCALE)
