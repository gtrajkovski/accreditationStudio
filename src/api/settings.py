"""Settings API Blueprint.

Handles user preferences including locale and theme.
"""

from flask import Blueprint, request, jsonify, session, g
from src.db import get_conn
from src.i18n import SUPPORTED_LOCALES, DEFAULT_LOCALE, get_supported_locales, t

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')

# Default user ID for single-user mode
DEFAULT_USER_ID = "user_local"

# Supported themes
SUPPORTED_THEMES = ["light", "dark", "system"]
DEFAULT_THEME = "system"


def _ensure_user_exists(conn, user_id: str = DEFAULT_USER_ID) -> None:
    """Ensure the user row exists in the database."""
    cursor = conn.execute(
        "SELECT id FROM users WHERE id = ?",
        (user_id,)
    )
    if cursor.fetchone() is None:
        conn.execute(
            """INSERT INTO users (id, email, display_name, locale, theme_preference)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, "local@accreditai.local", "Local User", DEFAULT_LOCALE, DEFAULT_THEME)
        )
        conn.commit()


def _get_user_preferences(conn, user_id: str = DEFAULT_USER_ID) -> dict:
    """Get user preferences from database."""
    _ensure_user_exists(conn, user_id)

    cursor = conn.execute(
        "SELECT locale, theme_preference FROM users WHERE id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    if row:
        return {
            "locale": row[0],
            "theme_preference": row[1],
        }
    return {
        "locale": DEFAULT_LOCALE,
        "theme_preference": DEFAULT_THEME,
    }


def _update_user_preferences(conn, user_id: str, locale: str = None, theme: str = None) -> dict:
    """Update user preferences in database."""
    _ensure_user_exists(conn, user_id)

    updates = []
    params = []

    if locale is not None and locale in SUPPORTED_LOCALES:
        updates.append("locale = ?")
        params.append(locale)

    if theme is not None and theme in SUPPORTED_THEMES:
        updates.append("theme_preference = ?")
        params.append(theme)

    if updates:
        updates.append("updated_at = datetime('now')")
        params.append(user_id)

        sql = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
        conn.execute(sql, params)
        conn.commit()

    return _get_user_preferences(conn, user_id)


@settings_bp.route('/me', methods=['GET'])
def get_settings():
    """Get current user settings.

    Returns:
        {
            locale: "en-US" | "es-PR",
            theme_preference: "light" | "dark" | "system",
            supported_locales: [{code, name}, ...],
            supported_themes: ["light", "dark", "system"]
        }
    """
    conn = get_conn()
    try:
        prefs = _get_user_preferences(conn, DEFAULT_USER_ID)

        return jsonify({
            "locale": prefs["locale"],
            "theme_preference": prefs["theme_preference"],
            "supported_locales": get_supported_locales(),
            "supported_themes": SUPPORTED_THEMES,
        })
    finally:
        conn.close()


@settings_bp.route('/me', methods=['POST'])
def update_settings():
    """Update current user settings.

    Request body:
        {
            locale?: "en-US" | "es-PR",
            theme_preference?: "light" | "dark" | "system"
        }

    Returns:
        Updated settings object
    """
    data = request.get_json() or {}
    locale = data.get('locale')
    theme = data.get('theme_preference')

    # Validate locale
    if locale and locale not in SUPPORTED_LOCALES:
        return jsonify({
            "error": f"Unsupported locale: {locale}",
            "supported": SUPPORTED_LOCALES
        }), 400

    # Validate theme
    if theme and theme not in SUPPORTED_THEMES:
        return jsonify({
            "error": f"Unsupported theme: {theme}",
            "supported": SUPPORTED_THEMES
        }), 400

    conn = get_conn()
    try:
        prefs = _update_user_preferences(conn, DEFAULT_USER_ID, locale, theme)

        return jsonify({
            "locale": prefs["locale"],
            "theme_preference": prefs["theme_preference"],
            "supported_locales": get_supported_locales(),
            "supported_themes": SUPPORTED_THEMES,
            "message": t("settings.saved", prefs["locale"]),
        })
    finally:
        conn.close()


@settings_bp.route('/locales', methods=['GET'])
def get_locales():
    """Get list of supported locales.

    Returns:
        {locales: [{code, name}, ...]}
    """
    return jsonify({
        "locales": get_supported_locales(),
        "default": DEFAULT_LOCALE,
    })


@settings_bp.route('/themes', methods=['GET'])
def get_themes():
    """Get list of supported themes.

    Returns:
        {themes: ["light", "dark", "system"]}
    """
    return jsonify({
        "themes": SUPPORTED_THEMES,
        "default": DEFAULT_THEME,
    })


@settings_bp.route('/translations', methods=['GET'])
def get_translations():
    """Get all translation strings for the current locale.

    Query params:
        locale: Target locale (optional, uses user preference)

    Returns:
        {locale, strings: {...}}
    """
    from src.i18n import get_all_strings

    locale = request.args.get('locale')

    if not locale:
        conn = get_conn()
        try:
            prefs = _get_user_preferences(conn, DEFAULT_USER_ID)
            locale = prefs["locale"]
        finally:
            conn.close()

    if locale not in SUPPORTED_LOCALES:
        locale = DEFAULT_LOCALE

    return jsonify({
        "locale": locale,
        "strings": get_all_strings(locale),
    })


def init_settings_bp():
    """Initialize the settings blueprint.

    Called from app.py to set up any required state.
    """
    # Ensure database tables exist - migrations should handle this
    pass


def get_current_locale() -> str:
    """Get the current user's locale preference.

    Useful for templates and other code that needs the locale.
    """
    # Check session first
    if 'locale' in session:
        return session['locale']

    # Check database
    conn = get_conn()
    try:
        prefs = _get_user_preferences(conn, DEFAULT_USER_ID)
        return prefs["locale"]
    finally:
        conn.close()


def get_current_theme() -> str:
    """Get the current user's theme preference."""
    conn = get_conn()
    try:
        prefs = _get_user_preferences(conn, DEFAULT_USER_ID)
        return prefs["theme_preference"]
    finally:
        conn.close()
