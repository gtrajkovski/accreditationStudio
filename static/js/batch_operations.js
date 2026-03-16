/**
 * Batch Operations Module
 * Handles batch selection, cost confirmation, and progress tracking for audits and remediations
 */

// ============================================
// BatchSelectionManager Class
// ============================================
class BatchSelectionManager {
    constructor(operationType) {
        this.operationType = operationType; // 'audit' or 'remediation'
        this.selectedIds = new Set();
        this.documents = new Map(); // id -> {name, doc_type, ...}
    }

    toggle(docId, docData) {
        if (this.selectedIds.has(docId)) {
            this.selectedIds.delete(docId);
            this.documents.delete(docId);
        } else {
            this.selectedIds.add(docId);
            this.documents.set(docId, docData);
        }
    }

    selectAll(docs) {
        docs.forEach(doc => {
            this.selectedIds.add(doc.id);
            this.documents.set(doc.id, doc);
        });
    }

    clearSelection() {
        this.selectedIds.clear();
        this.documents.clear();
    }

    getSelectedDocs() {
        return Array.from(this.documents.values());
    }

    getSelectedIds() {
        return Array.from(this.selectedIds);
    }

    getCount() {
        return this.selectedIds.size;
    }

    isSelected(docId) {
        return this.selectedIds.has(docId);
    }
}

// ============================================
// BatchActionBar Class
// ============================================
class BatchActionBar {
    constructor(selectionManager, institutionId) {
        this.selectionManager = selectionManager;
        this.institutionId = institutionId;
        this.element = null;
        this.render();
    }

    render() {
        // Create floating bar element
        this.element = document.createElement('div');
        this.element.id = 'batchActionBar';
        this.element.className = 'batch-action-bar hidden';

        const actionLabel = this.selectionManager.operationType === 'audit'
            ? 'Batch Audit'
            : 'Batch Remediate';

        this.element.innerHTML = `
            <span class="batch-selection-count">0 selected</span>
            <button class="btn btn-primary" id="batchActionBtn">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;">
                    <path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
                </svg>
                ${actionLabel}
            </button>
            <button class="btn btn-secondary" id="batchClearBtn">Clear</button>
        `;

        document.body.appendChild(this.element);

        // Attach event listeners
        document.getElementById('batchActionBtn').addEventListener('click', () => {
            this.onAction();
        });

        document.getElementById('batchClearBtn').addEventListener('click', () => {
            this.onClear();
        });
    }

    show() {
        this.element.classList.remove('hidden');
    }

    hide() {
        this.element.classList.add('hidden');
    }

    updateCount(count) {
        const countEl = this.element.querySelector('.batch-selection-count');
        countEl.textContent = `${count} selected`;

        if (count > 0) {
            this.show();
        } else {
            this.hide();
        }
    }

    async onAction() {
        const selectedIds = this.selectionManager.getSelectedIds();
        if (selectedIds.length === 0) return;

        // Show cost confirmation modal
        const confirmModal = new CostConfirmationModal(this.institutionId, this.selectionManager.operationType);
        const result = await confirmModal.show(selectedIds);

        if (result.confirmed) {
            // Start batch operation
            this.startBatch(selectedIds, result.concurrency);
        }
    }

    onClear() {
        this.selectionManager.clearSelection();
        this.updateCount(0);

        // Uncheck all checkboxes
        document.querySelectorAll('.batch-select-checkbox').forEach(cb => {
            cb.checked = false;
        });
        document.querySelectorAll('.document-row').forEach(row => {
            row.classList.remove('selected');
        });

        const selectAllCb = document.getElementById('selectAll');
        if (selectAllCb) selectAllCb.checked = false;
    }

    async startBatch(documentIds, concurrency) {
        try {
            const endpoint = this.selectionManager.operationType === 'audit'
                ? `/api/institutions/${this.institutionId}/audits/batch`
                : `/api/institutions/${this.institutionId}/remediations/batch`;

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    document_ids: documentIds,
                    concurrency: concurrency,
                    confirmed: true
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Failed to start batch');
            }

            const data = await response.json();

            // Clear selection
            this.onClear();

            // Show progress modal
            const progressModal = new BatchProgressModal(
                data.batch_id,
                this.selectionManager.operationType,
                this.institutionId
            );
            progressModal.show(data.document_count);

        } catch (error) {
            console.error('Batch start error:', error);
            if (window.toast) {
                window.toast.error(error.message);
            } else {
                alert('Error: ' + error.message);
            }
        }
    }
}

// ============================================
// CostConfirmationModal Class
// ============================================
class CostConfirmationModal {
    constructor(institutionId, operationType) {
        this.institutionId = institutionId;
        this.operationType = operationType;
        this.element = null;
        this.resolvePromise = null;
    }

    async show(documentIds) {
        return new Promise(async (resolve) => {
            this.resolvePromise = resolve;

            // Fetch cost estimate
            const estimate = await this.fetchEstimate(documentIds);

            if (!estimate) {
                resolve({ confirmed: false });
                return;
            }

            // Create modal
            this.render(estimate, documentIds.length);

            // Setup event listeners
            this.setupEventListeners();
        });
    }

    async fetchEstimate(documentIds) {
        try {
            const endpoint = this.operationType === 'audit'
                ? `/api/institutions/${this.institutionId}/audits/batch/estimate`
                : `/api/institutions/${this.institutionId}/remediations/batch/estimate`;

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    document_ids: documentIds,
                    model: 'claude-sonnet-4-20250514'
                })
            });

            if (!response.ok) {
                throw new Error('Failed to fetch estimate');
            }

            return await response.json();
        } catch (error) {
            console.error('Cost estimate error:', error);
            if (window.toast) {
                window.toast.error('Failed to estimate cost');
            }
            return null;
        }
    }

    render(estimate, documentCount) {
        this.element = document.createElement('div');
        this.element.className = 'cost-modal';
        this.element.id = 'costConfirmModal';

        const hasWarning = estimate.warning || documentCount > 20;
        const warningText = estimate.warning || 'Large batch may take a while. Continue?';

        this.element.innerHTML = `
            <div class="modal-backdrop"></div>
            <div class="cost-modal-content">
                <div class="modal-header">
                    <h3>Confirm Batch ${this.operationType === 'audit' ? 'Audit' : 'Remediation'}</h3>
                    <button class="btn btn-ghost close-btn">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="cost-estimate">
                        <div class="cost-label">Estimated Cost</div>
                        <div class="cost-total">~$${estimate.total_cost.toFixed(2)}</div>
                        <div class="cost-details">
                            ${documentCount} document${documentCount !== 1 ? 's' : ''} &bull;
                            ${estimate.breakdown.input_tokens.toLocaleString()} input tokens &bull;
                            ${estimate.breakdown.output_tokens.toLocaleString()} output tokens
                        </div>
                    </div>

                    ${hasWarning ? `
                        <div class="cost-warning">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 20px; height: 20px;">
                                <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                                <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
                            </svg>
                            <span>${warningText}</span>
                        </div>
                    ` : ''}

                    <div class="concurrency-control">
                        <label for="concurrencySlider">
                            <span>Concurrency: <span id="concurrencyValue">3</span></span>
                        </label>
                        <input type="range" id="concurrencySlider" class="concurrency-slider"
                               min="1" max="5" value="3" step="1">
                        <div class="concurrency-help">Process 1-5 documents in parallel. Higher is faster but may hit rate limits.</div>
                    </div>

                    <div class="cost-disclaimer">
                        Estimated based on averages. Actual cost may vary ±20%.
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary cancel-btn">Cancel</button>
                    <button class="btn btn-primary confirm-btn">Confirm & Start</button>
                </div>
            </div>
        `;

        document.body.appendChild(this.element);
    }

    setupEventListeners() {
        // Close handlers
        const closeBtn = this.element.querySelector('.close-btn');
        const cancelBtn = this.element.querySelector('.cancel-btn');
        const backdrop = this.element.querySelector('.modal-backdrop');

        closeBtn.addEventListener('click', () => this.close(false));
        cancelBtn.addEventListener('click', () => this.close(false));
        backdrop.addEventListener('click', () => this.close(false));

        // Confirm handler
        const confirmBtn = this.element.querySelector('.confirm-btn');
        confirmBtn.addEventListener('click', () => {
            const concurrency = parseInt(document.getElementById('concurrencySlider').value);
            this.close(true, concurrency);
        });

        // Concurrency slider
        const slider = document.getElementById('concurrencySlider');
        const valueDisplay = document.getElementById('concurrencyValue');
        slider.addEventListener('input', (e) => {
            valueDisplay.textContent = e.target.value;
        });
    }

    close(confirmed = false, concurrency = 3) {
        if (this.element) {
            this.element.remove();
        }

        if (this.resolvePromise) {
            this.resolvePromise({ confirmed, concurrency });
        }
    }
}

// ============================================
// BatchProgressModal Class
// ============================================
class BatchProgressModal {
    constructor(batchId, operationType, institutionId) {
        this.batchId = batchId;
        this.operationType = operationType;
        this.institutionId = institutionId;
        this.element = null;
        this.eventSource = null;
        this.isMinimized = false;
        this.documentItems = new Map(); // docId -> {status, result}
        this.stats = {
            total: 0,
            completed: 0,
            failed: 0,
            running: 0
        };
    }

    show(documentCount) {
        this.stats.total = documentCount;
        this.render();
        this.startStreaming();
    }

    render() {
        this.element = document.createElement('div');
        this.element.className = 'batch-progress-modal';
        this.element.id = 'batchProgressModal';

        const title = this.operationType === 'audit' ? 'Batch Audit' : 'Batch Remediation';

        this.element.innerHTML = `
            <div class="modal-backdrop"></div>
            <div class="progress-modal-content">
                <div class="modal-header">
                    <h3>${title} - <span id="progressDocCount">${this.stats.total}</span> documents</h3>
                    <div class="header-actions">
                        <button class="btn btn-ghost minimize-btn" title="Minimize">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;">
                                <path d="M19 12H5"/>
                            </svg>
                        </button>
                        <button class="btn btn-ghost close-btn" title="Close (keeps running)">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;">
                                <path d="M18 6L6 18M6 6l12 12"/>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="modal-body">
                    <div class="progress-summary">
                        <div class="progress-bar-container">
                            <div class="progress-bar-fill" id="progressBarFill" style="width: 0%"></div>
                        </div>
                        <div class="progress-stats">
                            <span><strong id="completedCount">0</strong> / <strong id="totalCount">${this.stats.total}</strong> completed</span>
                            <span id="failedCount" class="failed-count" style="display: none;"><strong>0</strong> failed</span>
                        </div>
                    </div>

                    <div class="documents-list" id="documentsList">
                        <div class="text-muted text-center" style="padding: var(--spacing-lg);">
                            Initializing batch...
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-danger cancel-batch-btn">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;">
                            <circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/>
                        </svg>
                        Cancel Batch
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(this.element);
        this.setupEventListeners();
    }

    setupEventListeners() {
        const minimizeBtn = this.element.querySelector('.minimize-btn');
        const closeBtn = this.element.querySelector('.close-btn');
        const cancelBtn = this.element.querySelector('.cancel-batch-btn');

        minimizeBtn.addEventListener('click', () => this.minimize());
        closeBtn.addEventListener('click', () => this.close());
        cancelBtn.addEventListener('click', () => this.cancel());
    }

    startStreaming() {
        const endpoint = this.operationType === 'audit'
            ? `/api/institutions/${this.institutionId}/audits/batch/${this.batchId}/stream`
            : `/api/institutions/${this.institutionId}/remediations/batch/${this.batchId}/stream`;

        this.eventSource = new EventSource(endpoint);

        this.eventSource.addEventListener('batch_started', (e) => {
            const data = JSON.parse(e.data);
            console.log('Batch started:', data);
        });

        this.eventSource.addEventListener('progress', (e) => {
            const data = JSON.parse(e.data);
            this.updateProgress(data);
        });

        this.eventSource.addEventListener('item_completed', (e) => {
            const data = JSON.parse(e.data);
            this.updateItem(data.doc_id, 'completed', data);
        });

        this.eventSource.addEventListener('item_failed', (e) => {
            const data = JSON.parse(e.data);
            this.updateItem(data.doc_id, 'failed', data);
        });

        this.eventSource.addEventListener('batch_completed', (e) => {
            const data = JSON.parse(e.data);
            this.onComplete(data.summary);
            this.eventSource.close();
        });

        this.eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            this.eventSource.close();
        };
    }

    updateProgress(data) {
        this.stats.completed = data.completed;
        this.stats.failed = data.failed;

        // Update progress bar
        const progressPct = data.progress_pct || 0;
        document.getElementById('progressBarFill').style.width = `${progressPct}%`;

        // Update stats
        document.getElementById('completedCount').textContent = data.completed;
        document.getElementById('totalCount').textContent = data.total;

        if (data.failed > 0) {
            const failedEl = document.getElementById('failedCount');
            failedEl.style.display = 'inline';
            failedEl.querySelector('strong').textContent = data.failed;
        }
    }

    updateItem(docId, status, result) {
        this.documentItems.set(docId, { status, result });
        this.renderDocumentsList();
    }

    renderDocumentsList() {
        const listEl = document.getElementById('documentsList');

        if (this.documentItems.size === 0) {
            return; // Keep "Initializing..." message
        }

        const items = Array.from(this.documentItems.entries()).map(([docId, item]) => {
            const statusIcons = {
                pending: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="status-icon"><circle cx="12" cy="12" r="10"/></svg>',
                running: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="status-icon"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>',
                completed: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="status-icon"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/></svg>',
                failed: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="status-icon"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>'
            };

            const icon = statusIcons[item.status] || statusIcons.pending;
            const docName = item.result?.doc_name || docId.slice(0, 12) + '...';
            const extraInfo = item.status === 'completed'
                ? `<span class="item-info">${item.result?.findings_count || 0} findings</span>`
                : item.status === 'failed'
                ? `<span class="item-error">${item.result?.error || 'Unknown error'}</span>`
                : '';

            return `
                <div class="document-item ${item.status}">
                    ${icon}
                    <span class="document-name">${docName}</span>
                    ${extraInfo}
                </div>
            `;
        }).join('');

        listEl.innerHTML = items;
    }

    minimize() {
        this.isMinimized = true;
        this.element.querySelector('.progress-modal-content').style.display = 'none';

        // Create toast
        const toast = document.createElement('div');
        toast.className = 'batch-toast';
        toast.id = 'batchToast';
        toast.innerHTML = `
            <div style="display: flex; align-items: center; gap: var(--spacing-sm);">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;">
                    <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
                </svg>
                <span>${this.operationType === 'audit' ? 'Audit' : 'Remediation'} in progress...</span>
            </div>
            <div class="mini-progress" style="margin-top: var(--spacing-xs);">
                <div class="progress-bar-container" style="height: 4px;">
                    <div class="progress-bar-fill" id="miniProgressFill" style="width: ${this.getProgressPct()}%"></div>
                </div>
            </div>
        `;

        toast.addEventListener('click', () => {
            toast.remove();
            this.element.querySelector('.progress-modal-content').style.display = 'block';
            this.isMinimized = false;
        });

        document.body.appendChild(toast);
    }

    getProgressPct() {
        if (this.stats.total === 0) return 0;
        return Math.round((this.stats.completed / this.stats.total) * 100);
    }

    async cancel() {
        if (!confirm('Cancel this batch operation? Completed items will be kept.')) {
            return;
        }

        try {
            const endpoint = this.operationType === 'audit'
                ? `/api/institutions/${this.institutionId}/audits/batch/${this.batchId}/cancel`
                : `/api/institutions/${this.institutionId}/remediations/batch/${this.batchId}/cancel`;

            const response = await fetch(endpoint, { method: 'POST' });

            if (response.ok) {
                if (window.toast) {
                    window.toast.info('Batch cancelled. Completed items preserved.');
                }
                this.close();
            }
        } catch (error) {
            console.error('Cancel error:', error);
        }
    }

    close() {
        if (this.eventSource) {
            this.eventSource.close();
        }

        const toast = document.getElementById('batchToast');
        if (toast) toast.remove();

        if (this.element) {
            this.element.remove();
        }
    }

    onComplete(summary) {
        // Update footer with completion summary
        const footer = this.element.querySelector('.modal-footer');
        const successCount = summary.completed || 0;
        const failCount = summary.failed || 0;
        const total = summary.total || this.stats.total;

        footer.innerHTML = `
            <div class="batch-summary">
                <h4>Batch Complete</h4>
                <div class="batch-summary-stats">
                    <div class="batch-summary-stat">
                        <span>Completed</span>
                        <span class="text-success"><strong>${successCount}</strong></span>
                    </div>
                    <div class="batch-summary-stat">
                        <span>Failed</span>
                        <span class="text-danger"><strong>${failCount}</strong></span>
                    </div>
                    <div class="batch-summary-stat">
                        <span>Total</span>
                        <span><strong>${total}</strong></span>
                    </div>
                </div>

                ${failCount > 0 ? `
                    <button class="btn btn-warning retry-btn" style="margin-top: var(--spacing-sm);">
                        Retry Failed Items
                    </button>
                ` : ''}

                ${this.operationType === 'audit' && successCount > 0 ? `
                    <div class="chain-offer">
                        <p><strong>${successCount} document${successCount !== 1 ? 's' : ''} have issues.</strong></p>
                        <button class="btn btn-primary chain-remediate-btn">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width: 16px; height: 16px;">
                                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                                <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                            </svg>
                            Remediate All
                        </button>
                    </div>
                ` : ''}

                <button class="btn btn-secondary close-summary-btn" style="margin-top: var(--spacing-md);">
                    Close
                </button>
            </div>
        `;

        // Setup completion handlers
        const closeBtn = footer.querySelector('.close-summary-btn');
        closeBtn.addEventListener('click', () => this.close());

        if (failCount > 0) {
            const retryBtn = footer.querySelector('.retry-btn');
            retryBtn.addEventListener('click', () => this.retryFailed());
        }

        if (this.operationType === 'audit' && successCount > 0) {
            const chainBtn = footer.querySelector('.chain-remediate-btn');
            chainBtn.addEventListener('click', () => this.chainRemediation());
        }
    }

    async retryFailed() {
        try {
            const endpoint = this.operationType === 'audit'
                ? `/api/institutions/${this.institutionId}/audits/batch/${this.batchId}/retry-failed`
                : `/api/institutions/${this.institutionId}/remediations/batch/${this.batchId}/retry-failed`;

            const response = await fetch(endpoint, { method: 'POST' });

            if (!response.ok) throw new Error('Retry failed');

            const data = await response.json();

            // Close current modal
            this.close();

            // Open new progress modal for retry batch
            const retryModal = new BatchProgressModal(
                data.new_batch_id,
                this.operationType,
                this.institutionId
            );
            retryModal.show(data.retrying_count);

        } catch (error) {
            console.error('Retry error:', error);
            if (window.toast) {
                window.toast.error('Failed to retry');
            }
        }
    }

    async chainRemediation() {
        try {
            const endpoint = `/api/institutions/${this.institutionId}/remediations/batch/from-audit/${this.batchId}`;

            const response = await fetch(endpoint, { method: 'POST' });

            if (!response.ok) throw new Error('Chain failed');

            const data = await response.json();

            // Close current modal
            this.close();

            // Open new progress modal for remediation batch
            const remediationModal = new BatchProgressModal(
                data.batch_id,
                'remediation',
                this.institutionId
            );
            remediationModal.show(data.document_count);

        } catch (error) {
            console.error('Chain error:', error);
            if (window.toast) {
                window.toast.error('Failed to start remediation');
            }
        }
    }
}

// ============================================
// Public API
// ============================================
function initBatchOperations(institutionId, operationType) {
    const selectionManager = new BatchSelectionManager(operationType);
    const actionBar = new BatchActionBar(selectionManager, institutionId);

    return {
        selectionManager,
        actionBar,
        startBatch: async () => {
            actionBar.onAction();
        }
    };
}

// Export for use in templates
window.BatchOperations = {
    init: initBatchOperations
};
