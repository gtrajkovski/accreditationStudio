/**
 * Workbench IDE - Three-panel document editor with inline findings
 */

(function() {
    'use strict';

    // State
    let documents = [];
    let currentDocument = null;
    let currentFindings = [];
    let currentPage = 1;
    let totalPages = 1;
    let currentViewMode = 'original';
    let currentFindingId = null;
    let pendingFixPreview = null;

    // DOM Elements
    const documentList = document.getElementById('documentList');
    const documentViewer = document.getElementById('documentViewer');
    const findingsList = document.getElementById('findingsList');
    const docTitle = document.getElementById('docTitle');
    const docCount = document.getElementById('docCount');
    const findingCount = document.getElementById('findingCount');
    const pageNav = document.getElementById('pageNav');
    const currentPageEl = document.getElementById('currentPage');
    const totalPagesEl = document.getElementById('totalPages');
    const prevPageBtn = document.getElementById('prevPage');
    const nextPageBtn = document.getElementById('nextPage');
    const severityFilter = document.getElementById('severityFilter');
    const docSearch = document.getElementById('docSearch');
    const fixPreviewModal = document.getElementById('fixPreviewModal');

    // Initialize
    document.addEventListener('DOMContentLoaded', init);

    function init() {
        loadDocuments();
        setupEventListeners();
        setupPanelResize();
    }

    function setupEventListeners() {
        // View mode toggle
        document.querySelectorAll('.view-toggle-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.view-toggle-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentViewMode = btn.dataset.mode;
                if (currentDocument) {
                    renderDocument();
                }
            });
        });

        // Pagination
        prevPageBtn.addEventListener('click', () => navigatePage(-1));
        nextPageBtn.addEventListener('click', () => navigatePage(1));

        // Filters
        severityFilter.addEventListener('change', loadDocuments);

        // Search
        let searchTimeout;
        docSearch.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(filterDocuments, 300);
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', handleKeyboard);
    }

    function handleKeyboard(e) {
        // Escape to close modal
        if (e.key === 'Escape' && fixPreviewModal.style.display !== 'none') {
            closeFixPreview();
        }
        // Arrow keys for page navigation
        if (currentDocument && !e.target.matches('input, textarea')) {
            if (e.key === 'ArrowLeft') navigatePage(-1);
            if (e.key === 'ArrowRight') navigatePage(1);
        }
    }

    // API Functions
    async function loadDocuments() {
        const severity = severityFilter.value;
        const params = new URLSearchParams();
        if (severity) params.append('severity', severity);

        try {
            const resp = await fetch(`${window.API_BASE}/documents?${params}`);
            const data = await resp.json();
            documents = data.documents || [];
            docCount.textContent = documents.length;
            renderDocumentList();
        } catch (err) {
            console.error('Failed to load documents:', err);
            documentList.innerHTML = '<div class="error-state">Failed to load documents</div>';
        }
    }

    async function loadDocument(docId) {
        documentViewer.innerHTML = '<div class="loading-placeholder"><div class="spinner"></div></div>';

        try {
            const resp = await fetch(`${window.API_BASE}/documents/${docId}/ide-view`);
            currentDocument = await resp.json();
            currentFindings = currentDocument.findings || [];
            currentPage = 1;
            totalPages = currentDocument.total_pages || 1;

            docTitle.textContent = currentDocument.title || 'Document';
            findingCount.textContent = currentFindings.length;

            updatePagination();
            renderDocument();
            renderFindings();

            // Mark selected in list
            document.querySelectorAll('.doc-item').forEach(item => {
                item.classList.toggle('active', item.dataset.id === docId);
            });
        } catch (err) {
            console.error('Failed to load document:', err);
            documentViewer.innerHTML = '<div class="error-state">Failed to load document</div>';
        }
    }

    async function loadDiff(docId) {
        try {
            const resp = await fetch(`${window.API_BASE}/documents/${docId}/diff`);
            return await resp.json();
        } catch (err) {
            console.error('Failed to load diff:', err);
            return null;
        }
    }

    async function previewFix(findingId) {
        currentFindingId = findingId;

        try {
            const resp = await fetch(`${window.API_BASE}/findings/${findingId}/preview-fix`);
            pendingFixPreview = await resp.json();

            document.getElementById('previewOriginal').textContent = pendingFixPreview.original_text || '[Not available]';
            document.getElementById('previewRemediated').textContent = pendingFixPreview.remediated_text || '[Not available]';
            document.getElementById('previewDescription').textContent = pendingFixPreview.change_description || '';

            fixPreviewModal.style.display = 'flex';
        } catch (err) {
            console.error('Failed to preview fix:', err);
            showNotification('Failed to load fix preview', 'error');
        }
    }

    async function applyCurrentFix() {
        if (!currentFindingId) return;

        const applyBtn = document.getElementById('applyFixBtn');
        applyBtn.disabled = true;
        applyBtn.innerHTML = '<div class="spinner spinner-sm"></div> Applying...';

        try {
            const resp = await fetch(`${window.API_BASE}/findings/${currentFindingId}/apply-fix`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });

            const result = await resp.json();

            if (result.success) {
                closeFixPreview();
                showNotification('Fix applied successfully', 'success');
                // Reload document to show changes
                if (currentDocument) {
                    loadDocument(currentDocument.document_id);
                }
            } else {
                showNotification(result.error || 'Failed to apply fix', 'error');
            }
        } catch (err) {
            console.error('Failed to apply fix:', err);
            showNotification('Failed to apply fix', 'error');
        } finally {
            applyBtn.disabled = false;
            applyBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg> Apply Fix';
        }
    }

    // Rendering Functions
    function renderDocumentList() {
        if (documents.length === 0) {
            documentList.innerHTML = '<div class="empty-state"><p>No documents with findings</p></div>';
            return;
        }

        documentList.innerHTML = documents.map(doc => `
            <div class="doc-item" data-id="${doc.id}" onclick="window.selectDocument('${doc.id}')">
                <div class="doc-item-header">
                    <span class="doc-item-title">${escapeHtml(doc.title)}</span>
                    <span class="doc-item-type">${doc.doc_type || 'document'}</span>
                </div>
                <div class="doc-item-stats">
                    ${doc.critical_count > 0 ? `<span class="severity-badge severity-critical">${doc.critical_count}</span>` : ''}
                    ${doc.significant_count > 0 ? `<span class="severity-badge severity-significant">${doc.significant_count}</span>` : ''}
                    ${doc.minor_count > 0 ? `<span class="severity-badge severity-minor">${doc.minor_count}</span>` : ''}
                    <span class="finding-total">${doc.finding_count} findings</span>
                </div>
            </div>
        `).join('');
    }

    function filterDocuments() {
        const query = docSearch.value.toLowerCase();
        document.querySelectorAll('.doc-item').forEach(item => {
            const title = item.querySelector('.doc-item-title').textContent.toLowerCase();
            item.style.display = title.includes(query) ? '' : 'none';
        });
    }

    function renderDocument() {
        if (!currentDocument || !currentDocument.pages) {
            documentViewer.innerHTML = '<div class="empty-state"><p>No content available</p></div>';
            return;
        }

        if (currentViewMode === 'diff') {
            renderDiffView();
            return;
        }

        const page = currentDocument.pages[currentPage - 1];
        if (!page) {
            documentViewer.innerHTML = '<div class="empty-state"><p>Page not found</p></div>';
            return;
        }

        const pageFindings = currentFindings.filter(f => f.page === currentPage);
        let content = escapeHtml(page.text || '');

        // Apply highlights for findings
        if (pageFindings.length > 0 && currentViewMode === 'original') {
            content = applyHighlights(content, pageFindings);
        }

        documentViewer.innerHTML = `
            <div class="document-page" data-page="${currentPage}">
                <pre class="document-content">${content}</pre>
            </div>
        `;

        // Add click handlers for highlights
        documentViewer.querySelectorAll('.finding-highlight').forEach(el => {
            el.addEventListener('click', () => {
                const findingId = el.dataset.findingId;
                scrollToFinding(findingId);
            });
        });
    }

    async function renderDiffView() {
        if (!currentDocument) return;

        documentViewer.innerHTML = '<div class="loading-placeholder"><div class="spinner"></div></div>';

        const diff = await loadDiff(currentDocument.document_id);
        if (!diff || diff.error) {
            documentViewer.innerHTML = '<div class="empty-state"><p>Could not load diff</p></div>';
            return;
        }

        if (diff.changes_count === 0) {
            documentViewer.innerHTML = '<div class="empty-state"><p>No changes have been applied yet</p></div>';
            return;
        }

        // Render side-by-side diff
        const maxLines = Math.max(diff.original_lines.length, diff.remediated_lines.length);
        let diffHtml = '<div class="diff-container"><div class="diff-side diff-original"><div class="diff-header">Original</div>';

        for (let i = 0; i < maxLines; i++) {
            const origLine = diff.original_lines[i] || '';
            const remLine = diff.remediated_lines[i] || '';
            const isDiff = origLine !== remLine;

            diffHtml += `<div class="diff-line ${isDiff ? 'diff-removed' : ''}">
                <span class="line-number">${i + 1}</span>
                <span class="line-content">${escapeHtml(origLine)}</span>
            </div>`;
        }

        diffHtml += '</div><div class="diff-side diff-remediated"><div class="diff-header">Remediated</div>';

        for (let i = 0; i < maxLines; i++) {
            const origLine = diff.original_lines[i] || '';
            const remLine = diff.remediated_lines[i] || '';
            const isDiff = origLine !== remLine;

            diffHtml += `<div class="diff-line ${isDiff ? 'diff-added' : ''}">
                <span class="line-number">${i + 1}</span>
                <span class="line-content">${escapeHtml(remLine)}</span>
            </div>`;
        }

        diffHtml += '</div></div>';
        documentViewer.innerHTML = diffHtml;
    }

    function applyHighlights(content, findings) {
        // Sort findings by position (descending) to apply from end to start
        const sortedFindings = [...findings]
            .filter(f => f.start_char >= 0 && f.end_char > f.start_char)
            .sort((a, b) => b.start_char - a.start_char);

        for (const finding of sortedFindings) {
            const before = content.substring(0, finding.start_char);
            const highlighted = content.substring(finding.start_char, finding.end_char);
            const after = content.substring(finding.end_char);

            content = before +
                `<span class="finding-highlight severity-${finding.severity}" data-finding-id="${finding.finding_id}" title="${escapeHtml(finding.summary)}">${highlighted}</span>` +
                after;
        }

        return content;
    }

    function renderFindings() {
        if (currentFindings.length === 0) {
            findingsList.innerHTML = '<div class="empty-state"><p>No findings</p></div>';
            return;
        }

        findingsList.innerHTML = currentFindings.map(finding => `
            <div class="finding-item" data-id="${finding.finding_id}" data-page="${finding.page}">
                <div class="finding-header">
                    <span class="severity-badge severity-${finding.severity}">${finding.severity}</span>
                    <span class="finding-page">Page ${finding.page}</span>
                </div>
                <div class="finding-summary">${escapeHtml(finding.summary)}</div>
                ${finding.standard_code ? `<div class="finding-standard">${escapeHtml(finding.standard_code)}</div>` : ''}
                <div class="finding-actions">
                    <button class="btn btn-sm btn-secondary" onclick="window.goToFinding('${finding.finding_id}')">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px">
                            <circle cx="11" cy="11" r="8"/>
                            <path d="M21 21l-4.35-4.35"/>
                        </svg>
                        View
                    </button>
                    <button class="btn btn-sm btn-primary" onclick="window.showFixPreview('${finding.finding_id}')" ${finding.has_remediation ? 'title="Edit applied fix"' : ''}>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px">
                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                        ${finding.has_remediation ? 'Edit' : 'Fix'}
                    </button>
                </div>
            </div>
        `).join('');
    }

    // Navigation
    function navigatePage(delta) {
        const newPage = currentPage + delta;
        if (newPage >= 1 && newPage <= totalPages) {
            currentPage = newPage;
            updatePagination();
            renderDocument();
        }
    }

    function updatePagination() {
        if (totalPages > 1) {
            pageNav.style.display = 'flex';
            currentPageEl.textContent = currentPage;
            totalPagesEl.textContent = totalPages;
            prevPageBtn.disabled = currentPage <= 1;
            nextPageBtn.disabled = currentPage >= totalPages;
        } else {
            pageNav.style.display = 'none';
        }
    }

    function scrollToFinding(findingId) {
        const finding = currentFindings.find(f => f.finding_id === findingId);
        if (!finding) return;

        // Navigate to page if needed
        if (finding.page !== currentPage) {
            currentPage = finding.page;
            updatePagination();
            renderDocument();
        }

        // Highlight finding in list
        document.querySelectorAll('.finding-item').forEach(item => {
            item.classList.toggle('highlighted', item.dataset.id === findingId);
        });

        // Scroll to highlight in viewer
        setTimeout(() => {
            const highlight = documentViewer.querySelector(`[data-finding-id="${findingId}"]`);
            if (highlight) {
                highlight.scrollIntoView({ behavior: 'smooth', block: 'center' });
                highlight.classList.add('pulse');
                setTimeout(() => highlight.classList.remove('pulse'), 1000);
            }
        }, 100);
    }

    // Panel Resize
    function setupPanelResize() {
        const container = document.getElementById('ideContainer');
        const handles = document.querySelectorAll('.panel-resize-handle');

        handles.forEach(handle => {
            let startX, startWidth, panel;

            handle.addEventListener('mousedown', (e) => {
                e.preventDefault();
                startX = e.clientX;
                panel = handle.parentElement;
                startWidth = panel.offsetWidth;

                document.addEventListener('mousemove', resize);
                document.addEventListener('mouseup', stopResize);
                document.body.style.cursor = 'col-resize';
                document.body.style.userSelect = 'none';
            });

            function resize(e) {
                const delta = handle.dataset.resize === 'left' ? e.clientX - startX : startX - e.clientX;
                const newWidth = Math.max(200, Math.min(500, startWidth + delta));
                panel.style.width = newWidth + 'px';
                panel.style.flex = 'none';
            }

            function stopResize() {
                document.removeEventListener('mousemove', resize);
                document.removeEventListener('mouseup', stopResize);
                document.body.style.cursor = '';
                document.body.style.userSelect = '';
            }
        });
    }

    // Utilities
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function showNotification(message, type = 'info') {
        // Use existing notification system if available
        if (window.showToast) {
            window.showToast(message, type);
        } else {
            console.log(`[${type}] ${message}`);
        }
    }

    function closeFixPreview() {
        fixPreviewModal.style.display = 'none';
        currentFindingId = null;
        pendingFixPreview = null;
    }

    // Global exports
    window.selectDocument = loadDocument;
    window.goToFinding = scrollToFinding;
    window.showFixPreview = previewFix;
    window.applyCurrentFix = applyCurrentFix;
    window.closeFixPreview = closeFixPreview;

})();
