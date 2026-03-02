/**
 * Theme management for AccreditAI
 *
 * Supports: light, dark, system (follows OS preference)
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'accreditai_theme';
  const VALID_THEMES = ['light', 'dark', 'system'];

  /**
   * Get the current theme preference
   */
  function getThemePreference() {
    // Check localStorage first
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && VALID_THEMES.includes(stored)) {
      return stored;
    }

    // Check data attribute (set by server)
    const htmlTheme = document.documentElement.getAttribute('data-theme-preference');
    if (htmlTheme && VALID_THEMES.includes(htmlTheme)) {
      return htmlTheme;
    }

    return 'system';
  }

  /**
   * Get the effective theme (resolved 'system' to actual theme)
   */
  function getEffectiveTheme(preference) {
    if (preference === 'system') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return preference;
  }

  /**
   * Apply theme to document
   */
  function applyTheme(preference) {
    const effective = getEffectiveTheme(preference);
    document.documentElement.setAttribute('data-theme', effective);
    document.documentElement.setAttribute('data-theme-preference', preference);

    // Update any theme toggle UI
    const toggles = document.querySelectorAll('[data-theme-toggle]');
    toggles.forEach(toggle => {
      toggle.setAttribute('data-current', preference);
    });

    // Dispatch custom event
    window.dispatchEvent(new CustomEvent('themechange', {
      detail: { preference, effective }
    }));
  }

  /**
   * Set and persist theme preference
   */
  function setTheme(preference) {
    if (!VALID_THEMES.includes(preference)) {
      console.warn('Invalid theme:', preference);
      return;
    }

    // Save to localStorage
    localStorage.setItem(STORAGE_KEY, preference);

    // Apply immediately
    applyTheme(preference);

    // Sync with server (non-blocking)
    fetch('/api/settings/me', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ theme_preference: preference })
    }).catch(err => console.warn('Failed to sync theme to server:', err));
  }

  /**
   * Cycle through themes: system -> light -> dark -> system
   */
  function cycleTheme() {
    const current = getThemePreference();
    const order = ['system', 'light', 'dark'];
    const currentIndex = order.indexOf(current);
    const nextIndex = (currentIndex + 1) % order.length;
    setTheme(order[nextIndex]);
  }

  /**
   * Initialize theme system
   */
  function init() {
    // Apply initial theme
    const preference = getThemePreference();
    applyTheme(preference);

    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
      if (getThemePreference() === 'system') {
        applyTheme('system');
      }
    });

    // Set up click handlers for theme controls
    document.addEventListener('click', e => {
      const toggle = e.target.closest('[data-theme-toggle]');
      if (toggle) {
        e.preventDefault();
        cycleTheme();
      }

      const setBtn = e.target.closest('[data-set-theme]');
      if (setBtn) {
        e.preventDefault();
        const theme = setBtn.getAttribute('data-set-theme');
        setTheme(theme);
      }
    });
  }

  // Export to window
  window.AccreditAI = window.AccreditAI || {};
  window.AccreditAI.theme = {
    get: getThemePreference,
    getEffective: () => getEffectiveTheme(getThemePreference()),
    set: setTheme,
    cycle: cycleTheme,
    init: init
  };

  // Auto-init when DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
