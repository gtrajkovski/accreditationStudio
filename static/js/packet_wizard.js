/**
 * Packet Studio Wizard Controller
 *
 * 5-step visual wizard for building submission packets:
 * 1. Submission Type - Select packet type and accreditor
 * 2. Standards - Select standards to address
 * 3. Evidence Mapping - Map evidence to standards via drag-drop
 * 4. Narrative Editor - Generate/edit narrative sections
 * 5. Live Preview - Preview and export
 */

const PacketWizard = {
    institutionId: null,
    currentStep: 1,
    totalSteps: 5,

    // Wizard state
    state: {
        submissionType: null,
        accreditor: null,
        packetName: '',
        selectedStandards: [],
        evidenceMapping: {},
        narratives: {},
        packetId: null,
    },

    // Standards data
    standards: [],
    documents: [],

    /**
     * Initialize the wizard.
     * @param {string} institutionId - Institution ID
     */
    init(institutionId) {
        this.institutionId = institutionId;
        this.bindEvents();
        this.loadInitialData();
        this.updateStepIndicators();
    },

    /**
     * Bind all event listeners.
     */
    bindEvents() {
        // Step navigation
        document.querySelectorAll('.wizard-step-indicator').forEach(indicator => {
            indicator.addEventListener('click', (e) => {
                const step = parseInt(e.currentTarget.dataset.step);
                if (this.canNavigateToStep(step)) {
                    this.goToStep(step);
                }
            });
        });

        // Submission type cards
        document.querySelectorAll('.submission-type-card').forEach(card => {
            card.addEventListener('click', () => {
                this.selectSubmissionType(card.dataset.type);
            });
        });

        // Accreditor select
        const accreditorSelect = document.getElementById('accreditor-select');
        if (accreditorSelect) {
            accreditorSelect.addEventListener('change', (e) => {
                this.state.accreditor = e.target.value;
                this.loadStandards();
            });
        }

        // Packet name
        const packetNameInput = document.getElementById('packet-name');
        if (packetNameInput) {
            packetNameInput.addEventListener('input', (e) => {
                this.state.packetName = e.target.value;
            });
        }

        // Navigation buttons
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');

        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.prevStep());
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.nextStep());
        }

        // Export button
        const exportBtn = document.getElementById('export-btn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportPacket());
        }

        // AI Suggest buttons
        document.addEventListener('click', (e) => {
            if (e.target.closest('.btn-ai-suggest')) {
                const standardCode = e.target.closest('.mapping-standard').dataset.standard;
                this.aiSuggestEvidence(standardCode);
            }
        });

        // Generate narrative button
        const generateBtn = document.getElementById('generate-narrative-btn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.generateNarrative());
        }

        // Regenerate narrative button
        const regenerateBtn = document.getElementById('regenerate-narrative-btn');
        if (regenerateBtn) {
            regenerateBtn.addEventListener('click', () => this.regenerateNarrative());
        }

        // Narrative textarea
        const narrativeTextarea = document.getElementById('narrative-content');
        if (narrativeTextarea) {
            narrativeTextarea.addEventListener('input', (e) => this.saveNarrativeContent(e.target.value));
        }

        // Evidence search
        const evidenceSearch = document.getElementById('evidence-search');
        if (evidenceSearch) {
            evidenceSearch.addEventListener('input', (e) => this.filterEvidence(e.target.value));
        }
    },

    /**
     * Load initial data (standards, documents).
     */
    async loadInitialData() {
        try {
            // Load documents for evidence pool
            const docsResponse = await fetch(`/api/institutions/${this.institutionId}/documents`);
            if (docsResponse.ok) {
                const docsData = await docsResponse.json();
                this.documents = docsData.documents || [];
            }
        } catch (error) {
            console.error('Failed to load initial data:', error);
        }
    },

    /**
     * Load standards for the selected accreditor.
     */
    async loadStandards() {
        if (!this.state.accreditor) return;

        try {
            const response = await fetch(`/api/standards/${this.state.accreditor}`);
            if (response.ok) {
                const data = await response.json();
                this.standards = data.standards || [];
                this.renderStandardsTree();
            }
        } catch (error) {
            console.error('Failed to load standards:', error);
        }
    },

    /**
     * Select submission type.
     * @param {string} type - Submission type
     */
    selectSubmissionType(type) {
        this.state.submissionType = type;

        // Update UI
        document.querySelectorAll('.submission-type-card').forEach(card => {
            card.classList.toggle('selected', card.dataset.type === type);
        });
    },

    /**
     * Check if user can navigate to a step.
     * @param {number} step - Target step
     * @returns {boolean}
     */
    canNavigateToStep(step) {
        // Can always go back
        if (step < this.currentStep) return true;

        // Validate current step before moving forward
        return this.validateStep(this.currentStep);
    },

    /**
     * Validate current step.
     * @param {number} step - Step to validate
     * @returns {boolean}
     */
    validateStep(step) {
        const errors = [];

        switch (step) {
            case 1:
                if (!this.state.submissionType) {
                    errors.push(AccreditAI.i18n.t('wizard.error_select_type'));
                }
                if (!this.state.accreditor) {
                    errors.push(AccreditAI.i18n.t('wizard.error_select_accreditor'));
                }
                if (!this.state.packetName.trim()) {
                    errors.push(AccreditAI.i18n.t('wizard.error_enter_name'));
                }
                break;

            case 2:
                if (this.state.selectedStandards.length === 0) {
                    errors.push(AccreditAI.i18n.t('wizard.error_select_standards'));
                }
                break;

            case 3:
                // Evidence mapping is optional but recommended
                break;

            case 4:
                // Narratives are optional
                break;
        }

        if (errors.length > 0) {
            this.showValidationErrors(errors);
            return false;
        }

        this.hideValidationErrors();
        return true;
    },

    /**
     * Show validation errors.
     * @param {string[]} errors - List of error messages
     */
    showValidationErrors(errors) {
        let container = document.getElementById('validation-errors');
        if (!container) {
            container = document.createElement('div');
            container.id = 'validation-errors';
            container.className = 'validation-errors';
            document.querySelector('.wizard-step.active').appendChild(container);
        }

        container.innerHTML = `
            <h4>${AccreditAI.i18n.t('wizard.validation_required')}</h4>
            <ul>
                ${errors.map(e => `<li>${e}</li>`).join('')}
            </ul>
        `;
        container.style.display = 'block';
    },

    /**
     * Hide validation errors.
     */
    hideValidationErrors() {
        const container = document.getElementById('validation-errors');
        if (container) {
            container.style.display = 'none';
        }
    },

    /**
     * Go to a specific step.
     * @param {number} step - Step number (1-5)
     */
    goToStep(step) {
        if (step < 1 || step > this.totalSteps) return;

        this.currentStep = step;
        this.updateStepIndicators();
        this.showStep(step);
        this.updateNavigationButtons();

        // Step-specific initialization
        switch (step) {
            case 2:
                this.renderStandardsTree();
                break;
            case 3:
                this.renderEvidenceMapping();
                break;
            case 4:
                this.renderNarrativeSections();
                break;
            case 5:
                this.renderPreview();
                break;
        }
    },

    /**
     * Go to previous step.
     */
    prevStep() {
        if (this.currentStep > 1) {
            this.goToStep(this.currentStep - 1);
        }
    },

    /**
     * Go to next step.
     */
    nextStep() {
        if (this.currentStep < this.totalSteps && this.validateStep(this.currentStep)) {
            // Create packet on moving from step 1
            if (this.currentStep === 1 && !this.state.packetId) {
                this.createPacket().then(() => {
                    this.goToStep(this.currentStep + 1);
                });
            } else {
                this.goToStep(this.currentStep + 1);
            }
        }
    },

    /**
     * Update step indicators.
     */
    updateStepIndicators() {
        document.querySelectorAll('.wizard-step-indicator').forEach(indicator => {
            const step = parseInt(indicator.dataset.step);
            indicator.classList.remove('active', 'completed', 'disabled');

            if (step === this.currentStep) {
                indicator.classList.add('active');
            } else if (step < this.currentStep) {
                indicator.classList.add('completed');
            } else if (!this.canNavigateToStep(step)) {
                indicator.classList.add('disabled');
            }
        });
    },

    /**
     * Show a specific step content.
     * @param {number} step - Step number
     */
    showStep(step) {
        document.querySelectorAll('.wizard-step').forEach(stepEl => {
            stepEl.classList.remove('active');
        });

        const stepEl = document.querySelector(`.wizard-step[data-step="${step}"]`);
        if (stepEl) {
            stepEl.classList.add('active');
        }
    },

    /**
     * Update navigation buttons state.
     */
    updateNavigationButtons() {
        const prevBtn = document.getElementById('prev-btn');
        const nextBtn = document.getElementById('next-btn');
        const exportBtn = document.getElementById('export-btn');

        if (prevBtn) {
            prevBtn.style.display = this.currentStep > 1 ? '' : 'none';
        }

        if (nextBtn) {
            nextBtn.style.display = this.currentStep < this.totalSteps ? '' : 'none';
        }

        if (exportBtn) {
            exportBtn.style.display = this.currentStep === this.totalSteps ? '' : 'none';
        }
    },

    /**
     * Create the packet via API.
     */
    async createPacket() {
        try {
            const response = await fetch(`/api/institutions/${this.institutionId}/packets`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: this.state.packetName,
                    accrediting_body: this.state.accreditor,
                    submission_type: this.state.submissionType,
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.state.packetId = data.packet_id;
                this.showToast(AccreditAI.i18n.t('wizard.packet_created'), 'success');
            } else {
                throw new Error('Failed to create packet');
            }
        } catch (error) {
            console.error('Create packet error:', error);
            this.showToast(AccreditAI.i18n.t('wizard.error_create_packet'), 'error');
        }
    },

    /**
     * Render standards tree (Step 2).
     */
    renderStandardsTree() {
        const container = document.getElementById('standards-tree');
        if (!container || !this.standards.length) return;

        // Group standards by section
        const sections = {};
        this.standards.forEach(std => {
            const sectionCode = std.code.split('.')[0];
            if (!sections[sectionCode]) {
                sections[sectionCode] = {
                    code: sectionCode,
                    title: std.section_title || `Section ${sectionCode}`,
                    items: []
                };
            }
            sections[sectionCode].items.push(std);
        });

        container.innerHTML = Object.values(sections).map(section => `
            <div class="standards-tree-section">
                <div class="section-header" onclick="PacketWizard.toggleSection('${section.code}')">
                    <svg class="section-toggle" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="9 18 15 12 9 6"/>
                    </svg>
                    <input type="checkbox" class="section-checkbox"
                           id="section-${section.code}"
                           onclick="event.stopPropagation(); PacketWizard.toggleSectionSelection('${section.code}')"
                           ${this.isSectionSelected(section.code) ? 'checked' : ''}>
                    <span class="section-title">${section.code} - ${section.title}</span>
                    <span class="section-count">(${section.items.length})</span>
                </div>
                <div class="section-items">
                    ${section.items.map(std => `
                        <div class="standard-item">
                            <input type="checkbox" id="std-${std.id}"
                                   onchange="PacketWizard.toggleStandard('${std.id}')"
                                   ${this.state.selectedStandards.includes(std.id) ? 'checked' : ''}>
                            <span class="standard-code">${std.code}</span>
                            <span class="standard-text">${std.title || std.text || ''}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');

        this.updateSelectedSummary();
    },

    /**
     * Toggle section expansion.
     * @param {string} sectionCode - Section code
     */
    toggleSection(sectionCode) {
        const header = document.querySelector(`#section-${sectionCode}`).closest('.section-header');
        header.classList.toggle('expanded');
    },

    /**
     * Toggle all standards in a section.
     * @param {string} sectionCode - Section code
     */
    toggleSectionSelection(sectionCode) {
        const checkbox = document.getElementById(`section-${sectionCode}`);
        const isChecked = checkbox.checked;

        // Find all standards in this section
        const sectionStandards = this.standards.filter(s => s.code.startsWith(sectionCode + '.'));

        sectionStandards.forEach(std => {
            const stdCheckbox = document.getElementById(`std-${std.id}`);
            if (stdCheckbox) {
                stdCheckbox.checked = isChecked;
            }

            if (isChecked && !this.state.selectedStandards.includes(std.id)) {
                this.state.selectedStandards.push(std.id);
            } else if (!isChecked) {
                this.state.selectedStandards = this.state.selectedStandards.filter(id => id !== std.id);
            }
        });

        this.updateSelectedSummary();
    },

    /**
     * Check if a section is fully selected.
     * @param {string} sectionCode - Section code
     * @returns {boolean}
     */
    isSectionSelected(sectionCode) {
        const sectionStandards = this.standards.filter(s => s.code.startsWith(sectionCode + '.'));
        return sectionStandards.length > 0 &&
               sectionStandards.every(s => this.state.selectedStandards.includes(s.id));
    },

    /**
     * Toggle a single standard selection.
     * @param {string} standardId - Standard ID
     */
    toggleStandard(standardId) {
        const index = this.state.selectedStandards.indexOf(standardId);
        if (index === -1) {
            this.state.selectedStandards.push(standardId);
        } else {
            this.state.selectedStandards.splice(index, 1);
        }

        this.updateSelectedSummary();
    },

    /**
     * Update selected standards summary.
     */
    updateSelectedSummary() {
        const countEl = document.getElementById('selected-count');
        const listEl = document.getElementById('selected-standards-list');

        if (countEl) {
            countEl.textContent = this.state.selectedStandards.length;
        }

        if (listEl) {
            const selectedStds = this.standards.filter(s => this.state.selectedStandards.includes(s.id));
            listEl.innerHTML = selectedStds.slice(0, 10).map(std => `
                <span class="selected-standard-tag">
                    ${std.code}
                    <span class="remove-tag" onclick="PacketWizard.toggleStandard('${std.id}')">&times;</span>
                </span>
            `).join('') + (selectedStds.length > 10 ? `<span class="text-muted">+${selectedStds.length - 10} more</span>` : '');
        }
    },

    /**
     * Render evidence mapping (Step 3).
     */
    renderEvidenceMapping() {
        const poolList = document.getElementById('evidence-pool-list');
        const mappingList = document.getElementById('standards-mapping-list');

        // Render evidence pool
        if (poolList) {
            poolList.innerHTML = this.documents.map(doc => `
                <div class="evidence-item" draggable="true" data-doc-id="${doc.id}"
                     ondragstart="PacketWizard.onDragStart(event, '${doc.id}')"
                     ondragend="PacketWizard.onDragEnd(event)">
                    <svg class="drag-handle" viewBox="0 0 24 24" fill="currentColor" width="16" height="16">
                        <circle cx="8" cy="6" r="2"/><circle cx="16" cy="6" r="2"/>
                        <circle cx="8" cy="12" r="2"/><circle cx="16" cy="12" r="2"/>
                        <circle cx="8" cy="18" r="2"/><circle cx="16" cy="18" r="2"/>
                    </svg>
                    <svg class="evidence-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                        <path d="M14 2v6h6"/>
                    </svg>
                    <div class="evidence-info">
                        <div class="evidence-name">${this.escapeHtml(doc.name || doc.filename)}</div>
                        <div class="evidence-meta">${doc.doc_type || 'Document'}</div>
                    </div>
                </div>
            `).join('');
        }

        // Render standards mapping zones
        if (mappingList) {
            const selectedStds = this.standards.filter(s => this.state.selectedStandards.includes(s.id));

            mappingList.innerHTML = selectedStds.map(std => `
                <div class="mapping-standard" data-standard="${std.code}">
                    <div class="mapping-standard-header">
                        <span class="mapping-standard-code">${std.code}</span>
                        <span class="mapping-standard-title">${std.title || ''}</span>
                        <button class="btn btn-secondary btn-ai-suggest">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                            </svg>
                            ${AccreditAI.i18n.t('wizard.ai_suggest')}
                        </button>
                    </div>
                    <div class="mapping-drop-zone ${this.state.evidenceMapping[std.code]?.length ? 'has-evidence' : ''}"
                         data-standard="${std.code}"
                         ondragover="PacketWizard.onDragOver(event)"
                         ondragleave="PacketWizard.onDragLeave(event)"
                         ondrop="PacketWizard.onDrop(event, '${std.code}')">
                        <div class="drop-placeholder">${AccreditAI.i18n.t('wizard.drop_evidence')}</div>
                        ${(this.state.evidenceMapping[std.code] || []).map(docId => {
                            const doc = this.documents.find(d => d.id === docId);
                            return doc ? `
                                <div class="mapped-evidence">
                                    <span class="evidence-name">${this.escapeHtml(doc.name || doc.filename)}</span>
                                    <span class="remove-mapping" onclick="PacketWizard.removeMapping('${std.code}', '${docId}')">&times;</span>
                                </div>
                            ` : '';
                        }).join('')}
                    </div>
                </div>
            `).join('');
        }
    },

    /**
     * Drag start handler.
     */
    onDragStart(event, docId) {
        event.dataTransfer.setData('text/plain', docId);
        event.target.classList.add('dragging');
    },

    /**
     * Drag end handler.
     */
    onDragEnd(event) {
        event.target.classList.remove('dragging');
    },

    /**
     * Drag over handler.
     */
    onDragOver(event) {
        event.preventDefault();
        event.currentTarget.classList.add('drag-over');
    },

    /**
     * Drag leave handler.
     */
    onDragLeave(event) {
        event.currentTarget.classList.remove('drag-over');
    },

    /**
     * Drop handler.
     */
    onDrop(event, standardCode) {
        event.preventDefault();
        event.currentTarget.classList.remove('drag-over');

        const docId = event.dataTransfer.getData('text/plain');
        if (!docId) return;

        if (!this.state.evidenceMapping[standardCode]) {
            this.state.evidenceMapping[standardCode] = [];
        }

        if (!this.state.evidenceMapping[standardCode].includes(docId)) {
            this.state.evidenceMapping[standardCode].push(docId);
            this.renderEvidenceMapping();
        }
    },

    /**
     * Remove evidence mapping.
     */
    removeMapping(standardCode, docId) {
        if (this.state.evidenceMapping[standardCode]) {
            this.state.evidenceMapping[standardCode] = this.state.evidenceMapping[standardCode].filter(id => id !== docId);
            this.renderEvidenceMapping();
        }
    },

    /**
     * AI suggest evidence for a standard.
     */
    async aiSuggestEvidence(standardCode) {
        this.showToast(AccreditAI.i18n.t('wizard.searching_evidence'), 'info');

        try {
            const response = await fetch(`/api/institutions/${this.institutionId}/evidence/suggest`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    standard_code: standardCode,
                    limit: 5
                })
            });

            if (response.ok) {
                const data = await response.json();
                const suggestions = data.suggestions || [];

                if (suggestions.length > 0) {
                    if (!this.state.evidenceMapping[standardCode]) {
                        this.state.evidenceMapping[standardCode] = [];
                    }

                    suggestions.forEach(s => {
                        if (!this.state.evidenceMapping[standardCode].includes(s.document_id)) {
                            this.state.evidenceMapping[standardCode].push(s.document_id);
                        }
                    });

                    this.renderEvidenceMapping();
                    this.showToast(`${suggestions.length} ${AccreditAI.i18n.t('wizard.evidence_found')}`, 'success');
                } else {
                    this.showToast(AccreditAI.i18n.t('wizard.no_evidence_found'), 'warning');
                }
            }
        } catch (error) {
            console.error('AI suggest error:', error);
            this.showToast(AccreditAI.i18n.t('wizard.suggest_failed'), 'error');
        }
    },

    /**
     * Filter evidence pool.
     */
    filterEvidence(query) {
        const items = document.querySelectorAll('#evidence-pool-list .evidence-item');
        const lowerQuery = query.toLowerCase();

        items.forEach(item => {
            const name = item.querySelector('.evidence-name').textContent.toLowerCase();
            item.style.display = name.includes(lowerQuery) ? '' : 'none';
        });
    },

    /**
     * Render narrative sections (Step 4).
     */
    renderNarrativeSections() {
        const sectionsList = document.getElementById('narrative-sections-list');
        if (!sectionsList) return;

        const selectedStds = this.standards.filter(s => this.state.selectedStandards.includes(s.id));

        sectionsList.innerHTML = selectedStds.map((std, idx) => {
            const narrative = this.state.narratives[std.code] || {};
            let statusClass = 'empty';
            if (narrative.content && narrative.content.length > 100) {
                statusClass = 'complete';
            } else if (narrative.content) {
                statusClass = 'draft';
            }

            return `
                <div class="section-nav-item ${idx === 0 ? 'active' : ''}" data-standard="${std.code}"
                     onclick="PacketWizard.selectNarrativeSection('${std.code}')">
                    <svg class="status-icon ${statusClass}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        ${statusClass === 'complete' ? '<circle cx="12" cy="12" r="10"/><path d="M9 12l2 2 4-4"/>' :
                          statusClass === 'draft' ? '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>' :
                          '<circle cx="12" cy="12" r="10"/>'}
                    </svg>
                    <div class="section-nav-info">
                        <div class="section-nav-title">${std.title || 'Standard Response'}</div>
                        <div class="section-nav-standard">${std.code}</div>
                    </div>
                </div>
            `;
        }).join('');

        // Select first section
        if (selectedStds.length > 0) {
            this.selectNarrativeSection(selectedStds[0].code);
        }
    },

    /**
     * Current selected narrative section.
     */
    currentNarrativeSection: null,

    /**
     * Select a narrative section for editing.
     */
    selectNarrativeSection(standardCode) {
        this.currentNarrativeSection = standardCode;

        // Update sidebar
        document.querySelectorAll('.section-nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.standard === standardCode);
        });

        // Update editor
        const standard = this.standards.find(s => s.code === standardCode);
        const narrative = this.state.narratives[standardCode] || {};

        const editorTitle = document.getElementById('editor-section-title');
        const editorTextarea = document.getElementById('narrative-content');
        const wordCount = document.getElementById('word-count');

        if (editorTitle && standard) {
            editorTitle.textContent = `${standard.code} - ${standard.title || 'Response'}`;
        }

        if (editorTextarea) {
            editorTextarea.value = narrative.content || '';
        }

        if (wordCount) {
            const words = (narrative.content || '').trim().split(/\s+/).filter(w => w).length;
            wordCount.textContent = `${words} words`;
        }
    },

    /**
     * Save narrative content.
     */
    saveNarrativeContent(content) {
        if (!this.currentNarrativeSection) return;

        if (!this.state.narratives[this.currentNarrativeSection]) {
            this.state.narratives[this.currentNarrativeSection] = {};
        }

        this.state.narratives[this.currentNarrativeSection].content = content;

        // Update word count
        const wordCount = document.getElementById('word-count');
        if (wordCount) {
            const words = content.trim().split(/\s+/).filter(w => w).length;
            wordCount.textContent = `${words} words`;
        }

        // Update section status in sidebar
        this.updateNarrativeSectionStatus(this.currentNarrativeSection);
    },

    /**
     * Update narrative section status icon.
     */
    updateNarrativeSectionStatus(standardCode) {
        const item = document.querySelector(`.section-nav-item[data-standard="${standardCode}"]`);
        if (!item) return;

        const narrative = this.state.narratives[standardCode];
        const icon = item.querySelector('.status-icon');

        icon.classList.remove('empty', 'draft', 'complete');

        if (narrative?.content && narrative.content.length > 100) {
            icon.classList.add('complete');
        } else if (narrative?.content) {
            icon.classList.add('draft');
        } else {
            icon.classList.add('empty');
        }
    },

    /**
     * Generate narrative using AI.
     */
    async generateNarrative() {
        if (!this.currentNarrativeSection) return;

        const standard = this.standards.find(s => s.code === this.currentNarrativeSection);
        if (!standard) return;

        const editorContent = document.getElementById('editor-content');
        const originalContent = editorContent.innerHTML;

        // Show generating indicator
        editorContent.innerHTML = `
            <div class="ai-generating">
                <div class="spinner"></div>
                <span>${AccreditAI.i18n.t('wizard.generating_narrative')}</span>
            </div>
        `;

        try {
            const response = await fetch(`/api/institutions/${this.institutionId}/packets/${this.state.packetId}/narratives/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    standard_code: this.currentNarrativeSection,
                    evidence_ids: this.state.evidenceMapping[this.currentNarrativeSection] || []
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.state.narratives[this.currentNarrativeSection] = {
                    content: data.content,
                    generated: true
                };

                // Restore editor with content
                editorContent.innerHTML = `<textarea id="narrative-content" class="narrative-textarea"
                    oninput="PacketWizard.saveNarrativeContent(this.value)">${this.escapeHtml(data.content)}</textarea>`;

                this.updateNarrativeSectionStatus(this.currentNarrativeSection);
                this.showToast(AccreditAI.i18n.t('wizard.narrative_generated'), 'success');
            } else {
                throw new Error('Generation failed');
            }
        } catch (error) {
            console.error('Generate narrative error:', error);
            editorContent.innerHTML = originalContent;
            this.showToast(AccreditAI.i18n.t('wizard.generate_failed'), 'error');
        }
    },

    /**
     * Regenerate narrative.
     */
    regenerateNarrative() {
        if (confirm(AccreditAI.i18n.t('wizard.confirm_regenerate'))) {
            this.generateNarrative();
        }
    },

    /**
     * Render live preview (Step 5).
     */
    renderPreview() {
        const tocList = document.getElementById('preview-toc-list');
        const previewContent = document.getElementById('preview-content');

        const selectedStds = this.standards.filter(s => this.state.selectedStandards.includes(s.id));

        // Render TOC
        if (tocList) {
            tocList.innerHTML = `
                <div class="toc-item active" onclick="PacketWizard.scrollToSection('cover')">
                    <span class="toc-number">-</span>
                    <span class="toc-title">${AccreditAI.i18n.t('wizard.cover_page')}</span>
                </div>
                ${selectedStds.map((std, idx) => `
                    <div class="toc-item" onclick="PacketWizard.scrollToSection('section-${std.code}')">
                        <span class="toc-number">${idx + 1}</span>
                        <span class="toc-title">${std.code}</span>
                    </div>
                `).join('')}
                <div class="toc-item" onclick="PacketWizard.scrollToSection('evidence-index')">
                    <span class="toc-number">-</span>
                    <span class="toc-title">${AccreditAI.i18n.t('wizard.evidence_index')}</span>
                </div>
            `;
        }

        // Render preview document
        if (previewContent) {
            const submissionTypeLabels = {
                'self_study': AccreditAI.i18n.t('wizard.type_self_study'),
                'response': AccreditAI.i18n.t('wizard.type_response'),
                'teach_out': AccreditAI.i18n.t('wizard.type_teach_out'),
                'annual': AccreditAI.i18n.t('wizard.type_annual'),
                'substantive_change': AccreditAI.i18n.t('wizard.type_substantive')
            };

            previewContent.innerHTML = `
                <div class="preview-page" id="cover">
                    <h1>${this.escapeHtml(this.state.packetName)}</h1>
                    <p style="text-align: center; margin-top: 40px;">
                        <strong>${submissionTypeLabels[this.state.submissionType] || this.state.submissionType}</strong>
                    </p>
                    <p style="text-align: center;">
                        ${this.state.accreditor}
                    </p>
                    <p style="text-align: center; margin-top: 60px;">
                        ${new Date().toLocaleDateString()}
                    </p>
                </div>

                ${selectedStds.map(std => {
                    const narrative = this.state.narratives[std.code];
                    const evidence = this.state.evidenceMapping[std.code] || [];

                    return `
                        <div class="preview-page" id="section-${std.code}">
                            <h2><span class="standard-ref">${std.code}</span> - ${std.title || 'Response'}</h2>
                            <p>${narrative?.content || '<em>[Narrative pending]</em>'}</p>
                            ${evidence.length > 0 ? `
                                <p style="margin-top: 20px;"><strong>Evidence:</strong></p>
                                <ul>
                                    ${evidence.map(docId => {
                                        const doc = this.documents.find(d => d.id === docId);
                                        return doc ? `<li>${this.escapeHtml(doc.name || doc.filename)}</li>` : '';
                                    }).join('')}
                                </ul>
                            ` : ''}
                        </div>
                    `;
                }).join('')}

                <div class="preview-page" id="evidence-index">
                    <h2>${AccreditAI.i18n.t('wizard.evidence_index')}</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="border-bottom: 1px solid #ccc;">
                            <th style="text-align: left; padding: 8px;">${AccreditAI.i18n.t('wizard.evidence_name')}</th>
                            <th style="text-align: left; padding: 8px;">${AccreditAI.i18n.t('wizard.standards')}</th>
                        </tr>
                        ${this.buildEvidenceIndex().map(row => `
                            <tr style="border-bottom: 1px solid #eee;">
                                <td style="padding: 8px;">${this.escapeHtml(row.name)}</td>
                                <td style="padding: 8px;">${row.standards.join(', ')}</td>
                            </tr>
                        `).join('')}
                    </table>
                </div>
            `;
        }
    },

    /**
     * Build evidence index from mappings.
     */
    buildEvidenceIndex() {
        const index = {};

        Object.entries(this.state.evidenceMapping).forEach(([standardCode, docIds]) => {
            docIds.forEach(docId => {
                if (!index[docId]) {
                    const doc = this.documents.find(d => d.id === docId);
                    index[docId] = {
                        name: doc?.name || doc?.filename || docId,
                        standards: []
                    };
                }
                index[docId].standards.push(standardCode);
            });
        });

        return Object.values(index);
    },

    /**
     * Scroll to a section in preview.
     */
    scrollToSection(sectionId) {
        const section = document.getElementById(sectionId);
        if (section) {
            section.scrollIntoView({ behavior: 'smooth' });
        }

        // Update active TOC item
        document.querySelectorAll('.toc-item').forEach(item => {
            item.classList.remove('active');
        });
        event.currentTarget.classList.add('active');
    },

    /**
     * Export the packet.
     */
    async exportPacket() {
        if (!this.state.packetId) {
            this.showToast(AccreditAI.i18n.t('wizard.error_no_packet'), 'error');
            return;
        }

        const exportBtn = document.getElementById('export-btn');
        if (exportBtn) {
            exportBtn.disabled = true;
            exportBtn.innerHTML = `<span class="spinner"></span> ${AccreditAI.i18n.t('wizard.exporting')}`;
        }

        try {
            // Save all narratives first
            for (const [standardCode, narrative] of Object.entries(this.state.narratives)) {
                if (narrative.content) {
                    await fetch(`/api/institutions/${this.institutionId}/packets/${this.state.packetId}/sections`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            title: `Response to ${standardCode}`,
                            content: narrative.content,
                            standard_refs: [standardCode],
                            evidence_refs: this.state.evidenceMapping[standardCode] || []
                        })
                    });
                }
            }

            // Validate and export
            const validateResponse = await fetch(`/api/institutions/${this.institutionId}/packets/${this.state.packetId}/validate`, {
                method: 'POST'
            });

            const validation = await validateResponse.json();

            if (!validation.is_valid && !confirm(AccreditAI.i18n.t('wizard.confirm_export_with_issues'))) {
                if (exportBtn) {
                    exportBtn.disabled = false;
                    exportBtn.innerHTML = AccreditAI.i18n.t('wizard.export');
                }
                return;
            }

            // Export as ZIP
            const exportResponse = await fetch(`/api/institutions/${this.institutionId}/packets/${this.state.packetId}/export/zip`, {
                method: 'POST'
            });

            if (exportResponse.ok) {
                window.location.href = `/api/institutions/${this.institutionId}/packets/${this.state.packetId}/download/zip`;
                this.showToast(AccreditAI.i18n.t('wizard.export_success'), 'success');
            } else {
                throw new Error('Export failed');
            }
        } catch (error) {
            console.error('Export error:', error);
            this.showToast(AccreditAI.i18n.t('wizard.export_failed'), 'error');
        } finally {
            if (exportBtn) {
                exportBtn.disabled = false;
                exportBtn.innerHTML = AccreditAI.i18n.t('wizard.export');
            }
        }
    },

    /**
     * Escape HTML.
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    },

    /**
     * Show toast notification.
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
    module.exports = PacketWizard;
}
