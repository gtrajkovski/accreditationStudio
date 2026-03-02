/**
 * AccreditAI - Toast Notifications
 *
 * Simple toast notification system.
 */

const Toast = {
  container: null,

  /**
   * Initialize toast container.
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

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

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
    `;

    this.container.appendChild(toast);

    // Auto-remove after duration
    setTimeout(() => {
      toast.style.animation = 'slideOut 0.3s ease forwards';
      setTimeout(() => {
        toast.remove();
      }, 300);
    }, duration);
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
