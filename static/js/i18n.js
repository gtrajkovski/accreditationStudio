/**
 * Internationalization (i18n) for AccreditAI frontend
 *
 * Provides translation lookup and locale management
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'accreditai_locale';
  const DEFAULT_LOCALE = 'en-US';
  const SUPPORTED_LOCALES = ['en-US', 'es-PR'];

  // Translation strings cache
  let _strings = {};
  let _currentLocale = DEFAULT_LOCALE;

  /**
   * Get nested value from object using dot notation
   */
  function getNestedValue(obj, path) {
    const parts = path.split('.');
    let current = obj;

    for (const part of parts) {
      if (current && typeof current === 'object' && part in current) {
        current = current[part];
      } else {
        return null;
      }
    }

    return typeof current === 'string' ? current : null;
  }

  /**
   * Translate a key with optional parameter interpolation
   */
  function t(key, params) {
    let value = getNestedValue(_strings, key);

    if (value === null) {
      // Return the key itself as fallback
      return key;
    }

    // Apply parameter interpolation
    if (params && typeof params === 'object') {
      Object.keys(params).forEach(paramKey => {
        value = value.replace(new RegExp(`\\{${paramKey}\\}`, 'g'), params[paramKey]);
      });
    }

    return value;
  }

  /**
   * Get current locale
   */
  function getLocale() {
    return _currentLocale;
  }

  /**
   * Load translations from server
   */
  async function loadTranslations(locale) {
    try {
      const response = await fetch(`/api/settings/translations?locale=${locale}`);
      if (response.ok) {
        const data = await response.json();
        _strings = data.strings || {};
        _currentLocale = data.locale || locale;
        return true;
      }
    } catch (err) {
      console.warn('Failed to load translations:', err);
    }
    return false;
  }

  /**
   * Set locale and reload translations
   */
  async function setLocale(locale) {
    if (!SUPPORTED_LOCALES.includes(locale)) {
      console.warn('Unsupported locale:', locale);
      return false;
    }

    // Save to localStorage
    localStorage.setItem(STORAGE_KEY, locale);

    // Sync with server
    try {
      await fetch('/api/settings/me', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ locale })
      });
    } catch (err) {
      console.warn('Failed to sync locale to server:', err);
    }

    // Reload page to apply new locale (server-side rendering)
    window.location.reload();
    return true;
  }

  /**
   * Initialize with translations from page
   */
  function init(strings, locale) {
    if (strings && typeof strings === 'object') {
      _strings = strings;
    }
    if (locale) {
      _currentLocale = locale;
    }

    // Store locale preference
    localStorage.setItem(STORAGE_KEY, _currentLocale);

    // Set up locale selector handlers
    document.addEventListener('click', e => {
      const localeBtn = e.target.closest('[data-set-locale]');
      if (localeBtn) {
        e.preventDefault();
        const locale = localeBtn.getAttribute('data-set-locale');
        setLocale(locale);
      }
    });

    // Set up change handlers for select elements
    document.addEventListener('change', e => {
      const localeSelect = e.target.closest('[data-locale-select]');
      if (localeSelect) {
        setLocale(localeSelect.value);
      }
    });
  }

  /**
   * Update all elements with data-i18n attribute
   */
  function updateDOM() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const params = el.getAttribute('data-i18n-params');
      const parsedParams = params ? JSON.parse(params) : null;
      el.textContent = t(key, parsedParams);
    });

    // Update placeholders
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      el.placeholder = t(key);
    });

    // Update titles
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      el.title = t(key);
    });
  }

  // Export to window
  window.AccreditAI = window.AccreditAI || {};
  window.AccreditAI.i18n = {
    t: t,
    getLocale: getLocale,
    setLocale: setLocale,
    loadTranslations: loadTranslations,
    init: init,
    updateDOM: updateDOM,
    SUPPORTED_LOCALES: SUPPORTED_LOCALES,
    DEFAULT_LOCALE: DEFAULT_LOCALE
  };
})();
