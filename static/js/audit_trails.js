/**
 * Audit Trails Manager
 *
 * Handles session filtering, display, and export functionality.
 */
class AuditTrailManager {
    constructor() {
        this.institutionId = window.institutionId;
        this.sessions = [];
        this.filters = {
            start_date: null,
            end_date: null,
            agent_type: null
        };

        this.init();
    }

    async init() {
        this.bindElements();
        this.setupEventListeners();
        await this.loadAgentTypes();
        await this.loadSessions();
        await this.loadReports();
    }

    bindElements() {
        // Filters
        this.startDateInput = document.getElementById('start-date');
        this.endDateInput = document.getElementById('end-date');
        this.agentTypeSelect = document.getElementById('agent-type');
        this.applyFiltersBtn = document.getElementById('apply-filters');
        this.clearFiltersBtn = document.getElementById('clear-filters');

        // Export
        this.exportFormatRadios = document.querySelectorAll('input[name="export-format"]');
        this.includeReportGroup = document.getElementById('include-report-group');
        this.includeReportCheckbox = document.getElementById('include-report');
        this.reportSelect = document.getElementById('report-select');
        this.exportBtn = document.getElementById('export-btn');
        this.sessionCountEl = document.getElementById('session-count');

        // Sessions
        this.sessionsListEl = document.getElementById('sessions-list');
        this.emptyStateEl = document.getElementById('empty-state');
        this.loadingStateEl = document.getElementById('loading-state');

        // Modal
        this.modal = document.getElementById('session-modal');
        this.modalContent = document.getElementById('session-detail-content');
        this.modalClose = this.modal.querySelector('.modal-close');
        this.modalBackdrop = this.modal.querySelector('.modal-backdrop');
    }

    setupEventListeners() {
        // Filters
        this.applyFiltersBtn.addEventListener('click', () => this.applyFilters());
        this.clearFiltersBtn.addEventListener('click', () => this.clearFilters());

        // Export format toggle
        this.exportFormatRadios.forEach(radio => {
            radio.addEventListener('change', (e) => this.onFormatChange(e));
        });

        // Include report checkbox
        this.includeReportCheckbox.addEventListener('change', () => {
            this.reportSelect.disabled = !this.includeReportCheckbox.checked;
        });

        // Export button
        this.exportBtn.addEventListener('click', () => this.exportAuditTrail());

        // Modal close
        this.modalClose.addEventListener('click', () => this.closeModal());
        this.modalBackdrop.addEventListener('click', () => this.closeModal());

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.style.display !== 'none') {
                this.closeModal();
            }
        });
    }

    async loadAgentTypes() {
        try {
            const response = await fetch(
                `/api/audit-trails/institutions/${this.institutionId}/agent-types`
            );
            const data = await response.json();

            if (data.success) {
                data.agent_types.forEach(type => {
                    const option = document.createElement('option');
                    option.value = type;
                    option.textContent = this.formatAgentType(type);
                    this.agentTypeSelect.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Failed to load agent types:', error);
        }
    }

    async loadReports() {
        try {
            const response = await fetch(
                `/api/reports/institutions/${this.institutionId}?limit=20`
            );
            const data = await response.json();

            if (data.success) {
                data.reports.forEach(report => {
                    const option = document.createElement('option');
                    option.value = report.file_path;
                    option.textContent = `${report.title} (${this.formatDate(report.generated_at)})`;
                    this.reportSelect.appendChild(option);
                });
            }
        } catch (error) {
            console.error('Failed to load reports:', error);
        }
    }

    async loadSessions() {
        this.showLoading(true);

        try {
            const params = new URLSearchParams();
            if (this.filters.start_date) {
                params.append('start_date', new Date(this.filters.start_date).toISOString());
            }
            if (this.filters.end_date) {
                params.append('end_date', new Date(this.filters.end_date).toISOString());
            }
            if (this.filters.agent_type) {
                params.append('agent_type', this.filters.agent_type);
            }

            const response = await fetch(
                `/api/audit-trails/institutions/${this.institutionId}/sessions?${params}`
            );
            const data = await response.json();

            if (data.success) {
                this.sessions = data.sessions;
                this.renderSessions();
                this.updateSessionCount();
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
        } finally {
            this.showLoading(false);
        }
    }

    renderSessions() {
        if (this.sessions.length === 0) {
            this.sessionsListEl.innerHTML = '';
            this.emptyStateEl.style.display = 'block';
            return;
        }

        this.emptyStateEl.style.display = 'none';
        this.sessionsListEl.innerHTML = this.sessions.map(session => `
            <div class="session-card" data-session-id="${session.id}">
                <div class="session-header">
                    <span class="session-id">${session.id}</span>
                    <span class="session-status status-${session.status}">${session.status}</span>
                </div>
                <div class="session-meta">
                    <span class="agent-type">${this.formatAgentType(session.agent_type)}</span>
                    <span class="session-date">${this.formatDate(session.created_at)}</span>
                </div>
                <div class="session-stats">
                    <span class="tool-count">${(session.tool_calls || []).length} tool calls</span>
                    ${session.total_tokens ? `<span class="token-count">${session.total_tokens} tokens</span>` : ''}
                </div>
                <button class="btn btn-sm btn-secondary view-details-btn">View Details</button>
            </div>
        `).join('');

        // Bind click handlers
        this.sessionsListEl.querySelectorAll('.view-details-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const sessionId = e.target.closest('.session-card').dataset.sessionId;
                this.showSessionDetails(sessionId);
            });
        });
    }

    async showSessionDetails(sessionId) {
        try {
            const response = await fetch(
                `/api/audit-trails/institutions/${this.institutionId}/sessions/${sessionId}`
            );
            const data = await response.json();

            if (data.success) {
                this.modalContent.innerHTML = this.renderSessionDetail(data.session);
                this.modal.style.display = 'flex';
            }
        } catch (error) {
            console.error('Failed to load session details:', error);
        }
    }

    renderSessionDetail(session) {
        const toolCallsHtml = (session.tool_calls || []).map((tc, i) => `
            <div class="tool-call">
                <span class="tool-index">#${i + 1}</span>
                <span class="tool-name">${tc.name}</span>
                <pre class="tool-input">${JSON.stringify(tc.input, null, 2)}</pre>
            </div>
        `).join('');

        return `
            <div class="session-detail">
                <div class="detail-row">
                    <label>Session ID:</label>
                    <span>${session.id}</span>
                </div>
                <div class="detail-row">
                    <label>Agent Type:</label>
                    <span>${this.formatAgentType(session.agent_type)}</span>
                </div>
                <div class="detail-row">
                    <label>Status:</label>
                    <span class="status-${session.status}">${session.status}</span>
                </div>
                <div class="detail-row">
                    <label>Created:</label>
                    <span>${this.formatDate(session.created_at)}</span>
                </div>
                ${session.completed_at ? `
                <div class="detail-row">
                    <label>Completed:</label>
                    <span>${this.formatDate(session.completed_at)}</span>
                </div>
                ` : ''}
                ${session.metadata?.confidence ? `
                <div class="detail-row">
                    <label>Confidence:</label>
                    <span>${(session.metadata.confidence * 100).toFixed(0)}%</span>
                </div>
                ` : ''}
                <div class="detail-section">
                    <h3>Tool Calls (${(session.tool_calls || []).length})</h3>
                    <div class="tool-calls-list">
                        ${toolCallsHtml || '<p>No tool calls recorded.</p>'}
                    </div>
                </div>
            </div>
        `;
    }

    closeModal() {
        this.modal.style.display = 'none';
    }

    applyFilters() {
        this.filters.start_date = this.startDateInput.value || null;
        this.filters.end_date = this.endDateInput.value || null;
        this.filters.agent_type = this.agentTypeSelect.value || null;
        this.loadSessions();
    }

    clearFilters() {
        this.startDateInput.value = '';
        this.endDateInput.value = '';
        this.agentTypeSelect.value = '';
        this.filters = { start_date: null, end_date: null, agent_type: null };
        this.loadSessions();
    }

    onFormatChange(e) {
        const format = e.target.value;
        this.includeReportGroup.style.display = format === 'zip' ? 'block' : 'none';
    }

    async exportAuditTrail() {
        const format = document.querySelector('input[name="export-format"]:checked').value;
        const includeReport = format === 'zip' && this.includeReportCheckbox.checked;
        const reportPath = includeReport ? this.reportSelect.value : null;

        const payload = {
            format,
            start_date: this.filters.start_date ? new Date(this.filters.start_date).toISOString() : null,
            end_date: this.filters.end_date ? new Date(this.filters.end_date).toISOString() : null,
            agent_type: this.filters.agent_type,
            include_report: includeReport,
            report_path: reportPath
        };

        try {
            const response = await fetch(
                `/api/audit-trails/institutions/${this.institutionId}/export`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                }
            );

            if (!response.ok) {
                throw new Error('Export failed');
            }

            // Trigger download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            // Get filename from Content-Disposition header
            const disposition = response.headers.get('Content-Disposition');
            const filenameMatch = disposition && disposition.match(/filename="?(.+)"?/);
            a.download = filenameMatch ? filenameMatch[1] : `audit_trail.${format}`;

            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

        } catch (error) {
            console.error('Export failed:', error);
            alert('Failed to export audit trail. Please try again.');
        }
    }

    updateSessionCount() {
        this.sessionCountEl.textContent = `${this.sessions.length} session(s) found`;
    }

    showLoading(show) {
        this.loadingStateEl.style.display = show ? 'flex' : 'none';
        if (show) {
            this.sessionsListEl.innerHTML = '';
            this.emptyStateEl.style.display = 'none';
        }
    }

    formatAgentType(type) {
        if (!type) return 'Unknown';
        return type.split('_').map(word =>
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    }

    formatDate(isoString) {
        if (!isoString) return 'N/A';
        return new Date(isoString).toLocaleString();
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    new AuditTrailManager();
});
