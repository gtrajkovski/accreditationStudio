/**
 * ScopeBadge - Visual scope indicator with Tab cycling
 *
 * Features:
 * - Displays current search scope as a pill-shaped badge
 * - Cycles through 6 scopes on Tab key press
 * - Emits 'scope-changed' custom event
 * - Uses i18n for localized scope labels
 */
window.ScopeBadge = (function() {
    'use strict';

    const SCOPES = ['global', 'institution', 'program', 'document', 'standards', 'compliance'];
    const TAB_DEBOUNCE_MS = 300; // Prevent rapid cycling

    class ScopeBadge {
        constructor(containerEl, initialScope = null) {
            this.container = containerEl;
            this.currentIndex = 0;
            this.lastTabTime = 0;

            // Detect initial scope from page context
            if (initialScope) {
                const idx = SCOPES.indexOf(initialScope);
                if (idx !== -1) this.currentIndex = idx;
            } else {
                this.currentIndex = SCOPES.indexOf(this._detectContextScope());
            }

            this.render();
        }

        // Detect scope from data attributes on body/main-wrapper
        _detectContextScope() {
            const wrapper = document.querySelector('.main-wrapper');
            if (!wrapper) return 'global';

            const page = wrapper.dataset.page || '';
            const instId = wrapper.dataset.institutionId;
            const progId = wrapper.dataset.programId;
            const docId = wrapper.dataset.documentId;

            if (docId) return 'document';
            if (progId) return 'program';
            if (page.includes('compliance')) return 'compliance';
            if (page.includes('standards')) return 'standards';
            if (instId) return 'institution';
            return 'global';
        }

        getCurrentScope() {
            return SCOPES[this.currentIndex];
        }

        cycle() {
            const now = Date.now();
            if (now - this.lastTabTime < TAB_DEBOUNCE_MS) return false;
            this.lastTabTime = now;

            this.currentIndex = (this.currentIndex + 1) % SCOPES.length;
            this.render();
            this._emit('scope-changed', this.getCurrentScope());
            return true;
        }

        setScope(scope) {
            const idx = SCOPES.indexOf(scope);
            if (idx !== -1 && idx !== this.currentIndex) {
                this.currentIndex = idx;
                this.render();
            }
        }

        render() {
            const scope = this.getCurrentScope();
            const label = this._t(`search.scope.${scope}`);

            this.container.innerHTML = `
                <span class="scope-badge scope-badge--${scope}"
                      aria-label="Search scope: ${label}"
                      aria-live="polite">
                    ${this._escapeHtml(label)}
                    <svg class="scope-badge__chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M6 9l6 6 6-6"/>
                    </svg>
                </span>
            `;
        }

        _t(key) {
            if (window.AccreditAI && window.AccreditAI.i18n) {
                return window.AccreditAI.i18n.t(key);
            }
            // Fallback: extract last segment
            return key.split('.').pop().replace(/_/g, ' ');
        }

        _escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        _emit(eventName, detail) {
            this.container.dispatchEvent(new CustomEvent(eventName, {
                detail,
                bubbles: true
            }));
        }
    }

    return ScopeBadge;
})();
