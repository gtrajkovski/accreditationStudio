/**
 * Standards Importer JavaScript
 *
 * Handles:
 * - File upload via drag-drop and file picker
 * - API communication for parsing and import
 * - SSE streaming for AI-enhanced parsing
 * - Tab navigation and state management
 * - Mapping adjustments
 * - History display
 */

document.addEventListener('DOMContentLoaded', function() {
    // State
    let currentState = {
        uploadedFile: null,
        filePath: null,
        parseResult: null,
        sections: [],
        checklistItems: [],
        userMappings: { sections: {}, items: {} },
    };

    // Elements
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const rawText = document.getElementById('rawText');
    const parseBtn = document.getElementById('parseBtn');
    const progressSection = document.getElementById('progressSection');
    const progressFill = document.getElementById('progressFill');
    const progressMessage = document.getElementById('progressMessage');

    // Tab Navigation
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tabId = btn.dataset.tab;
            switchTab(tabId);
        });
    });

    function switchTab(tabId) {
        tabBtns.forEach(b => b.classList.remove('active'));
        tabContents.forEach(c => c.classList.remove('active'));

        document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
        document.getElementById(`tab-${tabId}`).classList.add('active');

        if (tabId === 'history') {
            loadHistory();
        }
    }

    // File Drop Zone
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) handleFile(file);
    });

    function handleFile(file) {
        currentState.uploadedFile = file;
        dropZone.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="drop-icon file-icon">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
            </svg>
            <p>${escapeHtml(file.name)}</p>
            <span class="file-size">${formatBytes(file.size)}</span>
        `;

        // Auto-fill name from filename
        const nameInput = document.getElementById('libraryName');
        if (!nameInput.value) {
            nameInput.value = file.name.replace(/\.[^/.]+$/, '');
        }
    }

    // Parse Button
    parseBtn.addEventListener('click', async () => {
        const useAI = document.getElementById('useAI').checked;
        const accreditor = document.getElementById('accreditorSelect').value;
        const name = document.getElementById('libraryName').value;
        const version = document.getElementById('versionInput').value;

        // Validate input
        if (!currentState.uploadedFile && !rawText.value.trim()) {
            showToast('Please upload a file or paste text', 'error');
            return;
        }

        showProgress(true);

        try {
            let filePath;

            // Upload file if needed
            if (currentState.uploadedFile) {
                const uploadResult = await uploadFile(currentState.uploadedFile);
                filePath = uploadResult.file_path;
                currentState.filePath = filePath;
            }

            // Parse
            if (useAI) {
                await parseWithAI(filePath || null, rawText.value, accreditor, name, version);
            } else {
                await parseStandard(filePath || null, rawText.value, accreditor, name, version);
            }

        } catch (error) {
            console.error('Parse error:', error);
            showToast(error.message || 'Parse failed', 'error');
            showProgress(false);
        }
    });

    async function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('accreditor', document.getElementById('accreditorSelect').value);

        const response = await fetch('/api/standards-importer/upload', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Upload failed');
        }

        return response.json();
    }

    async function parseStandard(filePath, text, accreditor, name, version) {
        updateProgress(25, 'Parsing document...');

        const body = filePath
            ? { file_path: filePath, accreditor, name, version }
            : { text, accreditor, name, version };

        const response = await fetch('/api/standards-importer/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Parse failed');
        }

        const result = await response.json();
        handleParseResult(result);
    }

    async function parseWithAI(filePath, text, accreditor, name, version) {
        updateProgress(10, 'Starting AI-enhanced parsing...');

        const body = filePath
            ? { file_path: filePath, accreditor, name, version }
            : { text, accreditor, name, version };

        const response = await fetch('/api/standards-importer/parse-ai', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value);
            const lines = text.split('\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        handleSSEMessage(data);
                    } catch (e) {
                        console.warn('Failed to parse SSE:', line);
                    }
                }
            }
        }
    }

    function handleSSEMessage(data) {
        if (data.type === 'progress') {
            updateProgress(data.percentage, data.message);
        } else if (data.type === 'agent_update') {
            if (data.text) {
                updateProgress(null, data.text.substring(0, 100) + '...');
            }
        } else if (data.type === 'complete') {
            handleParseResult(data.result);
        } else if (data.type === 'error') {
            throw new Error(data.error);
        }
    }

    function handleParseResult(result) {
        currentState.parseResult = result;
        currentState.sections = result.sections || [];
        currentState.checklistItems = result.checklist_items || [];

        showProgress(false);
        populatePreview(result);
        switchTab('preview');
    }

    function populatePreview(result) {
        // Update summary cards
        document.getElementById('sectionsCount').textContent = result.sections_count || 0;
        document.getElementById('itemsCount').textContent = result.items_count || 0;
        document.getElementById('qualityScore').textContent = Math.round(result.quality_score || 0);

        const validationCard = document.getElementById('validationCard');
        const validationStatus = document.getElementById('validationStatus');

        // Reset validation card classes
        validationCard.classList.remove('success', 'error');

        if (result.can_import) {
            validationCard.classList.add('success');
            validationStatus.textContent = 'Valid';
        } else {
            validationCard.classList.add('error');
            validationStatus.textContent = 'Issues Found';
        }

        // Build section tree
        const sectionTree = document.getElementById('sectionTree');
        sectionTree.innerHTML = buildSectionTree(result.sections || []);

        // Build checklist preview
        const checklistPreview = document.getElementById('checklistPreview');
        checklistPreview.innerHTML = buildChecklistPreview(result.checklist_items || []);

        // Show validation issues
        const issuesPanel = document.getElementById('issuesPanel');
        const issuesList = document.getElementById('issuesList');

        if (result.validation && result.validation.issues && result.validation.issues.length > 0) {
            issuesPanel.classList.remove('hidden');
            issuesList.innerHTML = result.validation.issues.map(issue => `
                <div class="issue-item issue-${issue.severity}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="issue-icon">
                        ${issue.severity === 'error'
                            ? '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>'
                            : '<path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'}
                    </svg>
                    <div class="issue-content">
                        <strong>${escapeHtml(issue.location)}</strong>: ${escapeHtml(issue.message)}
                        ${issue.suggestion ? `<div class="issue-suggestion">${escapeHtml(issue.suggestion)}</div>` : ''}
                    </div>
                </div>
            `).join('');
        } else {
            issuesPanel.classList.add('hidden');
        }

        // Enable proceed button if valid
        document.getElementById('proceedToMappingBtn').disabled = !result.can_import;
    }

    function buildSectionTree(sections) {
        if (!sections || sections.length === 0) {
            return '<p class="empty-state">No sections detected</p>';
        }

        // Group by parent
        const byParent = {};
        sections.forEach(s => {
            const parent = s.parent_section || 'root';
            if (!byParent[parent]) byParent[parent] = [];
            byParent[parent].push(s);
        });

        function renderLevel(parentId) {
            const children = byParent[parentId] || [];
            if (children.length === 0) return '';

            return `<ul class="section-list">
                ${children.map(s => `
                    <li class="section-item">
                        <span class="section-number">${escapeHtml(s.number)}</span>
                        <span class="section-title">${escapeHtml(s.title || '(Untitled)')}</span>
                        ${renderLevel(s.id)}
                    </li>
                `).join('')}
            </ul>`;
        }

        return renderLevel('root') || renderLevel('');
    }

    function buildChecklistPreview(items) {
        if (!items || items.length === 0) {
            return '<p class="empty-state">No checklist items detected</p>';
        }

        // Group by category
        const byCategory = {};
        items.forEach(i => {
            const cat = i.category || 'Uncategorized';
            if (!byCategory[cat]) byCategory[cat] = [];
            byCategory[cat].push(i);
        });

        return Object.entries(byCategory).map(([cat, catItems]) => `
            <div class="category-group">
                <h4 class="category-header">${escapeHtml(cat)} (${catItems.length})</h4>
                <ul class="checklist-items">
                    ${catItems.slice(0, 5).map(i => `
                        <li class="checklist-item">
                            <span class="item-number">${escapeHtml(i.number)}</span>
                            <span class="item-desc">${escapeHtml(i.description.substring(0, 100))}${i.description.length > 100 ? '...' : ''}</span>
                        </li>
                    `).join('')}
                    ${catItems.length > 5 ? `<li class="more-items">...and ${catItems.length - 5} more</li>` : ''}
                </ul>
            </div>
        `).join('');
    }

    // Navigation Buttons
    document.getElementById('backToUploadBtn').addEventListener('click', () => switchTab('upload'));
    document.getElementById('proceedToMappingBtn').addEventListener('click', () => {
        populateMappingTables();
        switchTab('mapping');
    });
    document.getElementById('backToPreviewBtn').addEventListener('click', () => switchTab('preview'));

    function populateMappingTables() {
        // Section mapping table
        const sectionTable = document.getElementById('sectionMappingTable').querySelector('tbody');
        sectionTable.innerHTML = currentState.sections.slice(0, 50).map(s => `
            <tr data-id="${s.id}">
                <td><input type="text" value="${escapeHtml(s.number)}" class="mapping-input" data-field="number"></td>
                <td><input type="text" value="${escapeHtml(s.title || '')}" class="mapping-input" data-field="title"></td>
                <td>${escapeHtml(s.parent_section || '-')}</td>
                <td>
                    <button class="btn btn-sm btn-icon" onclick="editSection('${s.id}')">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                </td>
            </tr>
        `).join('');

        // Category mapping table
        const categoryTable = document.getElementById('categoryMappingTable').querySelector('tbody');
        categoryTable.innerHTML = currentState.checklistItems.slice(0, 20).map(i => `
            <tr data-number="${escapeHtml(i.number)}">
                <td>${escapeHtml(i.number)}</td>
                <td><input type="text" value="${escapeHtml(i.category || '')}" class="mapping-input" data-field="category"></td>
                <td>${escapeHtml((i.applies_to || []).join(', '))}</td>
                <td>
                    <button class="btn btn-sm btn-icon" onclick="editItem('${escapeHtml(i.number)}')">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                            <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                    </button>
                </td>
            </tr>
        `).join('');
    }

    // Import Button
    document.getElementById('importBtn').addEventListener('click', async () => {
        // Collect user mappings from tables
        collectMappings();

        const body = {
            import_id: currentState.parseResult?.import_id,
            accreditor: document.getElementById('accreditorSelect').value,
            name: document.getElementById('libraryName').value,
            version: document.getElementById('versionInput').value,
            sections: currentState.sections,
            checklist_items: currentState.checklistItems,
            user_mappings: currentState.userMappings,
        };

        try {
            const response = await fetch('/api/standards-importer/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Import failed');
            }

            const result = await response.json();
            showSuccessModal(result.library);

        } catch (error) {
            console.error('Import error:', error);
            showToast(error.message || 'Import failed', 'error');
        }
    });

    function collectMappings() {
        // Collect section mappings
        document.querySelectorAll('#sectionMappingTable tbody tr').forEach(row => {
            const id = row.dataset.id;
            const numberInput = row.querySelector('[data-field="number"]');
            const titleInput = row.querySelector('[data-field="title"]');

            if (!numberInput || !titleInput) return;

            const number = numberInput.value;
            const title = titleInput.value;

            const section = currentState.sections.find(s => s.id === id);
            if (section) {
                if (section.number !== number) {
                    currentState.userMappings.sections[section.number] = { number };
                    section.number = number;
                }
                if (section.title !== title) {
                    currentState.userMappings.sections[section.number] = {
                        ...currentState.userMappings.sections[section.number],
                        title,
                    };
                    section.title = title;
                }
            }
        });

        // Collect category mappings
        document.querySelectorAll('#categoryMappingTable tbody tr').forEach(row => {
            const number = row.dataset.number;
            const categoryInput = row.querySelector('[data-field="category"]');

            if (!categoryInput) return;

            const category = categoryInput.value;

            const item = currentState.checklistItems.find(i => i.number === number);
            if (item && item.category !== category) {
                currentState.userMappings.items[number] = { category };
                item.category = category;
            }
        });
    }

    function showSuccessModal(library) {
        const modal = document.getElementById('successModal');
        const details = document.getElementById('successDetails');

        details.innerHTML = `
            <p><strong>Name:</strong> ${escapeHtml(library.name)}</p>
            <p><strong>Accreditor:</strong> ${escapeHtml(library.accrediting_body)}</p>
            <p><strong>Sections:</strong> ${library.sections?.length || 0}</p>
            <p><strong>Checklist Items:</strong> ${library.checklist_items?.length || 0}</p>
        `;

        modal.classList.add('show');
    }

    document.getElementById('importAnotherBtn').addEventListener('click', () => {
        document.getElementById('successModal').classList.remove('show');
        resetState();
        switchTab('upload');
    });

    // Modal close handlers
    document.getElementById('closeEditModal').addEventListener('click', () => {
        document.getElementById('editModal').classList.remove('show');
    });

    document.getElementById('cancelEditBtn').addEventListener('click', () => {
        document.getElementById('editModal').classList.remove('show');
    });

    // History
    async function loadHistory() {
        const status = document.getElementById('historyStatusFilter').value;
        const historyEmpty = document.getElementById('historyEmpty');
        const historyTable = document.getElementById('historyTable');

        try {
            const url = `/api/standards-importer/imports${status ? `?status=${status}` : ''}`;
            const response = await fetch(url);
            const imports = await response.json();

            const tbody = historyTable.querySelector('tbody');

            if (imports.length === 0) {
                historyEmpty.style.display = 'flex';
                tbody.innerHTML = '';
                return;
            }

            historyEmpty.style.display = 'none';
            tbody.innerHTML = imports.map(imp => `
                <tr>
                    <td>${formatDate(imp.created_at)}</td>
                    <td>${escapeHtml(imp.source_name || 'N/A')}</td>
                    <td>${escapeHtml(imp.accreditor_code)}</td>
                    <td>${imp.sections_detected}</td>
                    <td>${imp.checklist_items_detected}</td>
                    <td><span class="status-badge status-${imp.status}">${imp.status}</span></td>
                    <td>
                        ${imp.library_id ? `<a href="/standards/${imp.library_id}" class="btn btn-sm">View</a>` : ''}
                        <button class="btn btn-sm btn-danger" onclick="deleteImport('${imp.id}')">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                            </svg>
                        </button>
                    </td>
                </tr>
            `).join('');

        } catch (error) {
            console.error('Failed to load history:', error);
        }
    }

    document.getElementById('refreshHistoryBtn').addEventListener('click', loadHistory);
    document.getElementById('historyStatusFilter').addEventListener('change', loadHistory);

    window.deleteImport = async function(importId) {
        if (!confirm('Delete this import record?')) return;

        try {
            await fetch(`/api/standards-importer/imports/${importId}`, { method: 'DELETE' });
            loadHistory();
            showToast('Import record deleted', 'success');
        } catch (error) {
            console.error('Delete failed:', error);
            showToast('Failed to delete import record', 'error');
        }
    };

    // Global edit functions
    window.editSection = function(sectionId) {
        const section = currentState.sections.find(s => s.id === sectionId);
        if (!section) return;

        const modal = document.getElementById('editModal');
        const title = document.getElementById('editModalTitle');
        const body = document.getElementById('editModalBody');

        title.textContent = 'Edit Section';
        body.innerHTML = `
            <div class="form-group">
                <label>Number</label>
                <input type="text" id="editSectionNumber" value="${escapeHtml(section.number)}">
            </div>
            <div class="form-group">
                <label>Title</label>
                <input type="text" id="editSectionTitle" value="${escapeHtml(section.title || '')}">
            </div>
        `;

        modal.classList.add('show');

        document.getElementById('saveEditBtn').onclick = () => {
            section.number = document.getElementById('editSectionNumber').value;
            section.title = document.getElementById('editSectionTitle').value;
            populateMappingTables();
            modal.classList.remove('show');
        };
    };

    window.editItem = function(itemNumber) {
        const item = currentState.checklistItems.find(i => i.number === itemNumber);
        if (!item) return;

        const modal = document.getElementById('editModal');
        const title = document.getElementById('editModalTitle');
        const body = document.getElementById('editModalBody');

        title.textContent = 'Edit Checklist Item';
        body.innerHTML = `
            <div class="form-group">
                <label>Number</label>
                <input type="text" id="editItemNumber" value="${escapeHtml(item.number)}" readonly>
            </div>
            <div class="form-group">
                <label>Category</label>
                <input type="text" id="editItemCategory" value="${escapeHtml(item.category || '')}">
            </div>
            <div class="form-group">
                <label>Description</label>
                <textarea id="editItemDescription" rows="4">${escapeHtml(item.description)}</textarea>
            </div>
        `;

        modal.classList.add('show');

        document.getElementById('saveEditBtn').onclick = () => {
            item.category = document.getElementById('editItemCategory').value;
            item.description = document.getElementById('editItemDescription').value;
            populateMappingTables();
            modal.classList.remove('show');
        };
    };

    // Utility Functions
    function showProgress(show) {
        progressSection.classList.toggle('hidden', !show);
        parseBtn.disabled = show;
    }

    function updateProgress(percentage, message) {
        if (percentage !== null) {
            progressFill.style.width = `${percentage}%`;
        }
        if (message) {
            progressMessage.textContent = message;
        }
    }

    function resetState() {
        currentState = {
            uploadedFile: null,
            filePath: null,
            parseResult: null,
            sections: [],
            checklistItems: [],
            userMappings: { sections: {}, items: {} },
        };

        // Reset UI
        dropZone.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="drop-icon">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                <polyline points="17 8 12 3 7 8"/>
                <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
            <p>Drag & drop a file here, or click to browse</p>
            <span class="file-types">PDF, Excel, CSV, or Text</span>
        `;
        rawText.value = '';
        document.getElementById('libraryName').value = '';
        document.getElementById('versionInput').value = '';
        fileInput.value = '';
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function formatDate(isoString) {
        return new Date(isoString).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function showToast(message, type = 'info') {
        // Use existing toast system if available
        if (typeof AccreditAI !== 'undefined' && AccreditAI.toast) {
            AccreditAI.toast.show(message, type);
        } else if (window.showToast) {
            window.showToast(message, type);
        } else {
            alert(message);
        }
    }

    // Initialize
    loadHistory();
});
