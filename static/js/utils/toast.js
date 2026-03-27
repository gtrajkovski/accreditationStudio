/**
 * AccreditAI - Toast Notifications
 *
 * Toast notification system with stacking limit and dismiss-all (A11Y-04).
 */

const Toast = {
  container: null,
  dismissAllBtn: null,
  MAX_TOASTS: 5,  // Maximum visible toasts
  toasts: [],     // Track active toasts

  /**
   * Initialize toast container with ARIA live region.
   */
  init() {
    if (!this.container) {
      this.container = document.getElementById('toast-container');
      if (!this.container) {
        this.container = document.createElement('div');
        this.container.id = 'toast-container';
        this.container.className = 'toast-container';
        document.body.appendChild(this.container);
      }

      // Make toast container an ARIA live region (A11Y-02)
      this.container.setAttribute('role', 'status');
      this.container.setAttribute('aria-live', 'polite');
      this.container.setAttribute('aria-atomic', 'false');

      // Create dismiss-all button
      this.dismissAllBtn = document.createElement('button');
      this.dismissAllBtn.className = 'toast-dismiss-all';
      this.dismissAllBtn.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
        Dismiss All
      `;
      this.dismissAllBtn.style.display = 'none';
      this.dismissAllBtn.addEventListener('click', () => this.dismissAll());
      this.container.appendChild(this.dismissAllBtn);
    }
  },

  /**
   * Show a toast notification.
   * @param {string} message - The message to display
   * @param {string} type - Toast type: 'success', 'error', 'warning', 'info'
   * @param {number} duration - Duration in ms (default: 3000)
   */
  show(message, type = 'info', duration = 3000) {
    this.init();

    // Enforce stacking limit — remove oldest toast if at max
    if (this.toasts.length >= this.MAX_TOASTS) {
      const oldest = this.toasts.shift();
      this.removeToast(oldest);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');

    // Icon based on type
    const icons = {
      success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 20px; height: 20px;"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/></svg>',
      error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 20px; height: 20px;"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>',
      warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 20px; height: 20px;"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><path d="M12 9v4M12 17h.01"/></svg>',
      info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 20px; height: 20px;"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',
    };

    toast.innerHTML = `
      ${icons[type] || icons.info}
      <span>${message}</span>
      <button class="toast-close" aria-label="Dismiss notification">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 14px; height: 14px;">
          <line x1="18" y1="6" x2="6" y2="18"/>
          <line x1="6" y1="6" x2="18" y2="18"/>
        </svg>
      </button>
    `;

    // Close button handler
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => this.removeToast(toast));

    this.container.insertBefore(toast, this.dismissAllBtn);
    this.toasts.push(toast);

    // Show dismiss-all button if multiple toasts
    if (this.toasts.length > 1) {
      this.dismissAllBtn.style.display = 'flex';
    }

    // Auto-remove after duration
    setTimeout(() => {
      this.removeToast(toast);
    }, duration);
  },

  /**
   * Remove a specific toast.
   */
  removeToast(toast) {
    if (!toast || !toast.parentElement) return;

    toast.style.animation = 'slideOut 0.3s ease forwards';
    setTimeout(() => {
      toast.remove();
      this.toasts = this.toasts.filter(t => t !== toast);

      // Hide dismiss-all button if 0-1 toasts remain
      if (this.toasts.length <= 1) {
        this.dismissAllBtn.style.display = 'none';
      }
    }, 300);
  },

  /**
   * Dismiss all active toasts.
   */
  dismissAll() {
    this.toasts.forEach(toast => this.removeToast(toast));
    this.dismissAllBtn.style.display = 'none';
  },

  /**
   * Shorthand methods.
   */
  success(message, duration) {
    this.show(message, 'success', duration);
  },

  error(message, duration) {
    this.show(message, 'error', duration);
  },

  warning(message, duration) {
    this.show(message, 'warning', duration);
  },

  info(message, duration) {
    this.show(message, 'info', duration);
  },
};

// Add slideOut animation
const style = document.createElement('style');
style.textContent = `
  @keyframes slideOut {
    to {
      transform: translateX(100%);
      opacity: 0;
    }
  }
`;
document.head.appendChild(style);

// Expose globally
window.toast = Toast;
