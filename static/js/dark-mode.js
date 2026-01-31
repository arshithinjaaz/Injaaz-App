/**
 * Injaaz Dark Mode System
 * Handles theme switching with system preference detection
 * Version: 1.0.0
 */

(function(window) {
  'use strict';

  const STORAGE_KEY = 'injaaz-theme';
  const THEMES = {
    LIGHT: 'light',
    DARK: 'dark',
    SYSTEM: 'system'
  };

  let currentTheme = THEMES.SYSTEM;
  let systemPreference = null;

  /**
   * Get system color scheme preference
   */
  function getSystemPreference() {
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return THEMES.DARK;
    }
    return THEMES.LIGHT;
  }

  /**
   * Get stored theme preference
   */
  function getStoredTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  /**
   * Store theme preference
   */
  function storeTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {
      console.warn('Could not save theme preference');
    }
  }

  /**
   * Apply theme to document
   */
  function applyTheme(theme) {
    const effectiveTheme = theme === THEMES.SYSTEM ? getSystemPreference() : theme;
    
    // Update data attribute
    document.documentElement.setAttribute('data-theme', effectiveTheme);
    
    // Update class for backward compatibility
    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(effectiveTheme);
    
    // Update body class
    document.body.classList.remove('light', 'dark');
    document.body.classList.add(effectiveTheme);
    
    // Update meta theme-color for mobile browsers
    const metaThemeColor = document.querySelector('meta[name="theme-color"]');
    if (metaThemeColor) {
      metaThemeColor.content = effectiveTheme === THEMES.DARK ? '#18181b' : '#125435';
    }
    
    // Dispatch custom event
    window.dispatchEvent(new CustomEvent('themechange', {
      detail: { theme: effectiveTheme, preference: theme }
    }));
    
    currentTheme = theme;
    
    // Update toggle button if exists
    updateToggleButton(effectiveTheme);
  }

  /**
   * Update toggle button appearance
   */
  function updateToggleButton(theme) {
    const toggles = document.querySelectorAll('[data-theme-toggle]');
    toggles.forEach(toggle => {
      const lightIcon = toggle.querySelector('.theme-icon-light');
      const darkIcon = toggle.querySelector('.theme-icon-dark');
      
      if (lightIcon && darkIcon) {
        if (theme === THEMES.DARK) {
          lightIcon.style.display = 'none';
          darkIcon.style.display = 'block';
        } else {
          lightIcon.style.display = 'block';
          darkIcon.style.display = 'none';
        }
      }
      
      // Update aria-label
      toggle.setAttribute('aria-label', `Switch to ${theme === THEMES.DARK ? 'light' : 'dark'} mode`);
    });
  }

  /**
   * Toggle between light and dark themes
   */
  function toggle() {
    const effectiveTheme = currentTheme === THEMES.SYSTEM ? getSystemPreference() : currentTheme;
    const newTheme = effectiveTheme === THEMES.DARK ? THEMES.LIGHT : THEMES.DARK;
    setTheme(newTheme);
  }

  /**
   * Set specific theme
   */
  function setTheme(theme) {
    if (!Object.values(THEMES).includes(theme)) {
      console.warn(`Invalid theme: ${theme}`);
      return;
    }
    
    storeTheme(theme);
    applyTheme(theme);
  }

  /**
   * Get current theme
   */
  function getTheme() {
    return currentTheme;
  }

  /**
   * Get effective theme (resolved system preference)
   */
  function getEffectiveTheme() {
    return currentTheme === THEMES.SYSTEM ? getSystemPreference() : currentTheme;
  }

  /**
   * Initialize dark mode system
   */
  function init() {
    // Get stored preference or use system default
    const stored = getStoredTheme();
    currentTheme = stored || THEMES.SYSTEM;
    
    // Apply initial theme
    applyTheme(currentTheme);
    
    // Listen for system preference changes
    if (window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      
      // Modern browsers
      if (mediaQuery.addEventListener) {
        mediaQuery.addEventListener('change', (e) => {
          systemPreference = e.matches ? THEMES.DARK : THEMES.LIGHT;
          if (currentTheme === THEMES.SYSTEM) {
            applyTheme(THEMES.SYSTEM);
          }
        });
      }
    }
    
    // Auto-bind toggle buttons
    document.addEventListener('click', (e) => {
      const toggle = e.target.closest('[data-theme-toggle]');
      if (toggle) {
        e.preventDefault();
        DarkMode.toggle();
      }
    });
  }

  /**
   * Create toggle button HTML
   */
  function createToggleButton(options = {}) {
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('data-theme-toggle', '');
    button.setAttribute('aria-label', 'Toggle dark mode');
    button.className = options.className || 'theme-toggle btn btn-ghost btn-icon';
    
    button.innerHTML = `
      <span class="theme-icon-light">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="5"/>
          <line x1="12" y1="1" x2="12" y2="3"/>
          <line x1="12" y1="21" x2="12" y2="23"/>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
          <line x1="1" y1="12" x2="3" y2="12"/>
          <line x1="21" y1="12" x2="23" y2="12"/>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
        </svg>
      </span>
      <span class="theme-icon-dark" style="display: none;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      </span>
    `;
    
    return button;
  }

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Export to window
  window.DarkMode = {
    init,
    toggle,
    setTheme,
    getTheme,
    getEffectiveTheme,
    createToggleButton,
    THEMES
  };

})(window);
