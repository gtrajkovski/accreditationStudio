/**
 * Audit Reproducibility Manager
 *
 * Loads and displays reproducibility bundle for an audit.
 */
class ReproducibilityManager {
    constructor() {
        this.institutionId = window.institutionId;
        this.auditId = window.auditId;
        this.data = null;
        this.technicalExpanded = false;

        this.init();
    }

    async init() {
        this.bindElements();
        this.setupEventListeners();
        await this.loadReproducibilityData();
    }

    bindElements() {
        // States
        this.loadingState = document.getElementById('loading-state');
        this.errorState = document.getElementById('error-state');
        this.errorMessage = document.getElementById('error-message');
        this.content = document.getElementById('content');

        // Summary
        this.summaryModel = document.getElementById('summary-model');
        this.summaryDate = document.getElementById('summary-date');
        this.summaryAccreditor = document.getElementById('summary-accreditor');
        this.summaryDocCount = document.getElementById('summary-doc-count');
        this.summaryThreshold = document.getElementById('summary-threshold');

        // Verification
        this.verificationBanner = document.getElementById('verification-banner');
        this.verificationIcon = document.getElementById('verification-icon');
        this.verificationTitle = document.getElementById('verification-title');
        this.verificationMessage = document.getElementById('verification-message');

        // Technical
        this.toggleBtn = document.getElementById('toggle-technical');
        this.technicalDetails = document.getElementById('technical-details');
        this.promptHash = document.getElementById('prompt-hash');
        this.promptText = document.getElementById('prompt-text');
        this.toolsHash = document.getElementById('tools-hash');
        this.truthHash = document.getElementById('truth-hash');
        this.docHashesTable = document.getElementById('document-hashes-table').querySelector('tbody');

        // Findings
        this.findingsList = document.getElementById('findings-list');

        // Modal
        this.modal = document.getElementById('finding-modal');
        this.modalPrompt = document.getElementById('modal-prompt');
        this.modalResponse = document.getElementById('modal-response');
        this.modalTokens = document.getElementById('modal-tokens');

        // Buttons
        this.verifyBtn = document.getElementById('verify-btn');
        this.exportBtn = document.getElementById('export-btn');
    }

    setupEventListeners() {
        // Technical toggle (D-05)
        this.toggleBtn.addEventListener('click', () => this.toggleTechnical());

        // Verify button
        this.verifyBtn.addEventListener('click', () => this.verifyReproducibility());

        // Export button
        this.exportBtn.addEventListener('click', () => this.exportBundle());

        // Modal close
        this.modal.querySelector('.modal-close').addEventListener('click', () => this.closeModal());
        this.modal.querySelector('.modal-backdrop').addEventListener('click', () => this.closeModal());

        // Keyboard
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.style.display !== 'none') {
                this.closeModal();
            }
        });
    }

    async loadReproducibilityData() {
        try {
            const response = await fetch(
                `/api/institutions/${this.institutionId}/audits/${this.auditId}/reproducibility?include_prompts=true`
            );

            if (!response.ok) {
                throw new Error(response.status === 404
                    ? 'No reproducibility data found for this audit.'
                    : 'Failed to load reproducibility data.');
            }

            this.data = await response.json();
            this.renderData();

        } catch (error) {
            this.showError(error.message);
        }
    }

    renderData() {
        // Hide loading, show content
        this.loadingState.style.display = 'none';
        this.content.style.display = 'block';

        // Executive summary (D-06)
        this.summaryModel.textContent = this.data.summary.model || '-';
        this.summaryDate.textContent = this.formatDate(this.data.created_at);
        this.summaryAccreditor.textContent = this.data.summary.accreditor || '-';
        this.summaryDocCount.textContent = this.data.summary.document_count || 0;
        this.summaryThreshold.textContent = (this.data.summary.confidence_threshold * 100).toFixed(0) + '%';

        // Technical details (D-07)
        this.promptHash.textContent = this.data.technical.system_prompt_hash || '-';
        this.promptText.textContent = this.data.technical.system_prompt || '(Not available)';
        this.toolsHash.textContent = this.data.technical.tool_definitions_hash || '-';
        this.truthHash.textContent = this.data.technical.truth_index_hash || '-';

        // Document hashes table
        this.docHashesTable.innerHTML = '';
        const hashes = this.data.technical.document_hashes || {};
        Object.entries(hashes).forEach(([docId, hash]) => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><code>${docId}</code></td>
                <td><code>${hash}</code></td>
            `;
            this.docHashesTable.appendChild(row);
        });

        if (Object.keys(hashes).length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="2">No documents</td>';
            this.docHashesTable.appendChild(row);
        }

        // Render verification if present
        if (this.data.verification) {
            this.renderVerification(this.data.verification);
        }
    }

    toggleTechnical() {
        this.technicalExpanded = !this.technicalExpanded;
        this.technicalDetails.style.display = this.technicalExpanded ? 'block' : 'none';

        const icon = this.toggleBtn.querySelector('.toggle-icon');
        icon.textContent = this.technicalExpanded ? '\u25BC' : '\u25B6';

        const text = this.technicalExpanded ? 'Hide Technical Details' : 'Show Technical Details';
        this.toggleBtn.innerHTML = `<span class="toggle-icon">${icon.textContent}</span> ${text}`;
    }

    async verifyReproducibility() {
        this.verifyBtn.disabled = true;
        this.verifyBtn.textContent = 'Verifying...';

        try {
            const response = await fetch(
                `/api/institutions/${this.institutionId}/audits/${this.auditId}/reproducibility?verify=true`
            );
            const data = await response.json();

            if (data.verification) {
                this.renderVerification(data.verification);
            }
        } catch (error) {
            console.error('Verification failed:', error);
        } finally {
            this.verifyBtn.disabled = false;
            this.verifyBtn.innerHTML = '<span class="icon">&#x2713;</span> Verify';
        }
    }

    renderVerification(verification) {
        this.verificationBanner.style.display = 'flex';

        if (verification.verified) {
            this.verificationBanner.className = 'verification-banner verified';
            this.verificationIcon.textContent = '\u2713';
            this.verificationTitle.textContent = 'Reproducible';
            this.verificationMessage.textContent = 'This audit can be reproduced with current system state.';
        } else {
            this.verificationBanner.className = 'verification-banner warning';
            this.verificationIcon.textContent = '\u26A0';
            this.verificationTitle.textContent = 'Discrepancies Detected';

            const discrepancies = verification.discrepancies || [];
            const messages = discrepancies.map(d => {
                if (d.type === 'model') {
                    return `Model changed: ${d.expected} → ${d.current}`;
                } else if (d.type === 'document') {
                    return `Document ${d.document_id} hash changed`;
                }
                return JSON.stringify(d);
            });
            this.verificationMessage.textContent = messages.join('; ') || 'See technical details.';
        }
    }

    exportBundle() {
        // Download as JSON
        const blob = new Blob([JSON.stringify(this.data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit_${this.auditId}_reproducibility.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    async loadFindingProvenance(findingId) {
        try {
            const response = await fetch(
                `/api/institutions/${this.institutionId}/audits/${this.auditId}/findings/${findingId}/provenance`
            );

            if (!response.ok) {
                throw new Error('Provenance not found');
            }

            const data = await response.json();
            this.showFindingModal(data);
        } catch (error) {
            console.error('Failed to load provenance:', error);
        }
    }

    showFindingModal(data) {
        this.modalPrompt.textContent = data.prompt_text || '(Not available)';
        this.modalResponse.textContent = data.response_text || '(Not available)';
        this.modalTokens.textContent = `Input: ${data.input_tokens || 0}, Output: ${data.output_tokens || 0}`;
        this.modal.style.display = 'block';
    }

    closeModal() {
        this.modal.style.display = 'none';
    }

    showError(message) {
        this.loadingState.style.display = 'none';
        this.errorState.style.display = 'block';
        this.errorMessage.textContent = message;
    }

    formatDate(isoString) {
        if (!isoString) return '-';
        const date = new Date(isoString);
        return date.toLocaleString();
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    new ReproducibilityManager();
});
