/**
 * Standards Harvester UI Controller
 * Handles fetching standards from web, PDF, or manual entry
 * and displaying version history with diff viewer.
 */
class HarvesterManager {
    constructor() {
        this.currentAccreditor = 'ACCSC';
        this.currentTab = 'web_scrape';
        this.versions = [];
    }

    init() {
        // Bind accreditor change
        const accreditorSelect = document.getElementById('accreditor-select');
        if (accreditorSelect) {
            accreditorSelect.addEventListener('change', (e) => {
                this.currentAccreditor = e.target.value;
                this.loadVersions();
            });
        }

        // Bind tab switches
        document.querySelectorAll('.source-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                this.switchTab(e.currentTarget.dataset.tab);
            });
        });

        // Bind action buttons
        const fetchWebBtn = document.getElementById('fetch-web-btn');
        if (fetchWebBtn) {
            fetchWebBtn.addEventListener('click', () => this.fetchWebScrape());
        }

        const uploadPdfBtn = document.getElementById('upload-pdf-btn');
        if (uploadPdfBtn) {
            uploadPdfBtn.addEventListener('click', () => this.uploadPdf());
        }

        const submitManualBtn = document.getElementById('submit-manual-btn');
        if (submitManualBtn) {
            submitManualBtn.addEventListener('click', () => this.submitManual());
        }

        // Load initial versions
        this.loadVersions();
    }

    switchTab(tab) {
        this.currentTab = tab;

        // Update tab active state
        document.querySelectorAll('.source-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.tab === tab);
        });

        // Update panel visibility
        document.querySelectorAll('.source-panel').forEach(panel => {
            const panelTab = panel.id.replace('panel-', '');
            panel.classList.toggle('active', panelTab === tab);
        });
    }

    async fetchWebScrape() {
        const urlInput = document.getElementById('source-url');
        const url = urlInput?.value?.trim();

        if (!url) {
            this.showResult('Please enter a URL', 'error');
            return;
        }

        this.showLoading('Fetching standards (this may take up to 15 seconds)...');

        try {
            const response = await fetch('/api/standards-harvester/fetch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    accreditor_code: this.currentAccreditor,
                    source_type: 'web_scrape',
                    url: url
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to fetch standards');
            }

            this.hideLoading();
            this.handleFetchSuccess(data);
            urlInput.value = '';
        } catch (error) {
            this.hideLoading();
            this.showResult(error.message, 'error');
        }
    }

    async uploadPdf() {
        const fileInput = document.getElementById('pdf-file');
        const file = fileInput?.files?.[0];

        if (!file) {
            this.showResult('Please select a PDF file', 'error');
            return;
        }

        this.showLoading('Uploading and parsing PDF...');

        try {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('accreditor_code', this.currentAccreditor);

            const response = await fetch('/api/standards-harvester/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to upload PDF');
            }

            this.hideLoading();
            this.handleFetchSuccess(data);
            fileInput.value = '';
        } catch (error) {
            this.hideLoading();
            this.showResult(error.message, 'error');
        }
    }

    async submitManual() {
        const textInput = document.getElementById('manual-text');
        const dateInput = document.getElementById('manual-version-date');
        const text = textInput?.value?.trim();

        if (!text) {
            this.showResult('Please enter standards text', 'error');
            return;
        }

        this.showLoading('Saving standards...');

        try {
            const body = {
                accreditor_code: this.currentAccreditor,
                source_type: 'manual_upload',
                text: text
            };

            if (dateInput?.value) {
                body.version_date = dateInput.value;
            }

            const response = await fetch('/api/standards-harvester/fetch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to save standards');
            }

            this.hideLoading();
            this.handleFetchSuccess(data);
            textInput.value = '';
            if (dateInput) dateInput.value = '';
        } catch (error) {
            this.hideLoading();
            this.showResult(error.message, 'error');
        }
    }

    handleFetchSuccess(data) {
        const { version, change_detected } = data;

        if (version.is_new) {
            this.showResult(AccreditAI.i18n.t('harvester.first_version'), 'success');
        } else if (change_detected) {
            this.showResult(AccreditAI.i18n.t('harvester.changes_detected'), 'success');
        } else {
            this.showResult(AccreditAI.i18n.t('harvester.no_changes'), 'info');
        }

        this.loadVersions();
    }

    async loadVersions() {
        const loading = document.getElementById('versions-loading');
        const empty = document.getElementById('versions-empty');
        const table = document.getElementById('versions-table');

        loading.style.display = 'flex';
        empty.style.display = 'none';
        table.style.display = 'none';

        try {
            const response = await fetch(`/api/standards-harvester/versions/${this.currentAccreditor}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to load versions');
            }

            this.versions = data.versions || [];
            loading.style.display = 'none';

            if (this.versions.length === 0) {
                empty.style.display = 'flex';
            } else {
                table.style.display = 'table';
                this.renderVersionTable(this.versions);
            }
        } catch (error) {
            loading.style.display = 'none';
            console.error('Failed to load versions:', error);
            this.showResult(error.message, 'error');
        }
    }

    renderVersionTable(versions) {
        const tbody = document.getElementById('versions-tbody');
        if (!tbody) return;

        tbody.innerHTML = versions.map((v, index) => {
            const date = this.formatDate(v.version_date);
            const hash = v.content_hash?.substring(0, 8) || '-';
            const sourceType = v.source_type || 'unknown';
            const sourceLabel = this.getSourceLabel(sourceType);
            const isFirst = index === versions.length - 1;

            return `
                <tr data-version-id="${v.id}">
                    <td>${date}</td>
                    <td><span class="source-badge ${sourceType}">${sourceLabel}</span></td>
                    <td><code class="hash-display">${hash}...</code></td>
                    <td>
                        <button
                            class="btn btn-sm btn-ghost"
                            onclick="window.harvesterManager.showDiff('${v.id}')"
                            ${isFirst ? 'disabled title="First version - no previous to compare"' : ''}
                        >
                            ${AccreditAI.i18n.t('harvester.view_diff')}
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    getSourceLabel(sourceType) {
        const labels = {
            'web_scrape': AccreditAI.i18n.t('harvester.web_scrape'),
            'pdf_parse': AccreditAI.i18n.t('harvester.pdf_parse'),
            'manual_upload': AccreditAI.i18n.t('harvester.manual_upload')
        };
        return labels[sourceType] || sourceType;
    }

    formatDate(dateStr) {
        if (!dateStr) return '-';
        try {
            const date = new Date(dateStr);
            return date.toLocaleDateString(undefined, {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return dateStr;
        }
    }

    async showDiff(versionId) {
        const modal = document.getElementById('diff-modal');
        const container = document.getElementById('diff-container');
        const oldDateEl = document.getElementById('diff-old-date');
        const newDateEl = document.getElementById('diff-new-date');

        // Show modal with loading state
        container.innerHTML = '<div class="diff-loading">' + AccreditAI.i18n.t('common.loading') + '</div>';
        oldDateEl.textContent = '-';
        newDateEl.textContent = '-';
        this.showDiffModal();

        try {
            const response = await fetch(`/api/standards-harvester/diff/${versionId}`);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to load diff');
            }

            // Update metadata
            if (data.old_version) {
                oldDateEl.textContent = this.formatDate(data.old_version.version_date);
            } else {
                oldDateEl.textContent = '-';
            }
            newDateEl.textContent = this.formatDate(data.new_version.version_date);

            // Insert diff HTML
            container.innerHTML = data.diff_html;
        } catch (error) {
            container.innerHTML = `<div class="diff-info" style="color: var(--danger);">${error.message}</div>`;
        }
    }

    showDiffModal() {
        const modal = document.getElementById('diff-modal');
        if (modal) {
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    }

    hideDiffModal() {
        const modal = document.getElementById('diff-modal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    showLoading(message = 'Loading...') {
        const overlay = document.getElementById('harvester-loading');
        const msgEl = document.getElementById('loading-message');
        if (overlay) {
            overlay.style.display = 'flex';
            if (msgEl) msgEl.textContent = message;
            document.body.style.overflow = 'hidden';
        }
    }

    hideLoading() {
        const overlay = document.getElementById('harvester-loading');
        if (overlay) {
            overlay.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    showResult(message, type = 'info') {
        const banner = document.getElementById('result-banner');
        const msgEl = document.getElementById('result-message');

        if (banner && msgEl) {
            banner.className = 'result-banner ' + type;
            msgEl.textContent = message;
            banner.style.display = 'flex';

            // Auto-hide after 5 seconds
            setTimeout(() => {
                banner.style.display = 'none';
            }, 5000);
        }
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.harvesterManager = new HarvesterManager();
    window.harvesterManager.init();
});

// Close modal on Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && window.harvesterManager) {
        window.harvesterManager.hideDiffModal();
    }
});
