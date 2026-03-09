/**
 * Quick Actions FAB (Floating Action Button)
 *
 * Provides fast access to common actions:
 * - Upload Document (U)
 * - Run Audit (A)
 * - Create Packet (P)
 */

window.QuickActionsFAB = (function() {
    'use strict';

    let isOpen = false;
    let fabButton = null;
    let fabMenu = null;
    let menuItems = [];

    /**
     * Initialize FAB
     */
    function init() {
        fabButton = document.getElementById('fab-button');
        fabMenu = document.getElementById('fab-menu');

        if (!fabButton || !fabMenu) {
            return; // FAB not present on this page
        }

        menuItems = Array.from(fabMenu.querySelectorAll('.fab-menu-item'));

        // Event listeners
        fabButton.addEventListener('click', toggle);
        fabButton.addEventListener('keydown', handleButtonKeydown);

        // Menu item clicks
        menuItems.forEach(item => {
            item.addEventListener('click', handleItemClick);
            item.addEventListener('keydown', handleItemKeydown);
        });

        // Close on outside click
        document.addEventListener('click', handleOutsideClick);

        // Close on Escape
        document.addEventListener('keydown', handleGlobalKeydown);
    }

    /**
     * Toggle FAB menu
     */
    function toggle() {
        if (isOpen) {
            close();
        } else {
            open();
        }
    }

    /**
     * Open FAB menu
     */
    function open() {
        if (isOpen) return;
        isOpen = true;

        fabButton.classList.add('open');
        fabButton.setAttribute('aria-expanded', 'true');
        fabMenu.classList.add('open');

        // Focus first menu item
        if (menuItems.length > 0) {
            setTimeout(() => menuItems[0].focus(), 100);
        }
    }

    /**
     * Close FAB menu
     */
    function close() {
        if (!isOpen) return;
        isOpen = false;

        fabButton.classList.remove('open');
        fabButton.setAttribute('aria-expanded', 'false');
        fabMenu.classList.remove('open');

        // Return focus to FAB button
        fabButton.focus();
    }

    /**
     * Handle FAB button keydown
     */
    function handleButtonKeydown(e) {
        switch (e.key) {
            case 'Enter':
            case ' ':
                e.preventDefault();
                toggle();
                break;
            case 'ArrowUp':
                e.preventDefault();
                open();
                if (menuItems.length > 0) {
                    menuItems[menuItems.length - 1].focus();
                }
                break;
            case 'ArrowDown':
                e.preventDefault();
                open();
                if (menuItems.length > 0) {
                    menuItems[0].focus();
                }
                break;
        }
    }

    /**
     * Handle menu item keydown
     */
    function handleItemKeydown(e) {
        const currentIndex = menuItems.indexOf(e.target);

        switch (e.key) {
            case 'ArrowUp':
                e.preventDefault();
                if (currentIndex > 0) {
                    menuItems[currentIndex - 1].focus();
                } else {
                    menuItems[menuItems.length - 1].focus();
                }
                break;
            case 'ArrowDown':
                e.preventDefault();
                if (currentIndex < menuItems.length - 1) {
                    menuItems[currentIndex + 1].focus();
                } else {
                    menuItems[0].focus();
                }
                break;
            case 'Escape':
                e.preventDefault();
                close();
                break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                handleItemClick(e);
                break;
        }
    }

    /**
     * Handle menu item click
     */
    function handleItemClick(e) {
        const item = e.currentTarget;
        const action = item.dataset.action;

        close();

        // Execute via CommandPalette
        if (action && window.CommandPalette) {
            // Small delay to allow menu close animation
            setTimeout(() => {
                window.CommandPalette.executeById
                    ? window.CommandPalette.executeById(action)
                    : console.warn('CommandPalette.executeById not available');
            }, 50);
        }
    }

    /**
     * Handle outside click
     */
    function handleOutsideClick(e) {
        if (!isOpen) return;

        const fabContainer = document.getElementById('fab-container');
        if (fabContainer && !fabContainer.contains(e.target)) {
            close();
        }
    }

    /**
     * Handle global keydown (Escape)
     */
    function handleGlobalKeydown(e) {
        if (e.key === 'Escape' && isOpen) {
            close();
        }
    }

    // Public API
    return {
        init,
        open,
        close,
        toggle
    };
})();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    QuickActionsFAB.init();
});
