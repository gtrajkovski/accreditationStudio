/**
 * Evidence Assistant Frontend Module
 * Context-aware evidence finding for accreditation standards
 */

(function() {
    'use strict';

    // State
    let currentStandardId = null;
    let currentInstitutionId = null;
    let conversationHistory = [];

    // DOM Elements
    let standardSelector;
    let searchQueryInput;
    let findEvidenceBtn;
    let searchLoading;
    let emptyState;
    let resultsHeader;
    let standardInfo;
    let resultsCount;
    let resultsList;
    let noResults;
    let suggestionsPanel;
    let suggestionsList;

    /**
     * Initialize the Evidence Assistant page
     */
    function init() {
        // Get DOM elements
        standardSelector = document.getElementById('standard-selector');
        searchQueryInput = document.getElementById('search-query');
        findEvidenceBtn = document.getElementById('find-evidence-btn');
        searchLoading = document.getElementById('search-loading');
        emptyState = document.getElementById('empty-state');
        resultsHeader = document.getElementById('results-header');
        standardInfo = document.getElementById('standard-info');
        resultsCount = document.getElementById('results-count');
        resultsList = document.getElementById('results-list');
        noResults = document.getElementById('no-results');
        suggestionsPanel = document.getElementById('suggestions-panel');
        suggestionsList = document.getElementById('suggestions-list');

        // Get current institution from localStorage
        currentInstitutionId = localStorage.getItem('currentInstitutionId') || 'default';

        // Load standards for selector
        loadStandards();

        // Event listeners
        standardSelector.addEventListener('change', handleStandardChange);
        searchQueryInput.addEventListener('keypress', handleSearchKeypress);
        findEvidenceBtn.addEventListener('click', handleSearchClick);
    }

    /**
     * Load standards into the selector dropdown
     */
    async function loadStandards() {
        try {
            const response = await fetch('/api/standards');
            const data = await response.json();

            if (data.standards && data.standards.length > 0) {
                data.standards.forEach(standard => {
                    const option = document.createElement('option');
                    option.value = standard.id;
                    option.textContent = `${standard.code} - ${standard.title}`;
                    standardSelector.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Error loading standards:', error);
        }
    }

    /**
     * Handle standard selector change
     */
    function handleStandardChange(event) {
        currentStandardId = event.target.value;

        // Enable/disable search button
        findEvidenceBtn.disabled = !currentStandardId;

        // Clear previous results
        clearResults();
    }

    /**
     * Handle Enter key in search input
     */
    function handleSearchKeypress(event) {
        if (event.key === 'Enter' && currentStandardId) {
            handleSearchClick();
        }
    }

    /**
     * Handle search button click
     */
    async function handleSearchClick() {
        if (!currentStandardId) return;

        const query = searchQueryInput.value.trim() || null;

        await searchEvidence(currentStandardId, query);
    }

    /**
     * Search for evidence for a specific standard
     */
    async function searchEvidence(standardId, query) {
        // Show loading state
        showLoading();

        try {
            const response = await fetch('/api/evidence/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    standard_id: standardId,
                    institution_id: currentInstitutionId,
                    query: query,
                    context: {
                        current_page: 'evidence_assistant',
                        institution_id: currentInstitutionId
                    }
                })
            });

            const data = await response.json();

            if (response.ok) {
                renderResults(data);
                fetchSuggestions();
            } else {
                showError(data.error || 'Search failed');
            }
        } catch (error) {
            console.error('Error searching evidence:', error);
            showError('Network error occurred');
        } finally {
            hideLoading();
        }
    }

    /**
     * Render search results
     */
    function renderResults(data) {
        const { results, standard } = data;

        // Hide empty state, show results header
        emptyState.style.display = 'none';
        resultsHeader.style.display = 'block';

        // Update standard info
        standardInfo.innerHTML = `
            <strong>${standard.code}</strong> - ${standard.title}
        `;

        // Update results count
        resultsCount.textContent = `${results.length} ${results.length === 1 ? 'result' : 'results'} found`;

        // Clear previous results
        resultsList.innerHTML = '';

        if (results.length === 0) {
            noResults.style.display = 'block';
            resultsList.style.display = 'none';
        } else {
            noResults.style.display = 'none';
            resultsList.style.display = 'block';

            // Render evidence cards
            results.forEach(result => {
                const card = createEvidenceCard(result);
                resultsList.appendChild(card);
            });
        }
    }

    /**
     * Create an evidence card element
     */
    function createEvidenceCard(result) {
        const card = document.createElement('div');
        card.className = 'evidence-card';

        // Relevance badge
        const badgeClass = getBadgeClass(result.relevance_label);
        const badgeIcon = getBadgeIcon(result.relevance_label);

        // Confidence bar width
        const confidencePercent = Math.round(result.confidence * 100);

        card.innerHTML = `
            <div class="evidence-header">
                <div class="doc-type">
                    <span class="doc-icon">📄</span>
                    <span class="doc-type-text">${escapeHtml(result.doc_type || 'Document')}</span>
                </div>
                <span class="relevance-badge ${badgeClass}">
                    ${badgeIcon} ${result.relevance_label}
                </span>
            </div>

            <div class="evidence-snippet">
                ${escapeHtml(result.snippet)}
            </div>

            <div class="evidence-meta">
                ${result.page !== null ? `<span class="page-number">Page ${result.page}</span>` : ''}
                <span class="document-id">${result.document_id}</span>
            </div>

            <div class="confidence-bar-container">
                <div class="confidence-label">Confidence: ${confidencePercent}%</div>
                <div class="confidence-bar">
                    <div class="confidence-fill" style="width: ${confidencePercent}%"></div>
                </div>
            </div>

            <div class="evidence-actions">
                <a href="/documents/viewer?doc_id=${result.document_id}&page=${result.page || 1}"
                   class="btn btn-sm btn-secondary" target="_blank">
                    View Document
                </a>
            </div>
        `;

        return card;
    }

    /**
     * Fetch suggested follow-up prompts
     */
    async function fetchSuggestions() {
        try {
            const response = await fetch('/api/evidence/suggestions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    conversation_history: conversationHistory,
                    context: {
                        current_page: 'evidence_assistant',
                        active_standard_id: currentStandardId,
                        institution_id: currentInstitutionId
                    }
                })
            });

            const data = await response.json();

            if (response.ok && data.suggestions && data.suggestions.length > 0) {
                renderSuggestions(data.suggestions);
            }
        } catch (error) {
            console.error('Error fetching suggestions:', error);
        }
    }

    /**
     * Render suggested prompts
     */
    function renderSuggestions(suggestions) {
        suggestionsList.innerHTML = '';

        suggestions.forEach(suggestion => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.textContent = suggestion;
            item.addEventListener('click', () => {
                searchQueryInput.value = suggestion;
                handleSearchClick();
            });
            suggestionsList.appendChild(item);
        });

        suggestionsPanel.style.display = 'block';
    }

    /**
     * Get CSS class for relevance badge
     */
    function getBadgeClass(label) {
        switch (label) {
            case 'Required':
                return 'badge-required';
            case 'Relevant':
                return 'badge-relevant';
            case 'Related':
                return 'badge-related';
            default:
                return 'badge-related';
        }
    }

    /**
     * Get icon for relevance badge
     */
    function getBadgeIcon(label) {
        switch (label) {
            case 'Required':
                return '✓';
            case 'Relevant':
                return '●';
            case 'Related':
                return '○';
            default:
                return '○';
        }
    }

    /**
     * Show loading state
     */
    function showLoading() {
        findEvidenceBtn.disabled = true;
        searchLoading.style.display = 'block';
        resultsList.style.display = 'none';
        noResults.style.display = 'none';
    }

    /**
     * Hide loading state
     */
    function hideLoading() {
        findEvidenceBtn.disabled = false;
        searchLoading.style.display = 'none';
    }

    /**
     * Clear results and reset to empty state
     */
    function clearResults() {
        emptyState.style.display = 'block';
        resultsHeader.style.display = 'none';
        resultsList.innerHTML = '';
        noResults.style.display = 'none';
        suggestionsPanel.style.display = 'none';
    }

    /**
     * Show error message
     */
    function showError(message) {
        alert('Error: ' + message);
    }

    /**
     * Escape HTML to prevent XSS
     */
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
