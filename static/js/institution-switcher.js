/**
 * Institution Quick-Switcher
 *
 * Enables rapid navigation between institutions with search,
 * recent history, and keyboard shortcut (Ctrl+K).
 */

(function() {
    'use strict';

    const switcher = document.getElementById('institution-switcher');
    if (!switcher) return;

    const trigger = switcher.querySelector('.switcher-trigger');
    const dropdown = switcher.querySelector('.switcher-dropdown');
    const searchInput = switcher.querySelector('.switcher-search');
    const sectionsContainer = switcher.querySelector('.switcher-sections');

    let institutions = [];
    let recentIds = [];
    let isOpen = false;

    // Initialize
    async function init() {
        await loadInstitutions();
        await loadRecentInstitutions();
        renderSections();
        bindEvents();
    }

    // Load all institutions
    async function loadInstitutions() {
        try {
            const resp = await fetch('/api/institutions');
            const data = await resp.json();
            institutions = data.institutions || [];
        } catch (e) {
            console.error('Failed to load institutions:', e);
            institutions = [];
        }
    }

    // Load recent institutions
    async function loadRecentInstitutions() {
        try {
            const resp = await fetch('/api/institutions/recent?limit=5');
            const data = await resp.json();
            recentIds = data.institution_ids || [];
        } catch (e) {
            console.error('Failed to load recent institutions:', e);
            recentIds = [];
        }
    }

    // Render dropdown sections
    function renderSections(filter = '') {
        const filterLower = filter.toLowerCase().trim();

        // Filter institutions
        const filtered = filterLower
            ? institutions.filter(i =>
                i.name.toLowerCase().includes(filterLower) ||
                (i.accrediting_body || '').toLowerCase().includes(filterLower)
            )
            : institutions;

        // Get recent (only if no filter)
        const recent = filterLower
            ? []
            : recentIds
                .map(id => institutions.find(i => i.id === id))
                .filter(Boolean)
                .slice(0, 5);

        // Build HTML
        let html = '';

        if (filtered.length === 0) {
            html = '<div class="switcher-empty">No institutions found</div>';
        } else {
            // Recent section
            if (recent.length > 0) {
                html += '<div class="switcher-section-title">Recent</div>';
                recent.forEach(inst => {
                    html += renderItem(inst);
                });
            }

            // All institutions section
            html += '<div class="switcher-section-title">All Institutions</div>';
            filtered.forEach(inst => {
                html += renderItem(inst);
            });
        }

        sectionsContainer.innerHTML = html;

        // Bind item clicks
        sectionsContainer.querySelectorAll('.switcher-item').forEach(item => {
            item.addEventListener('click', () => {
                const id = item.dataset.id;
                navigateToInstitution(id);
            });
        });
    }

    // Render single item
    function renderItem(inst) {
        const currentId = getCurrentInstitutionId();
        const isActive = inst.id === currentId;
        const score = inst.readiness_score || 0;
        const scoreClass = score < 60 ? 'at-risk' : (score >= 80 ? 'ready' : '');

        return `
            <div class="switcher-item${isActive ? ' active' : ''}" data-id="${inst.id}">
                <span class="switcher-item-name">${escapeHtml(inst.name)}</span>
                ${score > 0 ? `<span class="switcher-item-score ${scoreClass}">${score}</span>` : ''}
            </div>
        `;
    }

    // Get current institution ID from URL
    function getCurrentInstitutionId() {
        const match = window.location.pathname.match(/\/institutions\/([^\/]+)/);
        return match ? match[1] : null;
    }

    // Navigate to institution
    async function navigateToInstitution(id) {
        // Record access
        try {
            await fetch(`/api/institutions/${id}/access`, { method: 'POST' });
        } catch (e) {
            // Ignore errors
        }

        // Navigate to institution overview
        window.location.href = `/institutions/${id}`;
    }

    // Toggle dropdown
    function toggle(open) {
        isOpen = open !== undefined ? open : !isOpen;
        trigger.setAttribute('aria-expanded', isOpen);

        if (isOpen) {
            dropdown.classList.add('open');
            searchInput.value = '';
            searchInput.focus();
            renderSections();
        } else {
            dropdown.classList.remove('open');
        }
    }

    // Bind events
    function bindEvents() {
        // Trigger click
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            toggle();
        });

        // Search input
        searchInput.addEventListener('input', (e) => {
            renderSections(e.target.value);
        });

        // Keyboard navigation
        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                toggle(false);
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                const first = sectionsContainer.querySelector('.switcher-item');
                if (first) first.focus();
            }
        });

        // Close on outside click
        document.addEventListener('click', (e) => {
            if (isOpen && !switcher.contains(e.target)) {
                toggle(false);
            }
        });

        // Global keyboard shortcut (Ctrl+K)
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                toggle(true);
            }
        });

        // Keyboard navigation within items
        sectionsContainer.addEventListener('keydown', (e) => {
            const items = [...sectionsContainer.querySelectorAll('.switcher-item')];
            const idx = items.indexOf(document.activeElement);

            if (e.key === 'ArrowDown' && idx < items.length - 1) {
                e.preventDefault();
                items[idx + 1].focus();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                if (idx > 0) {
                    items[idx - 1].focus();
                } else {
                    searchInput.focus();
                }
            } else if (e.key === 'Enter' && idx >= 0) {
                e.preventDefault();
                items[idx].click();
            } else if (e.key === 'Escape') {
                toggle(false);
            }
        });

        // Make items focusable
        sectionsContainer.addEventListener('focusin', (e) => {
            if (e.target.classList.contains('switcher-item')) {
                e.target.setAttribute('tabindex', '0');
            }
        });
    }

    // Escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
