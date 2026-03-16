/**
 * AccreditAI - Onboarding System
 * Phase 14-03: Contextual tooltips for first-time users
 *
 * Features:
 * - Per-institution state management via localStorage
 * - Auto-dismiss after timeout or interaction
 * - Position-aware tooltips with arrow indicators
 * - Tracks completed and dismissed tooltips separately
 */

class OnboardingManager {
    constructor(institutionId) {
        this.institutionId = institutionId;
        this.storageKey = `accreditai_onboarding_${institutionId}`;
        this.state = this.loadState();
        this.activeTooltips = new Map(); // Track active tooltip elements
    }

    /**
     * Load onboarding state from localStorage
     * @returns {Object} State object with completed, dismissed arrays and version
     */
    loadState() {
        try {
            const stored = localStorage.getItem(this.storageKey);
            return stored ? JSON.parse(stored) : {
                completed: [],
                dismissed: [],
                version: '1.0'
            };
        } catch (error) {
            console.error('Failed to load onboarding state:', error);
            return {
                completed: [],
                dismissed: [],
                version: '1.0'
            };
        }
    }

    /**
     * Save onboarding state to localStorage
     */
    saveState() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.state));
        } catch (error) {
            console.error('Failed to save onboarding state:', error);
        }
    }

    /**
     * Check if a tooltip should be shown
     * @param {string} tooltipId - Unique identifier for the tooltip
     * @returns {boolean} True if tooltip should be shown
     */
    shouldShow(tooltipId) {
        return !this.state.completed.includes(tooltipId) &&
               !this.state.dismissed.includes(tooltipId);
    }

    /**
     * Mark a tooltip as completed (user interacted with the feature)
     * @param {string} tooltipId - Unique identifier for the tooltip
     */
    markCompleted(tooltipId) {
        if (!this.state.completed.includes(tooltipId)) {
            this.state.completed.push(tooltipId);
            this.saveState();
        }
    }

    /**
     * Mark a tooltip as dismissed (user explicitly closed it)
     * @param {string} tooltipId - Unique identifier for the tooltip
     */
    dismiss(tooltipId) {
        if (!this.state.dismissed.includes(tooltipId)) {
            this.state.dismissed.push(tooltipId);
            this.saveState();
        }
    }

    /**
     * Reset all onboarding state (for testing or user preference)
     */
    reset() {
        localStorage.removeItem(this.storageKey);
        this.state = this.loadState();
        // Close all active tooltips
        this.activeTooltips.forEach((tooltip, id) => {
            tooltip.remove();
        });
        this.activeTooltips.clear();
    }

    /**
     * Attach a tooltip to a target element
     * @param {string} elementSelector - CSS selector for target element
     * @param {string} tooltipId - Unique identifier for the tooltip
     * @param {Object} options - Configuration options
     * @param {string} options.text - Tooltip text content
     * @param {string} options.icon - Optional icon emoji
     * @param {string} options.position - Position relative to target (top/bottom/left/right)
     * @param {number} options.timeout - Auto-dismiss timeout in milliseconds
     * @param {string} options.dismissLabel - Aria label for dismiss button
     */
    attachTooltip(elementSelector, tooltipId, options = {}) {
        // Don't show if already completed or dismissed
        if (!this.shouldShow(tooltipId)) {
            return;
        }

        // Wait for element to be available
        const element = document.querySelector(elementSelector);
        if (!element) {
            console.warn(`Onboarding: Element not found for selector: ${elementSelector}`);
            return;
        }

        // Create and position tooltip
        const tooltip = this.createTooltip(tooltipId, options);
        this.positionTooltip(tooltip, element, options.position || 'bottom');

        // Track active tooltip
        this.activeTooltips.set(tooltipId, tooltip);

        // Auto-dismiss on target element interaction
        const dismissOnAction = () => {
            this.markCompleted(tooltipId);
            this.removeTooltip(tooltipId);
        };

        // Listen for click on target element
        element.addEventListener('click', dismissOnAction, { once: true });

        // Auto-dismiss after timeout
        if (options.timeout) {
            setTimeout(() => {
                if (this.activeTooltips.has(tooltipId)) {
                    this.dismiss(tooltipId);
                    this.removeTooltip(tooltipId);
                }
            }, options.timeout);
        }

        // Update position on window resize
        const updatePosition = () => {
            if (this.activeTooltips.has(tooltipId)) {
                this.positionTooltip(tooltip, element, options.position || 'bottom');
            }
        };
        window.addEventListener('resize', updatePosition);

        // Clean up resize listener when tooltip is removed
        tooltip.dataset.resizeListener = 'attached';
        tooltip.addEventListener('remove', () => {
            window.removeEventListener('resize', updatePosition);
        }, { once: true });
    }

    /**
     * Create tooltip DOM element
     * @param {string} tooltipId - Unique identifier
     * @param {Object} options - Configuration options
     * @returns {HTMLElement} The tooltip element
     */
    createTooltip(tooltipId, options) {
        const tooltip = document.createElement('div');
        tooltip.className = 'onboarding-tooltip';
        tooltip.setAttribute('role', 'tooltip');
        tooltip.setAttribute('data-tooltip-id', tooltipId);
        tooltip.setAttribute('data-position', options.position || 'bottom');

        tooltip.innerHTML = `
            <div class="tooltip-content">
                ${options.icon ? `<span class="tooltip-icon">${options.icon}</span>` : ''}
                <div class="tooltip-text">${options.text}</div>
            </div>
            <button class="tooltip-dismiss" aria-label="${options.dismissLabel || 'Dismiss'}" type="button">×</button>
        `;

        // Dismiss button handler
        const dismissBtn = tooltip.querySelector('.tooltip-dismiss');
        dismissBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.dismiss(tooltipId);
            this.removeTooltip(tooltipId);
        });

        document.body.appendChild(tooltip);
        return tooltip;
    }

    /**
     * Position tooltip relative to target element
     * @param {HTMLElement} tooltip - The tooltip element
     * @param {HTMLElement} element - The target element
     * @param {string} position - Position (top/bottom/left/right)
     */
    positionTooltip(tooltip, element, position) {
        const rect = element.getBoundingClientRect();
        const tooltipRect = tooltip.getBoundingClientRect();
        const scrollX = window.pageXOffset || document.documentElement.scrollLeft;
        const scrollY = window.pageYOffset || document.documentElement.scrollTop;

        const gap = 10; // Gap between tooltip and target
        let top, left;

        switch (position) {
            case 'top':
                top = rect.top + scrollY - tooltipRect.height - gap;
                left = rect.left + scrollX + (rect.width / 2) - (tooltipRect.width / 2);
                break;

            case 'bottom':
                top = rect.bottom + scrollY + gap;
                left = rect.left + scrollX + (rect.width / 2) - (tooltipRect.width / 2);
                break;

            case 'left':
                top = rect.top + scrollY + (rect.height / 2) - (tooltipRect.height / 2);
                left = rect.left + scrollX - tooltipRect.width - gap;
                break;

            case 'right':
                top = rect.top + scrollY + (rect.height / 2) - (tooltipRect.height / 2);
                left = rect.right + scrollX + gap;
                break;

            default:
                // Default to bottom
                top = rect.bottom + scrollY + gap;
                left = rect.left + scrollX + (rect.width / 2) - (tooltipRect.width / 2);
        }

        // Keep tooltip within viewport bounds
        const maxLeft = window.innerWidth - tooltipRect.width - 20;
        const maxTop = window.innerHeight + scrollY - tooltipRect.height - 20;

        left = Math.max(20, Math.min(left, maxLeft));
        top = Math.max(scrollY + 20, Math.min(top, maxTop));

        tooltip.style.top = `${top}px`;
        tooltip.style.left = `${left}px`;
    }

    /**
     * Remove a tooltip from the DOM
     * @param {string} tooltipId - Unique identifier
     */
    removeTooltip(tooltipId) {
        const tooltip = this.activeTooltips.get(tooltipId);
        if (tooltip && tooltip.parentNode) {
            tooltip.remove();
        }
        this.activeTooltips.delete(tooltipId);
    }

    /**
     * Dismiss all active tooltips
     */
    dismissAll() {
        this.activeTooltips.forEach((tooltip, id) => {
            this.dismiss(id);
            tooltip.remove();
        });
        this.activeTooltips.clear();
    }
}

// Export to window for global access
window.OnboardingManager = OnboardingManager;
