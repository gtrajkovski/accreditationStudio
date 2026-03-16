/**
 * Keyboard Shortcuts Modal
 *
 * Displays keyboard shortcuts help modal with:
 * - Focus trap (Tab cycles through focusable elements)
 * - ESC key to close
 * - Focus restoration to previous element
 * - WCAG 2.1 Level AA compliant
 */

class KeyboardShortcutsModal {
  constructor() {
    this.modal = null;
    this.modalContent = null;
    this.focusableElements = null;
    this.firstFocusableElement = null;
    this.lastFocusableElement = null;
    this.previousActiveElement = null;
    this.isOpen = false;

    // Selector for all focusable elements
    this.focusableSelector = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.init());
    } else {
      this.init();
    }
  }

  /**
   * Initialize the modal after DOM is ready
   */
  init() {
    this.modal = document.getElementById('keyboard-shortcuts-modal');

    if (!this.modal) {
      console.warn('Keyboard shortcuts modal element not found');
      return;
    }

    this.modalContent = this.modal.querySelector('.modal-content');

    // Bind event handlers
    this.handleKeydown = this.handleKeydown.bind(this);
    this.handleBackdropClick = this.handleBackdropClick.bind(this);

    // Add backdrop click handler
    const backdrop = this.modal.querySelector('.modal-backdrop');
    if (backdrop) {
      backdrop.addEventListener('click', this.handleBackdropClick);
    }
  }

  /**
   * Open the modal
   */
  open() {
    if (!this.modal || this.isOpen) return;

    // Store the currently focused element to restore later
    this.previousActiveElement = document.activeElement;

    // Show modal
    this.modal.style.display = 'flex';
    this.modal.setAttribute('aria-hidden', 'false');
    this.isOpen = true;

    // Query all focusable elements inside the modal content
    this.focusableElements = this.modalContent.querySelectorAll(this.focusableSelector);

    if (this.focusableElements.length > 0) {
      this.firstFocusableElement = this.focusableElements[0];
      this.lastFocusableElement = this.focusableElements[this.focusableElements.length - 1];

      // Focus the first focusable element
      this.firstFocusableElement.focus();
    }

    // Add keydown event listener for focus trap and ESC
    document.addEventListener('keydown', this.handleKeydown);
  }

  /**
   * Close the modal
   */
  close() {
    if (!this.modal || !this.isOpen) return;

    // Hide modal
    this.modal.style.display = 'none';
    this.modal.setAttribute('aria-hidden', 'true');
    this.isOpen = false;

    // Remove keydown event listener
    document.removeEventListener('keydown', this.handleKeydown);

    // Restore focus to the element that had focus before modal opened
    if (this.previousActiveElement && this.previousActiveElement.focus) {
      this.previousActiveElement.focus();
    }

    this.previousActiveElement = null;
  }

  /**
   * Handle keydown events for focus trap and ESC
   * @param {KeyboardEvent} e
   */
  handleKeydown(e) {
    // ESC key closes modal
    if (e.key === 'Escape') {
      e.preventDefault();
      this.close();
      return;
    }

    // Tab key - implement focus trap
    if (e.key === 'Tab') {
      // If no focusable elements, prevent default
      if (!this.focusableElements || this.focusableElements.length === 0) {
        e.preventDefault();
        return;
      }

      // Shift+Tab (backward)
      if (e.shiftKey) {
        if (document.activeElement === this.firstFocusableElement) {
          e.preventDefault();
          this.lastFocusableElement.focus();
        }
      }
      // Tab (forward)
      else {
        if (document.activeElement === this.lastFocusableElement) {
          e.preventDefault();
          this.firstFocusableElement.focus();
        }
      }
    }
  }

  /**
   * Handle backdrop click
   * @param {MouseEvent} e
   */
  handleBackdropClick(e) {
    // Only close if clicking directly on backdrop (not on modal content)
    if (e.target.classList.contains('modal-backdrop')) {
      this.close();
    }
  }
}

// Initialize and expose globally
window.KeyboardShortcuts = new KeyboardShortcutsModal();

// Global listener for ? key to open shortcuts modal
document.addEventListener('keydown', (e) => {
  // Only trigger if:
  // 1. Key is ?
  // 2. Not already typing in an input field
  // 3. Modal is not already open
  if (
    e.key === '?' &&
    !['INPUT', 'TEXTAREA'].includes(e.target.tagName) &&
    !window.KeyboardShortcuts.isOpen
  ) {
    e.preventDefault();
    window.KeyboardShortcuts.open();
  }
});
