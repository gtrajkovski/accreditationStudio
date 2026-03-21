/**
 * Standard Explainer Module
 * Handles fetching and rendering plain-English explanations of standards.
 */

class StandardExplainer {
    constructor() {
        this.currentStandardId = null;
        this.cache = new Map();
    }

    /**
     * Initialize explainer for a container element.
     * @param {HTMLElement} container - Container element for the explanation
     * @param {string} standardId - ID of the standard to explain
     */
    async init(container, standardId) {
        this.currentStandardId = standardId;

        // Show loading state
        this.showLoading(container);

        try {
            const explanation = await this.fetchExplanation(standardId);
            this.renderExplanation(container, explanation);
        } catch (error) {
            this.showError(container, error.message);
        }
    }

    /**
     * Fetch explanation from API.
     * @param {string} standardId - ID of the standard
     * @returns {Promise<Object>} Explanation data
     */
    async fetchExplanation(standardId) {
        // Check cache first
        if (this.cache.has(standardId)) {
            return this.cache.get(standardId);
        }

        const response = await fetch(`/api/standards/${standardId}/explain`);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to fetch explanation');
        }

        const explanation = await response.json();
        this.cache.set(standardId, explanation);
        return explanation;
    }

    /**
     * Refresh explanation (invalidate cache and regenerate).
     * @param {string} standardId - ID of the standard
     * @param {HTMLElement} container - Container to update
     */
    async refreshExplanation(standardId, container) {
        this.showLoading(container);

        try {
            const response = await fetch(`/api/standards/${standardId}/explain/refresh`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to refresh explanation');
            }

            const explanation = await response.json();
            this.cache.set(standardId, explanation);
            this.renderExplanation(container, explanation);
        } catch (error) {
            this.showError(container, error.message);
        }
    }

    /**
     * Show loading skeleton.
     * @param {HTMLElement} container - Container element
     */
    showLoading(container) {
        container.innerHTML = `
            <div class="explanation-loading">
                <div class="skeleton skeleton-title"></div>
                <div class="skeleton skeleton-text"></div>
                <div class="skeleton skeleton-text"></div>
                <div class="skeleton skeleton-text" style="width: 60%;"></div>
            </div>
        `;
    }

    /**
     * Show error message.
     * @param {HTMLElement} container - Container element
     * @param {string} message - Error message
     */
    showError(container, message) {
        container.innerHTML = `
            <div class="explanation-error">
                <p class="error-message">${message}</p>
                <button class="btn btn-secondary" onclick="location.reload()">
                    Retry
                </button>
            </div>
        `;
    }

    /**
     * Render explanation in container.
     * @param {HTMLElement} container - Container element
     * @param {Object} data - Explanation data
     */
    renderExplanation(container, data) {
        const html = `
            <div class="standard-explanation">
                <div class="explanation-header">
                    <h3 class="explanation-title" data-i18n="standard_explainer.title">Plain English Explanation</h3>
                    <button class="btn btn-icon btn-sm" onclick="standardExplainer.refreshExplanation('${data.standard_id}', this.closest('.standard-explanation-container'))" title="Regenerate Explanation">
                        <svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
                            <path d="M11.534 7h3.932a.25.25 0 0 1 .192.41l-1.966 2.36a.25.25 0 0 1-.384 0l-1.966-2.36a.25.25 0 0 1 .192-.41zm-11 2h3.932a.25.25 0 0 0 .192-.41L2.692 6.23a.25.25 0 0 0-.384 0L.342 8.59A.25.25 0 0 0 .534 9z"/>
                            <path fill-rule="evenodd" d="M8 3c-1.552 0-2.94.707-3.857 1.818a.5.5 0 1 1-.771-.636A6.002 6.002 0 0 1 13.917 7H12.9A5.002 5.002 0 0 0 8 3zM3.1 9a5.002 5.002 0 0 0 8.757 2.182.5.5 0 1 1 .771.636A6.002 6.002 0 0 1 2.083 9H3.1z"/>
                        </svg>
                    </button>
                </div>

                <div class="explanation-content">
                    <p class="plain-english">${this.escapeHtml(data.plain_english)}</p>
                </div>

                <div class="explanation-section">
                    <h4 data-i18n="standard_explainer.required_evidence">Required Evidence</h4>
                    <ul class="evidence-list">
                        ${data.required_evidence.map(item => `
                            <li>
                                <label class="evidence-item">
                                    <input type="checkbox" class="evidence-checkbox">
                                    <span>${this.escapeHtml(item)}</span>
                                </label>
                            </li>
                        `).join('')}
                    </ul>
                </div>

                ${data.common_mistakes && data.common_mistakes.length > 0 ? `
                    <div class="explanation-section">
                        <h4 data-i18n="standard_explainer.common_mistakes">Common Mistakes to Avoid</h4>
                        <ul class="mistakes-list">
                            ${data.common_mistakes.map(mistake => `
                                <li>${this.escapeHtml(mistake)}</li>
                            `).join('')}
                        </ul>
                    </div>
                ` : ''}

                ${data.regulatory_context ? `
                    <details class="explanation-context">
                        <summary data-i18n="standard_explainer.why_matters">Why This Matters</summary>
                        <p>${this.escapeHtml(data.regulatory_context)}</p>
                    </details>
                ` : ''}

                ${data.confidence < 0.7 ? `
                    <div class="explanation-warning">
                        <strong>Note:</strong> This explanation has lower confidence (${(data.confidence * 100).toFixed(0)}%).
                        Please verify with official documentation.
                    </div>
                ` : ''}
            </div>
        `;

        container.innerHTML = html;
    }

    /**
     * Escape HTML to prevent XSS.
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Attach "Explain" buttons to standards on the page.
     * @param {string} selector - CSS selector for standard elements
     */
    attachExplainButtons(selector = '.standard-item') {
        const standards = document.querySelectorAll(selector);

        standards.forEach(standard => {
            const standardId = standard.dataset.standardId;
            if (!standardId) return;

            // Check if button already exists
            if (standard.querySelector('.btn-explain')) return;

            // Create button
            const btn = document.createElement('button');
            btn.className = 'btn btn-secondary btn-sm btn-explain';
            btn.innerHTML = '<span data-i18n="standard_explainer.explain">Explain</span>';
            btn.onclick = () => this.toggleExplanation(standard, standardId);

            // Add to standard element
            const actions = standard.querySelector('.standard-actions');
            if (actions) {
                actions.appendChild(btn);
            } else {
                standard.appendChild(btn);
            }
        });
    }

    /**
     * Toggle explanation visibility for a standard.
     * @param {HTMLElement} standardElement - Standard element
     * @param {string} standardId - Standard ID
     */
    async toggleExplanation(standardElement, standardId) {
        let container = standardElement.querySelector('.standard-explanation-container');

        if (container) {
            // Toggle visibility
            const isHidden = container.style.display === 'none';
            container.style.display = isHidden ? 'block' : 'none';
            return;
        }

        // Create container
        container = document.createElement('div');
        container.className = 'standard-explanation-container';
        standardElement.appendChild(container);

        // Load explanation
        await this.init(container, standardId);
    }
}

// Global instance
const standardExplainer = new StandardExplainer();

// Auto-initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    // Attach to standards if they exist
    if (document.querySelectorAll('.standard-item').length > 0) {
        standardExplainer.attachExplainButtons();
    }
});
