/**
 * Bulk Remediation UI Controller
 *
 * Manages the wizard flow for fixing all findings:
 * 1. Scope selection with preview
 * 2. SSE progress tracking
 * 3. Batch approval interface
 */

const BulkRemediation = {
    institutionId: null,
    currentJobId: null,
    eventSource: null,
    isPaused: false,

    /**
     * Initialize the bulk remediation interface.
     * @param {string} institutionId - The institution ID
     */
    init(institutionId) {
        this.institutionId = institutionId;
        this.bindEvents();
        this.updatePreview();
    },

    /**
     * Bind all event listeners.
     */
    bindEvents() {
        // Scope type radio buttons
        document.querySelectorAll('input[name="scope_type"]').forEach(radio => {
            radio.addEventListener('change', () => this.onScopeChange());
        });

        // Dropdown changes trigger preview update
        const docTypeSelect = document.getElementById('doc-type-select');
        if (docTypeSelect) {
            docTypeSelect.addEventListener('change', () => this.updatePreview());
        }

        const programSelect = document.getElementById('program-select');
        if (programSelect) {
            programSelect.addEventListener('change', () => this.updatePreview());
        }

        // Severity checkboxes
        document.querySelectorAll('.severity-checks input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', () => this.updatePreview());
        });

        // Start button
        const startBtn = document.getElementById('start-btn');
        if (startBtn) {
            startBtn.addEventListener('click', () => this.startJob());
        }

        // Pause/Cancel buttons
        const pauseBtn = document.getElementById('pause-btn');
        if (pauseBtn) {
            pauseBtn.addEventListener('click', () => this.togglePause());
        }

        const cancelBtn = document.getElementById('cancel-btn');
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.cancelJob());
        }

        // Approval buttons
        const approveAllBtn = document.getElementById('approve-all-btn');
        if (approveAllBtn) {
            approveAllBtn.addEventListener('click', () => this.approveAll());
        }

        const rejectAllBtn = document.getElementById('reject-all-btn');
        if (rejectAllBtn) {
            rejectAllBtn.addEventListener('click', () => this.rejectAll());
        }
    },

    /**
     * Handle scope type change.
     */
    onScopeChange() {
        const scopeType = document.querySelector('input[name="scope_type"]:checked').value;

        // Enable/disable selects based on scope type
        const docTypeSelect = document.getElementById('doc-type-select');
        const programSelect = document.getElementById('program-select');
        const severityChecks = document.querySelector('.severity-checks');

        if (docTypeSelect) {
            docTypeSelect.disabled = scopeType !== 'doc_type';
        }
        if (programSelect) {
            programSelect.disabled = scopeType !== 'program';
        }
        if (severityChecks) {
            severityChecks.style.display = scopeType === 'severity' ? 'flex' : 'none';
        }

        this.updatePreview();
    },

    /**
     * Get the current scope configuration.
     * @returns {Object} The scope object
     */
    getScope() {
        const scopeType = document.querySelector('input[name="scope_type"]:checked').value;
        const scope = { scope_type: scopeType };

        if (scopeType === 'doc_type') {
            const selected = document.getElementById('doc-type-select').value;
            if (selected) scope.doc_types = [selected];
        } else if (scopeType === 'program') {
            const selected = document.getElementById('program-select').value;
            if (selected) scope.program_ids = [selected];
        } else if (scopeType === 'severity') {
            scope.severities = Array.from(
                document.querySelectorAll('.severity-checks input:checked')
            ).map(cb => cb.value);
        }

        return scope;
    },

    /**
     * Update the preview panel with document/finding counts.
     */
    async updatePreview() {
        const scope = this.getScope();
        const previewDocs = document.getElementById('preview-docs');
        const previewFindings = document.getElementById('preview-findings');
        const startBtn = document.getElementById('start-btn');

        // Show loading state
        if (previewDocs) previewDocs.textContent = '...';
        if (previewFindings) previewFindings.textContent = '...';

        try {
            const response = await fetch(`/api/institutions/${this.institutionId}/bulk-remediation/preview`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(scope)
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            if (previewDocs) previewDocs.textContent = data.document_count || 0;
            if (previewFindings) previewFindings.textContent = data.total_findings || 0;
            if (startBtn) startBtn.disabled = (data.document_count || 0) === 0;

        } catch (error) {
            console.error('Preview error:', error);
            if (previewDocs) previewDocs.textContent = '-';
            if (previewFindings) previewFindings.textContent = '-';
            if (startBtn) startBtn.disabled = true;
        }
    },

    /**
     * Start a new bulk remediation job.
     */
    async startJob() {
        const scope = this.getScope();

        try {
            // Create job
            const createResponse = await fetch(`/api/institutions/${this.institutionId}/bulk-remediation/jobs`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(scope)
            });

            if (!createResponse.ok) {
                throw new Error(`Failed to create job: ${createResponse.status}`);
            }

            const job = await createResponse.json();
            this.currentJobId = job.id;

            // Show progress section, hide scope section
            document.getElementById('scope-section').style.display = 'none';
            document.getElementById('progress-section').style.display = 'block';

            // Update progress count
            const progressCount = document.getElementById('progress-count');
            if (progressCount) {
                progressCount.textContent = `0 / ${job.total_documents} documents`;
            }

            // Start SSE connection for progress
            this.startProgressStream();

        } catch (error) {
            console.error('Start job error:', error);
            this.showToast('Failed to start bulk remediation: ' + error.message, 'error');
        }
    },

    /**
     * Start SSE connection for progress updates.
     */
    startProgressStream() {
        this.eventSource = new EventSource(
            `/api/institutions/${this.institutionId}/bulk-remediation/jobs/${this.currentJobId}/run`
        );

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleProgressEvent(data);
            } catch (e) {
                console.error('Parse error:', e);
            }
        };

        this.eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            this.eventSource.close();
        };
    },

    /**
     * Handle progress events from SSE stream.
     * @param {Object} data - Event data
     */
    handleProgressEvent(data) {
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const progressCount = document.getElementById('progress-count');

        switch (data.event) {
            case 'start':
                // Job started
                break;

            case 'processing':
                if (progressBar) progressBar.style.width = `${data.progress}%`;
                if (progressText) progressText.textContent = `${Math.round(data.progress)}%`;
                this.addProgressItem(data.document_name, 'running');
                break;

            case 'complete':
                this.updateProgressItem(data.document_name, 'complete', `${data.changes} fixes`);
                break;

            case 'failed':
                this.updateProgressItem(data.document_name, 'failed', data.error);
                break;

            case 'stopped':
                // Job was paused or cancelled
                this.showToast(`Job ${data.reason}`, 'warning');
                break;

            case 'done':
                this.eventSource.close();
                if (progressBar) progressBar.style.width = '100%';
                if (progressText) progressText.textContent = '100%';
                if (progressCount) {
                    progressCount.textContent = `${data.total} documents processed (${data.successful} successful, ${data.failed} failed)`;
                }
                this.showApprovalSection();
                break;
        }
    },

    /**
     * Add a progress item to the list.
     * @param {string} name - Document name
     * @param {string} status - Status (running, complete, failed)
     */
    addProgressItem(name, status) {
        const list = document.getElementById('progress-list');
        if (!list) return;

        const itemId = `item-${name.replace(/\W/g, '')}`;

        // Check if item already exists
        if (document.getElementById(itemId)) {
            return;
        }

        const item = document.createElement('div');
        item.className = `progress-item status-${status}`;
        item.id = itemId;
        item.innerHTML = `
            <span class="item-icon">${status === 'running' ? '<span class="spinner-small"></span>' : ''}</span>
            <span class="item-name">${this.escapeHtml(name)}</span>
            <span class="item-status">${status}</span>
        `;
        list.appendChild(item);

        // Scroll to bottom
        list.scrollTop = list.scrollHeight;
    },

    /**
     * Update an existing progress item.
     * @param {string} name - Document name
     * @param {string} status - New status
     * @param {string} detail - Status detail
     */
    updateProgressItem(name, status, detail) {
        const itemId = `item-${name.replace(/\W/g, '')}`;
        const item = document.getElementById(itemId);
        if (item) {
            item.className = `progress-item status-${status}`;
            const iconEl = item.querySelector('.item-icon');
            const statusEl = item.querySelector('.item-status');

            if (iconEl) {
                iconEl.textContent = status === 'complete' ? '\u2713' : '\u2717';
            }
            if (statusEl) {
                statusEl.textContent = detail || status;
            }
        }
    },

    /**
     * Toggle pause/resume for the current job.
     */
    async togglePause() {
        if (!this.currentJobId) return;

        const endpoint = this.isPaused ? 'resume' : 'pause';

        try {
            const response = await fetch(
                `/api/institutions/${this.institutionId}/bulk-remediation/jobs/${this.currentJobId}/${endpoint}`,
                { method: 'POST' }
            );

            if (response.ok) {
                this.isPaused = !this.isPaused;
                const pauseBtn = document.getElementById('pause-btn');
                if (pauseBtn) {
                    pauseBtn.textContent = this.isPaused ? 'Resume' : 'Pause';
                }
            }
        } catch (error) {
            console.error('Pause/resume error:', error);
        }
    },

    /**
     * Cancel the current job.
     */
    cancelJob() {
        if (this.eventSource) {
            this.eventSource.close();
        }
        // Redirect back
        window.location.reload();
    },

    /**
     * Show the approval section after processing completes.
     */
    async showApprovalSection() {
        document.getElementById('progress-section').style.display = 'none';
        document.getElementById('approval-section').style.display = 'block';

        try {
            // Load job details
            const response = await fetch(
                `/api/institutions/${this.institutionId}/bulk-remediation/jobs/${this.currentJobId}`
            );

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const job = await response.json();
            const list = document.getElementById('approval-list');

            if (!list || !job.items) return;

            const completedItems = job.items.filter(i => i.status === 'complete');

            if (completedItems.length === 0) {
                list.innerHTML = '<div class="no-items">No completed remediations to approve.</div>';
                return;
            }

            list.innerHTML = completedItems.map(item => `
                <div class="approval-item" data-id="${item.id}">
                    <input type="checkbox" class="approval-checkbox" checked>
                    <div class="item-info">
                        <span class="item-name">${this.escapeHtml(item.document_name)}</span>
                        <span class="item-detail">${item.changes_count} changes | confidence: ${(item.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <div class="item-actions">
                        <button class="btn btn-sm btn-secondary" onclick="BulkRemediation.viewDiff('${item.id}')">View Diff</button>
                        <button class="btn btn-sm btn-success" onclick="BulkRemediation.approveItem('${item.id}')">Approve</button>
                        <button class="btn btn-sm btn-danger" onclick="BulkRemediation.rejectItem('${item.id}')">Reject</button>
                    </div>
                </div>
            `).join('');

        } catch (error) {
            console.error('Load approval section error:', error);
        }
    },

    /**
     * Approve a single item.
     * @param {string} itemId - Item ID
     */
    async approveItem(itemId) {
        try {
            const response = await fetch(
                `/api/institutions/${this.institutionId}/bulk-remediation/items/${itemId}/approve`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ approved_by: 'user' })
                }
            );

            if (response.ok) {
                const item = document.querySelector(`[data-id="${itemId}"]`);
                if (item) {
                    item.classList.add('approved');
                    const approveBtn = item.querySelector('.btn-success');
                    if (approveBtn) approveBtn.disabled = true;
                }
                this.showToast('Item approved', 'success');
            }
        } catch (error) {
            console.error('Approve error:', error);
            this.showToast('Failed to approve item', 'error');
        }
    },

    /**
     * Reject a single item.
     * @param {string} itemId - Item ID
     */
    async rejectItem(itemId) {
        try {
            const response = await fetch(
                `/api/institutions/${this.institutionId}/bulk-remediation/items/${itemId}/reject`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ approved_by: 'user' })
                }
            );

            if (response.ok) {
                const item = document.querySelector(`[data-id="${itemId}"]`);
                if (item) {
                    item.classList.add('rejected');
                    const rejectBtn = item.querySelector('.btn-danger');
                    if (rejectBtn) rejectBtn.disabled = true;
                }
                this.showToast('Item rejected', 'warning');
            }
        } catch (error) {
            console.error('Reject error:', error);
            this.showToast('Failed to reject item', 'error');
        }
    },

    /**
     * Approve all pending items.
     */
    async approveAll() {
        if (!this.currentJobId) return;

        try {
            const response = await fetch(
                `/api/institutions/${this.institutionId}/bulk-remediation/jobs/${this.currentJobId}/approve-all`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ approved_by: 'user' })
                }
            );

            if (response.ok) {
                const data = await response.json();
                // Update UI
                document.querySelectorAll('.approval-item').forEach(item => {
                    item.classList.add('approved');
                });
                this.showToast(`${data.approved_count} remediations approved! Finals have been created.`, 'success');
            }
        } catch (error) {
            console.error('Approve all error:', error);
            this.showToast('Failed to approve all items', 'error');
        }
    },

    /**
     * Reject all pending items.
     */
    async rejectAll() {
        if (!confirm('Are you sure you want to reject all remediations? This cannot be undone.')) {
            return;
        }

        // Mark all as rejected in UI
        document.querySelectorAll('.approval-item').forEach(item => {
            item.classList.add('rejected');
        });

        this.showToast('All remediations rejected', 'warning');
    },

    /**
     * Open diff viewer for an item.
     * @param {string} itemId - Item ID
     */
    viewDiff(itemId) {
        // Open diff viewer modal or navigate to document workbench
        window.open(`/institutions/${this.institutionId}/workbench?item=${itemId}`, '_blank');
    },

    /**
     * Escape HTML to prevent XSS.
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * Show a toast notification.
     * @param {string} message - Message to show
     * @param {string} type - Toast type (success, error, warning)
     */
    showToast(message, type = 'info') {
        if (typeof AccreditAI !== 'undefined' && AccreditAI.toast) {
            AccreditAI.toast.show(message, type);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }
};

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BulkRemediation;
}
