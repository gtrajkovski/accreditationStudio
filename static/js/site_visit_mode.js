/**
 * Site Visit Mode - Fast unified search for auditor visits.
 *
 * Provides instant search across documents, standards, findings, faculty,
 * truth index, and knowledge graph with document + page citations.
 *
 * Keyboard shortcuts:
 * - F2 or Ctrl+Shift+S: Open Site Visit Mode
 * - Escape: Close
 * - Up/Down: Navigate results
 * - Enter: Open selected result
 * - Tab: Toggle preview pane
 */

window.SiteVisitMode = (function() {
    'use strict';

    // State
    let isOpen = false;
    let selectedIndex = 0;
    let results = [];
    let searchTimeout = null;
    let institutionId = null;
    let showPreview = false;

    const DEBOUNCE_MS = 150;
    const ALL_SOURCES = ['documents', 'standards', 'findings', 'faculty', 'truth_index', 'knowledge_graph'];

    /**
     * Initialize Site Visit Mode for an institution.
     */
    function init(instId) {
        institutionId = instId;

        const input = document.getElementById('site-visit-input');
        if (input) {
            input.addEventListener('input', handleInput);
            input.addEventListener('keydown', handleKeydown);
        }

        // Filter buttons
        const filters = document.getElementById('site-visit-filters');
        if (filters) {
            filters.addEventListener('click', handleFilterClick);
        }

        // Global shortcut: F2 or Ctrl+Shift+S
        document.addEventListener('keydown', handleGlobalKeydown);
    }

    /**
     * Handle global keyboard shortcuts.
     */
    function handleGlobalKeydown(e) {
        // Don't trigger if in another input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            if (e.target.id !== 'site-visit-input') {
                return;
            }
        }

        // F2 opens Site Visit Mode
        if (e.key === 'F2') {
            e.preventDefault();
            toggle();
            return;
        }

        // Ctrl+Shift+S also opens
        if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 's') {
            e.preventDefault();
            toggle();
            return;
        }
    }

    /**
     * Toggle the overlay.
     */
    function toggle() {
        if (isOpen) {
            close();
        } else {
            open();
        }
    }

    /**
     * Open the Site Visit Mode overlay.
     */
    function open() {
        if (!institutionId) {
            console.warn('SiteVisitMode: No institution ID set');
            return;
        }

        isOpen = true;
        const overlay = document.getElementById('site-visit-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
            const input = document.getElementById('site-visit-input');
            if (input) {
                input.value = '';
                input.focus();
            }
            renderEmptyState();
        }
    }

    /**
     * Close the Site Visit Mode overlay.
     */
    function close() {
        isOpen = false;
        const overlay = document.getElementById('site-visit-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
        results = [];
        selectedIndex = 0;
        showPreview = false;
        hidePreviewPane();
    }

    /**
     * Handle search input changes.
     */
    function handleInput(e) {
        const query = e.target.value.trim();

        if (searchTimeout) {
            clearTimeout(searchTimeout);
        }

        if (query.length < 2) {
            renderEmptyState();
            return;
        }

        // Debounce search
        searchTimeout = setTimeout(() => {
            search(query);
        }, DEBOUNCE_MS);
    }

    /**
     * Handle keyboard navigation.
     */
    function handleKeydown(e) {
        switch (e.key) {
            case 'Escape':
                e.preventDefault();
                close();
                break;

            case 'ArrowDown':
                e.preventDefault();
                if (results.length > 0) {
                    selectedIndex = Math.min(selectedIndex + 1, results.length - 1);
                    renderResults();
                    scrollToSelected();
                }
                break;

            case 'ArrowUp':
                e.preventDefault();
                if (results.length > 0) {
                    selectedIndex = Math.max(selectedIndex - 1, 0);
                    renderResults();
                    scrollToSelected();
                }
                break;

            case 'Enter':
                e.preventDefault();
                if (results.length > 0 && results[selectedIndex]) {
                    openResult(results[selectedIndex]);
                }
                break;

            case 'Tab':
                e.preventDefault();
                togglePreview();
                break;
        }
    }

    /**
     * Handle filter button clicks.
     */
    function handleFilterClick(e) {
        const btn = e.target.closest('.filter-btn');
        if (!btn) return;

        const source = btn.dataset.source;
        const allBtns = document.querySelectorAll('#site-visit-filters .filter-btn');

        if (source === 'all') {
            // Select only "All"
            allBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        } else {
            // Toggle this filter
            const allBtn = document.querySelector('#site-visit-filters .filter-btn[data-source="all"]');
            if (allBtn) allBtn.classList.remove('active');
            btn.classList.toggle('active');

            // If no filters selected, re-select "All"
            const activeFilters = document.querySelectorAll('#site-visit-filters .filter-btn.active');
            if (activeFilters.length === 0 && allBtn) {
                allBtn.classList.add('active');
            }
        }

        // Re-run search with new filters
        const input = document.getElementById('site-visit-input');
        if (input && input.value.trim().length >= 2) {
            search(input.value.trim());
        }
    }

    /**
     * Get active source filters.
     */
    function getActiveFilters() {
        const allBtn = document.querySelector('#site-visit-filters .filter-btn[data-source="all"]');
        if (allBtn && allBtn.classList.contains('active')) {
            return ALL_SOURCES;
        }

        const active = document.querySelectorAll('#site-visit-filters .filter-btn.active');
        return Array.from(active).map(btn => btn.dataset.source).filter(s => s !== 'all');
    }

    /**
     * Execute search.
     */
    async function search(query) {
        const container = document.getElementById('site-visit-results');
        if (!container) return;

        // Show loading state
        container.innerHTML = '<div class="site-visit-loading">Searching</div>';

        try {
            const filters = {
                sources: getActiveFilters()
            };

            const response = await fetch(`/api/institutions/${institutionId}/site-visit/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    filters: filters,
                    limit: 30
                })
            });

            if (!response.ok) {
                throw new Error('Search failed');
            }

            const data = await response.json();
            results = data.results || [];
            selectedIndex = 0;

            // Update stats
            const stats = document.getElementById('site-visit-stats');
            if (stats) {
                stats.textContent = `${data.total} results in ${data.query_time_ms}ms`;
            }

            renderResults();

        } catch (error) {
            console.error('Site Visit search error:', error);
            container.innerHTML = '<div class="site-visit-no-results"><p>Search failed. Please try again.</p></div>';
        }
    }

    /**
     * Render empty state.
     */
    function renderEmptyState() {
        const container = document.getElementById('site-visit-results');
        if (!container) return;

        container.innerHTML = `
            <div class="site-visit-empty">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="M21 21l-4.35-4.35"/>
                </svg>
                <p>Search documents, standards, findings, and more</p>
                <span class="site-visit-hint">Type at least 2 characters to search</span>
            </div>
        `;

        // Clear stats
        const stats = document.getElementById('site-visit-stats');
        if (stats) stats.textContent = '';
    }

    /**
     * Render search results.
     */
    function renderResults() {
        const container = document.getElementById('site-visit-results');
        if (!container) return;

        if (results.length === 0) {
            container.innerHTML = `
                <div class="site-visit-no-results">
                    <p>No results found</p>
                    <span class="site-visit-hint">Try different keywords or adjust filters</span>
                </div>
            `;
            return;
        }

        container.innerHTML = results.map((item, idx) => {
            const citation = item.citation || {};
            const scorePercent = Math.round(item.score * 100);

            return `
                <div class="site-visit-result ${idx === selectedIndex ? 'selected' : ''}"
                     data-index="${idx}" onclick="SiteVisitMode.select(${idx})">
                    <div class="site-visit-result-source ${item.source_type}">${formatSourceType(item.source_type)}</div>
                    <div class="site-visit-result-content">
                        <div class="site-visit-result-title">${escapeHtml(item.title)}</div>
                        <div class="site-visit-result-snippet">${escapeHtml(item.snippet)}</div>
                        <div class="site-visit-result-citation">
                            <span class="citation-doc">${escapeHtml(citation.document || '')}</span>
                            ${citation.page ? `<span class="citation-page">p. ${citation.page}</span>` : ''}
                            ${citation.standard_code ? `<span class="citation-code">${escapeHtml(citation.standard_code)}</span>` : ''}
                            ${citation.section ? `<span class="citation-section">${escapeHtml(citation.section)}</span>` : ''}
                        </div>
                    </div>
                    <div class="site-visit-result-score">${scorePercent}%</div>
                </div>
            `;
        }).join('');

        // Update preview if visible
        if (showPreview && results[selectedIndex]) {
            renderPreview(results[selectedIndex]);
        }
    }

    /**
     * Select a result by index.
     */
    function select(index) {
        selectedIndex = index;
        renderResults();
        if (showPreview && results[index]) {
            renderPreview(results[index]);
        }
    }

    /**
     * Toggle preview pane.
     */
    function togglePreview() {
        showPreview = !showPreview;
        const preview = document.getElementById('site-visit-preview');
        if (!preview) return;

        if (showPreview && results[selectedIndex]) {
            preview.style.display = 'block';
            renderPreview(results[selectedIndex]);
        } else {
            hidePreviewPane();
        }
    }

    /**
     * Hide preview pane.
     */
    function hidePreviewPane() {
        const preview = document.getElementById('site-visit-preview');
        if (preview) {
            preview.style.display = 'none';
        }
    }

    /**
     * Render preview for a result.
     */
    function renderPreview(item) {
        const preview = document.getElementById('site-visit-preview');
        if (!preview) return;

        const citation = item.citation || {};

        preview.innerHTML = `
            <div class="site-visit-preview-title">${escapeHtml(item.title)}</div>
            <div class="site-visit-preview-citation">
                <span>${escapeHtml(citation.document || item.source_type)}</span>
                ${citation.page ? `<span>Page ${citation.page}</span>` : ''}
                ${citation.section ? `<span>${escapeHtml(citation.section)}</span>` : ''}
            </div>
            <div class="site-visit-preview-content">${escapeHtml(item.snippet)}</div>
            <div class="site-visit-preview-actions">
                <button class="btn btn-primary btn-sm" onclick="SiteVisitMode.openResult(SiteVisitMode.getSelected())">
                    Open Document
                </button>
            </div>
        `;
    }

    /**
     * Get currently selected result.
     */
    function getSelected() {
        return results[selectedIndex];
    }

    /**
     * Open a result (navigate to document).
     */
    function openResult(item) {
        if (!item) return;

        close();

        // Navigate based on source type
        switch (item.source_type) {
            case 'document':
                window.location.href = `/institutions/${institutionId}/documents?highlight=${item.source_id}`;
                break;
            case 'standard':
                window.location.href = `/standards?highlight=${item.source_id}`;
                break;
            case 'finding':
                window.location.href = `/institutions/${institutionId}/compliance?finding=${item.source_id}`;
                break;
            case 'faculty':
                window.location.href = `/institutions/${institutionId}/faculty?highlight=${item.source_id}`;
                break;
            case 'knowledge_graph':
                window.location.href = `/institutions/${institutionId}/knowledge-graph?entity=${item.source_id}`;
                break;
            default:
                console.log('Result:', item);
        }
    }

    /**
     * Scroll to keep selected item visible.
     */
    function scrollToSelected() {
        const container = document.getElementById('site-visit-results');
        const selected = container?.querySelector('.site-visit-result.selected');
        if (selected) {
            selected.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    }

    /**
     * Format source type for display.
     */
    function formatSourceType(type) {
        const labels = {
            'document': 'Doc',
            'standard': 'Std',
            'finding': 'Find',
            'faculty': 'Fac',
            'truth_index': 'Fact',
            'knowledge_graph': 'KG'
        };
        return labels[type] || type;
    }

    /**
     * Escape HTML for safe rendering.
     */
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Public API
    return {
        init,
        open,
        close,
        toggle,
        select,
        openResult,
        getSelected
    };
})();
