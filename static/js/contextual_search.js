/**
 * InlineSearchBar - Contextual search bar for page header
 *
 * Features:
 * - Displays scope-aware placeholder text
 * - Debounced search with race condition prevention
 * - Results dropdown with keyboard navigation
 * - Uses ScopeBadge for scope indicator
 *
 * Phase 27: Frontend & Visual Testing (SRCHUI-02)
 */
window.InlineSearchBar = (function() {
    'use strict';

    const DEBOUNCE_MS = 250;
    const MIN_QUERY_LENGTH = 2;
    const MAX_RESULTS = 10;

    class InlineSearchBar {
        constructor(containerEl, options = {}) {
            this.container = containerEl;
            this.options = {
                debounceMs: DEBOUNCE_MS,
                minQueryLength: MIN_QUERY_LENGTH,
                maxResults: MAX_RESULTS,
                ...options
            };

            // State
            this.searchInput = null;
            this.resultsPanel = null;
            this.scopeBadge = null;
            this.currentScope = 'global';
            this.searchTimeout = null;
            this.currentSearchId = 0;
            this.results = [];
            this.selectedIndex = -1;
            this.isOpen = false;

            this._init();
        }

        _init() {
            this._render();
            this._attachEventListeners();
            this._detectScope();
        }

        _detectScope() {
            const wrapper = document.querySelector('.main-wrapper');
            if (!wrapper) {
                this.currentScope = 'global';
                return;
            }

            const page = wrapper.dataset.page || '';
            const instId = wrapper.dataset.institutionId;
            const progId = wrapper.dataset.programId;
            const docId = wrapper.dataset.documentId;

            if (docId) this.currentScope = 'document';
            else if (progId) this.currentScope = 'program';
            else if (page.includes('compliance')) this.currentScope = 'compliance';
            else if (page.includes('standards')) this.currentScope = 'standards';
            else if (instId) this.currentScope = 'institution';
            else this.currentScope = 'global';

            this._updatePlaceholder();
        }

        _t(key) {
            if (window.AccreditAI && window.AccreditAI.i18n) {
                return window.AccreditAI.i18n.t(key);
            }
            return key.split('.').pop().replace(/_/g, ' ');
        }

        _escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        _render() {
            const placeholder = this._t(`search.placeholder.${this.currentScope}`);

            this.container.innerHTML = `
                <div class="inline-search-bar" role="search">
                    <svg class="inline-search-bar__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="11" cy="11" r="8"/>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    </svg>
                    <input
                        type="search"
                        class="inline-search-bar__input"
                        id="inline-search-input"
                        placeholder="${this._escapeHtml(placeholder)}"
                        autocomplete="off"
                        spellcheck="false"
                        aria-label="${this._t('common.search')}"
                        aria-autocomplete="list"
                        aria-expanded="false"
                        aria-controls="inline-search-results"
                    />
                    <kbd class="inline-search-bar__shortcut">/</kbd>
                </div>
                <div class="inline-search-results" id="inline-search-results" hidden role="listbox">
                    <!-- Results rendered dynamically -->
                </div>
            `;

            this.searchInput = this.container.querySelector('.inline-search-bar__input');
            this.resultsPanel = this.container.querySelector('.inline-search-results');
        }

        _attachEventListeners() {
            // Input event - debounced search
            this.searchInput.addEventListener('input', (e) => {
                this._handleInput(e.target.value);
            });

            // Keydown for navigation and shortcuts
            this.searchInput.addEventListener('keydown', (e) => {
                this._handleKeydown(e);
            });

            // Focus/blur for results panel visibility
            this.searchInput.addEventListener('focus', () => {
                if (this.results.length > 0) {
                    this._showResults();
                }
            });

            // Close results when clicking outside
            document.addEventListener('click', (e) => {
                if (!this.container.contains(e.target)) {
                    this._hideResults();
                }
            });

            // Global / key to focus
            document.addEventListener('keydown', (e) => {
                if (e.key === '/' && !this._isTypingInInput(e.target)) {
                    // Only if command palette is not open
                    const palette = document.getElementById('command-palette');
                    if (palette && palette.style.display !== 'none') return;

                    e.preventDefault();
                    this.searchInput.focus();
                }
            });
        }

        _isTypingInInput(target) {
            const tag = target.tagName.toLowerCase();
            return tag === 'input' || tag === 'textarea' || target.isContentEditable;
        }

        _handleInput(query) {
            if (this.searchTimeout) {
                clearTimeout(this.searchTimeout);
            }

            if (query.length === 0) {
                this._hideResults();
                this.results = [];
                return;
            }

            if (query.length < this.options.minQueryLength) {
                this._renderMinLengthHint();
                this._showResults();
                return;
            }

            this.searchTimeout = setTimeout(() => {
                this._executeSearch(query);
            }, this.options.debounceMs);
        }

        _handleKeydown(e) {
            switch (e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    if (this.isOpen && this.results.length > 0) {
                        this.selectedIndex = Math.min(this.selectedIndex + 1, this.results.length - 1);
                        this._updateSelection();
                    }
                    break;

                case 'ArrowUp':
                    e.preventDefault();
                    if (this.isOpen && this.results.length > 0) {
                        this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
                        this._updateSelection();
                    }
                    break;

                case 'Enter':
                    e.preventDefault();
                    if (this.isOpen && this.selectedIndex >= 0 && this.results[this.selectedIndex]) {
                        this._openResult(this.results[this.selectedIndex]);
                    }
                    break;

                case 'Escape':
                    e.preventDefault();
                    this._hideResults();
                    this.searchInput.blur();
                    break;

                case 'Tab':
                    // Close results on Tab
                    this._hideResults();
                    break;
            }
        }

        async _executeSearch(query) {
            const searchId = ++this.currentSearchId;
            this._renderLoading();
            this._showResults();

            const wrapper = document.querySelector('.main-wrapper');
            const institutionId = wrapper?.dataset.institutionId || '';
            const programId = wrapper?.dataset.programId || null;
            const documentId = wrapper?.dataset.documentId || null;

            try {
                const response = await fetch('/api/search/contextual', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query,
                        scope: this.currentScope,
                        institution_id: institutionId || undefined,
                        program_id: programId || undefined,
                        document_id: documentId || undefined,
                        per_page: this.options.maxResults
                    })
                });

                if (searchId !== this.currentSearchId) return; // Stale

                if (!response.ok) {
                    throw new Error(`Search failed: ${response.status}`);
                }

                const data = await response.json();
                this.results = data.items || [];
                this.selectedIndex = this.results.length > 0 ? 0 : -1;
                this._renderResults(data);
            } catch (error) {
                if (searchId !== this.currentSearchId) return;
                console.error('Inline search error:', error);
                this._renderError();
            }
        }

        _updatePlaceholder() {
            if (this.searchInput) {
                const placeholder = this._t(`search.placeholder.${this.currentScope}`);
                this.searchInput.placeholder = placeholder;
            }
        }

        _showResults() {
            this.resultsPanel.hidden = false;
            this.isOpen = true;
            this.searchInput.setAttribute('aria-expanded', 'true');
        }

        _hideResults() {
            this.resultsPanel.hidden = true;
            this.isOpen = false;
            this.selectedIndex = -1;
            this.searchInput.setAttribute('aria-expanded', 'false');
        }

        _renderLoading() {
            this.resultsPanel.innerHTML = `
                <div class="inline-search-loading">
                    <div class="inline-search-loading__spinner"></div>
                    <span>${this._t('common.loading')}</span>
                </div>
            `;
        }

        _renderMinLengthHint() {
            this.resultsPanel.innerHTML = `
                <div class="inline-search-hint">
                    ${this._t('commands.min_length_hint')}
                </div>
            `;
        }

        _renderError() {
            this.resultsPanel.innerHTML = `
                <div class="inline-search-empty">
                    <div class="inline-search-empty__title">${this._t('search.results.search_error')}</div>
                </div>
            `;
        }

        _renderResults(data) {
            if (this.results.length === 0) {
                this.resultsPanel.innerHTML = `
                    <div class="inline-search-empty">
                        <svg class="inline-search-empty__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="11" cy="11" r="8"/>
                            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                            <line x1="8" y1="8" x2="14" y2="14"/>
                            <line x1="14" y1="8" x2="8" y2="14"/>
                        </svg>
                        <div class="inline-search-empty__title">${this._t('search.results.no_results')}</div>
                        <div class="inline-search-empty__hint">${this._t('commands.try_different')}</div>
                    </div>
                `;
                return;
            }

            let html = `
                <div class="inline-search-results__header">
                    <span>${this._t('search.results.showing').replace('{count}', this.results.length)}</span>
                    <span>${this._t(`search.scope.${this.currentScope}`)}</span>
                </div>
                <div class="inline-search-results__list" role="listbox">
            `;

            this.results.forEach((item, idx) => {
                const isSelected = idx === this.selectedIndex;
                html += `
                    <div class="inline-search-result ${isSelected ? 'selected' : ''}"
                         role="option"
                         aria-selected="${isSelected}"
                         data-index="${idx}"
                         onclick="InlineSearchBar._handleResultClick(${idx})">
                        <svg class="inline-search-result__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            ${this._getSourceIcon(item.source_type)}
                        </svg>
                        <div class="inline-search-result__content">
                            <div class="inline-search-result__title">${this._escapeHtml(item.title)}</div>
                            ${item.snippet ? `<div class="inline-search-result__snippet">${this._escapeHtml(item.snippet)}</div>` : ''}
                            <div class="inline-search-result__meta">
                                <span class="inline-search-result__source">${this._escapeHtml(item.source_type)}</span>
                                ${item.citation?.document ? `<span>${this._escapeHtml(item.citation.document)}</span>` : ''}
                            </div>
                        </div>
                    </div>
                `;
            });

            html += '</div>';
            this.resultsPanel.innerHTML = html;
        }

        _updateSelection() {
            const items = this.resultsPanel.querySelectorAll('.inline-search-result');
            items.forEach((item, idx) => {
                const isSelected = idx === this.selectedIndex;
                item.classList.toggle('selected', isSelected);
                item.setAttribute('aria-selected', isSelected);

                if (isSelected) {
                    item.scrollIntoView({ block: 'nearest' });
                }
            });
        }

        _getSourceIcon(sourceType) {
            const icons = {
                documents: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>',
                document_text: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/>',
                standards: '<path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>',
                findings: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
                evidence: '<path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>',
                knowledge_graph: '<circle cx="12" cy="12" r="3"/><line x1="12" y1="3" x2="12" y2="9"/><line x1="12" y1="15" x2="12" y2="21"/>',
                truth_index: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
                agent_sessions: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33"/>'
            };
            return icons[sourceType] || icons.documents;
        }

        _openResult(item) {
            this._hideResults();
            this.searchInput.value = '';

            // Get context
            const wrapper = document.querySelector('.main-wrapper');
            const institutionId = wrapper?.dataset.institutionId || '';

            // Navigate based on source type
            switch (item.source_type) {
                case 'documents':
                case 'document_text':
                    window.location.href = `/institutions/${institutionId}/documents?highlight=${item.source_id}`;
                    break;
                case 'standards':
                    window.location.href = `/standards?highlight=${item.source_id}`;
                    break;
                case 'findings':
                    window.location.href = `/institutions/${institutionId}/compliance?finding=${item.source_id}`;
                    break;
                case 'evidence':
                    window.location.href = `/institutions/${institutionId}/evidence?highlight=${item.source_id}`;
                    break;
                case 'knowledge_graph':
                    window.location.href = `/institutions/${institutionId}/knowledge-graph?entity=${item.source_id}`;
                    break;
                default:
                    console.log('Result clicked:', item);
            }
        }

        // Public API
        focus() {
            this.searchInput?.focus();
        }

        clear() {
            if (this.searchInput) {
                this.searchInput.value = '';
            }
            this._hideResults();
            this.results = [];
        }
    }

    // Static method for onclick handler
    InlineSearchBar._instance = null;
    InlineSearchBar._handleResultClick = function(idx) {
        if (InlineSearchBar._instance && InlineSearchBar._instance.results[idx]) {
            InlineSearchBar._instance._openResult(InlineSearchBar._instance.results[idx]);
        }
    };

    // Factory function
    InlineSearchBar.create = function(containerEl, options) {
        const instance = new InlineSearchBar(containerEl, options);
        InlineSearchBar._instance = instance;
        return instance;
    };

    return InlineSearchBar;
})();
