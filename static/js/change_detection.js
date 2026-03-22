/**
 * Change Detection Controller
 * Handles badge polling, change review modal, and re-audit triggering.
 * Per user decisions D-01 (non-blocking), D-02 (user reviews when ready), D-07 (manual trigger).
 */

class ChangeDetectionManager {
    constructor() {
        this.institutionId = null;
        this.pollingInterval = 30000; // 30 seconds per D-02 (non-intrusive)
        this.pollTimer = null;
        this.pendingChanges = [];
        this.selectedDocIds = new Set();

        this.init();
    }

    init() {
        // Get institution ID from page data
        const instElement = document.querySelector('[data-institution-id]');
        if (instElement) {
            this.institutionId = instElement.dataset.institutionId;
        } else {
            // Try to get from URL or global
            const match = window.location.pathname.match(/institutions\/([^\/]+)/);
            if (match) {
                this.institutionId = match[1];
            }
        }

        // Start polling if we have an institution
        if (this.institutionId) {
            this.updateBadge();
            this.startPolling();
        }

        // Also check for global institution selector
        document.addEventListener('institutionChanged', (e) => {
            this.institutionId = e.detail.institutionId;
            this.updateBadge();
        });
    }

    startPolling() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
        }
        this.pollTimer = setInterval(() => this.updateBadge(), this.pollingInterval);
    }

    stopPolling() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
    }

    async updateBadge() {
        if (!this.institutionId) return;

        try {
            const response = await fetch(`/api/change-detection/pending-count?institution_id=${this.institutionId}`);
            if (!response.ok) return;

            const data = await response.json();
            const count = data.count || 0;

            const badge = document.getElementById('changes-card');
            const countEl = document.getElementById('changes-count');

            if (badge && countEl) {
                countEl.textContent = count;
                badge.style.display = count > 0 ? 'block' : 'none';
            }
        } catch (error) {
            console.error('Failed to update change badge:', error);
        }
    }

    async loadPendingChanges() {
        if (!this.institutionId) return;

        try {
            const response = await fetch(`/api/institutions/${this.institutionId}/changes/pending`);
            if (!response.ok) return;

            this.pendingChanges = await response.json();
            this.renderChangesList();
        } catch (error) {
            console.error('Failed to load pending changes:', error);
        }
    }

    renderChangesList() {
        const container = document.getElementById('changes-list');
        if (!container) return;

        if (this.pendingChanges.length === 0) {
            container.innerHTML = '<p class="text-muted">No pending changes.</p>';
            return;
        }

        container.innerHTML = this.pendingChanges.map(change => `
            <div class="change-item">
                <input type="checkbox"
                       class="change-item-checkbox"
                       data-doc-id="${change.document_id}"
                       onchange="changeDetection.toggleSelection('${change.document_id}')"
                       checked>
                <div class="change-item-info">
                    <div class="change-item-title">${change.document_id}</div>
                    <div class="change-item-meta">
                        Detected: ${new Date(change.detected_at).toLocaleString()}
                    </div>
                </div>
                <span class="change-item-badge modified">Modified</span>
            </div>
        `).join('');

        // Select all by default
        this.selectedDocIds = new Set(this.pendingChanges.map(c => c.document_id));
        this.updateReauditButton();
    }

    toggleSelection(docId) {
        if (this.selectedDocIds.has(docId)) {
            this.selectedDocIds.delete(docId);
        } else {
            this.selectedDocIds.add(docId);
        }
        this.updateReauditButton();
    }

    updateReauditButton() {
        const btn = document.getElementById('reaudit-btn');
        if (btn) {
            btn.disabled = this.selectedDocIds.size === 0;
        }

        // Update scope preview if documents selected
        if (this.selectedDocIds.size > 0) {
            this.loadReauditScope();
        } else {
            const scopeEl = document.getElementById('reaudit-scope');
            if (scopeEl) {
                scopeEl.style.display = 'none';
            }
        }
    }

    async loadReauditScope() {
        if (!this.institutionId || this.selectedDocIds.size === 0) return;

        try {
            const response = await fetch(`/api/institutions/${this.institutionId}/changes/scope/preview`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ document_ids: Array.from(this.selectedDocIds) })
            });

            if (!response.ok) return;

            const scope = await response.json();
            this.renderScope(scope);
        } catch (error) {
            console.error('Failed to load re-audit scope:', error);
        }
    }

    renderScope(scope) {
        const scopeEl = document.getElementById('reaudit-scope');
        const detailsEl = document.getElementById('scope-details');

        if (!scopeEl || !detailsEl) return;

        scopeEl.style.display = 'block';
        detailsEl.innerHTML = `
            <div class="scope-stat">
                <span class="scope-stat-label">Changed Documents</span>
                <span class="scope-stat-value">${scope.changed_documents.length}</span>
            </div>
            <div class="scope-stat">
                <span class="scope-stat-label">Affected Standards</span>
                <span class="scope-stat-value">${scope.affected_standards.length}</span>
            </div>
            <div class="scope-stat">
                <span class="scope-stat-label">Impacted Documents (cascade)</span>
                <span class="scope-stat-value">${scope.impacted_documents.length}</span>
            </div>
            <div class="scope-stat">
                <span class="scope-stat-label">Total to Re-audit</span>
                <span class="scope-stat-value highlight">${scope.total_to_audit}</span>
            </div>
        `;
    }

    showModal() {
        this.loadPendingChanges();
        const modal = document.getElementById('changes-modal');
        if (modal) {
            modal.style.display = 'flex';
        }
    }

    hideModal() {
        const modal = document.getElementById('changes-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
}

// Global instance
const changeDetection = new ChangeDetectionManager();

// Global functions for template onclick handlers
function showChangesModal() {
    changeDetection.showModal();
}

function hideChangesModal() {
    changeDetection.hideModal();
}

function triggerReaudit() {
    // Placeholder - implemented in Plan 22-03
    alert('Re-audit will be implemented in Plan 22-03');
}
