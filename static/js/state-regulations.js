/**
 * State Regulations JavaScript Module
 * Handles state authorization, catalog compliance, and program approvals
 */

// Global state
let currentInstitutionId = null;
let statesData = [];
let selectedStateCode = null;
let selectedStateData = null;
let programsData = [];

// US States list
const US_STATES = [
    {code: 'AL', name: 'Alabama'}, {code: 'AK', name: 'Alaska'}, {code: 'AZ', name: 'Arizona'},
    {code: 'AR', name: 'Arkansas'}, {code: 'CA', name: 'California'}, {code: 'CO', name: 'Colorado'},
    {code: 'CT', name: 'Connecticut'}, {code: 'DE', name: 'Delaware'}, {code: 'FL', name: 'Florida'},
    {code: 'GA', name: 'Georgia'}, {code: 'HI', name: 'Hawaii'}, {code: 'ID', name: 'Idaho'},
    {code: 'IL', name: 'Illinois'}, {code: 'IN', name: 'Indiana'}, {code: 'IA', name: 'Iowa'},
    {code: 'KS', name: 'Kansas'}, {code: 'KY', name: 'Kentucky'}, {code: 'LA', name: 'Louisiana'},
    {code: 'ME', name: 'Maine'}, {code: 'MD', name: 'Maryland'}, {code: 'MA', name: 'Massachusetts'},
    {code: 'MI', name: 'Michigan'}, {code: 'MN', name: 'Minnesota'}, {code: 'MS', name: 'Mississippi'},
    {code: 'MO', name: 'Missouri'}, {code: 'MT', name: 'Montana'}, {code: 'NE', name: 'Nebraska'},
    {code: 'NV', name: 'Nevada'}, {code: 'NH', name: 'New Hampshire'}, {code: 'NJ', name: 'New Jersey'},
    {code: 'NM', name: 'New Mexico'}, {code: 'NY', name: 'New York'}, {code: 'NC', name: 'North Carolina'},
    {code: 'ND', name: 'North Dakota'}, {code: 'OH', name: 'Ohio'}, {code: 'OK', name: 'Oklahoma'},
    {code: 'OR', name: 'Oregon'}, {code: 'PA', name: 'Pennsylvania'}, {code: 'RI', name: 'Rhode Island'},
    {code: 'SC', name: 'South Carolina'}, {code: 'SD', name: 'South Dakota'}, {code: 'TN', name: 'Tennessee'},
    {code: 'TX', name: 'Texas'}, {code: 'UT', name: 'Utah'}, {code: 'VT', name: 'Vermont'},
    {code: 'VA', name: 'Virginia'}, {code: 'WA', name: 'Washington'}, {code: 'WV', name: 'West Virginia'},
    {code: 'WI', name: 'Wisconsin'}, {code: 'WY', name: 'Wyoming'}, {code: 'DC', name: 'District of Columbia'},
    {code: 'PR', name: 'Puerto Rico'}
];

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    currentInstitutionId = document.body.dataset.institutionId;
    populateStateDropdown();
    loadStates();
    loadPrograms();
});

// Populate state dropdown
function populateStateDropdown() {
    const select = document.getElementById('addStateCode');
    if (!select) return;
    US_STATES.forEach(state => {
        const option = document.createElement('option');
        option.value = state.code;
        option.textContent = `${state.name} (${state.code})`;
        select.appendChild(option);
    });
}

// Load institution programs for dropdown
async function loadPrograms() {
    try {
        const resp = await fetch(`/api/institutions/${currentInstitutionId}/programs`);
        if (resp.ok) {
            const data = await resp.json();
            programsData = data.programs || [];
            populateProgramDropdown();
        }
    } catch (err) {
        console.error('Error loading programs:', err);
    }
}

function populateProgramDropdown() {
    const select = document.getElementById('addProgramId');
    if (!select) return;
    select.innerHTML = '<option value="">Select a program...</option>';
    programsData.forEach(prog => {
        const option = document.createElement('option');
        option.value = prog.id;
        option.textContent = prog.name;
        select.appendChild(option);
    });
}

// API Functions
async function loadStates() {
    try {
        const resp = await fetch(`/api/state-regulations/summary?institution_id=${currentInstitutionId}`);
        if (!resp.ok) throw new Error('Failed to load states');
        const data = await resp.json();
        statesData = data.states || [];
        renderStatesList();
        renderSummaryCards();
    } catch (err) {
        console.error('Error loading states:', err);
        showToast('Failed to load states', 'error');
    }
}

async function loadStateDetails(stateCode) {
    try {
        selectedStateCode = stateCode;

        // Fetch authorization
        const authResp = await fetch(`/api/state-regulations/${stateCode}?institution_id=${currentInstitutionId}`);
        const authData = authResp.ok ? await authResp.json() : {};

        // Fetch requirements
        const reqResp = await fetch(`/api/state-regulations/${stateCode}/requirements`);
        const reqData = reqResp.ok ? await reqResp.json() : {requirements: []};

        // Fetch compliance
        const compResp = await fetch(`/api/state-regulations/${stateCode}/compliance?institution_id=${currentInstitutionId}`);
        const compData = compResp.ok ? await compResp.json() : {compliance: []};

        // Fetch programs
        const progResp = await fetch(`/api/state-regulations/${stateCode}/programs?institution_id=${currentInstitutionId}`);
        const progData = progResp.ok ? await progResp.json() : {approvals: []};

        // Fetch readiness
        const readyResp = await fetch(`/api/state-regulations/${stateCode}/readiness?institution_id=${currentInstitutionId}`);
        const readyData = readyResp.ok ? await readyResp.json() : {readiness: {total: 0}};

        selectedStateData = {
            authorization: authData.authorization || authData,
            requirements: reqData.requirements || [],
            compliance: compData.compliance || [],
            approvals: progData.approvals || [],
            readiness: readyData.readiness || readyData
        };

        renderStateDetails();
    } catch (err) {
        console.error('Error loading state details:', err);
        showToast('Failed to load state details', 'error');
    }
}

async function addState(data) {
    try {
        const resp = await fetch('/api/state-regulations', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({...data, institution_id: currentInstitutionId})
        });
        if (!resp.ok) throw new Error('Failed to add state');
        hideAddStateModal();
        showToast('State added successfully', 'success');
        loadStates();
    } catch (err) {
        console.error('Error adding state:', err);
        showToast('Failed to add state', 'error');
    }
}

async function updateAuthorization(stateCode, data) {
    try {
        const resp = await fetch(`/api/state-regulations/${stateCode}?institution_id=${currentInstitutionId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        if (!resp.ok) throw new Error('Failed to update authorization');
        hideEditAuthModal();
        showToast('Authorization updated', 'success');
        loadStates();
        loadStateDetails(stateCode);
    } catch (err) {
        console.error('Error updating authorization:', err);
        showToast('Failed to update', 'error');
    }
}

async function deleteAuthorization(stateCode) {
    if (!confirm(`Delete authorization for ${stateCode}? This cannot be undone.`)) return;
    try {
        const resp = await fetch(`/api/state-regulations/${stateCode}?institution_id=${currentInstitutionId}`, {
            method: 'DELETE'
        });
        if (!resp.ok) throw new Error('Failed to delete');
        showToast('Authorization deleted', 'success');
        selectedStateCode = null;
        selectedStateData = null;
        clearStateDetails();
        loadStates();
    } catch (err) {
        console.error('Error deleting:', err);
        showToast('Failed to delete', 'error');
    }
}

async function updateCompliance(requirementId, status) {
    try {
        const resp = await fetch(`/api/state-regulations/${selectedStateCode}/compliance/${requirementId}?institution_id=${currentInstitutionId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({status})
        });
        if (!resp.ok) throw new Error('Failed to update compliance');
        loadStateDetails(selectedStateCode);
    } catch (err) {
        console.error('Error updating compliance:', err);
        showToast('Failed to update compliance', 'error');
    }
}

async function addProgramApproval(stateCode, data) {
    try {
        const resp = await fetch(`/api/state-regulations/${stateCode}/programs`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({...data, institution_id: currentInstitutionId})
        });
        if (!resp.ok) throw new Error('Failed to add program approval');
        hideAddProgramModal();
        showToast('Program approval added', 'success');
        loadStateDetails(stateCode);
    } catch (err) {
        console.error('Error adding program:', err);
        showToast('Failed to add program approval', 'error');
    }
}

async function deleteProgramApproval(approvalId) {
    if (!confirm('Delete this program approval?')) return;
    try {
        const resp = await fetch(`/api/state-regulations/${selectedStateCode}/programs/${approvalId}`, {
            method: 'DELETE'
        });
        if (!resp.ok) throw new Error('Failed to delete');
        showToast('Program approval deleted', 'success');
        loadStateDetails(selectedStateCode);
    } catch (err) {
        console.error('Error deleting:', err);
        showToast('Failed to delete', 'error');
    }
}

async function loadPreset() {
    const stateCode = document.getElementById('presetStateCode').value;
    try {
        const resp = await fetch(`/api/state-regulations/${stateCode}/load-preset`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({institution_id: currentInstitutionId})
        });
        if (!resp.ok) throw new Error('Failed to load preset');
        const data = await resp.json();
        hideLoadPresetModal();
        showToast(`Loaded ${data.loaded || 0} requirements`, 'success');
        if (selectedStateCode === stateCode) {
            loadStateDetails(stateCode);
        }
    } catch (err) {
        console.error('Error loading preset:', err);
        showToast('Failed to load preset', 'error');
    }
}

function loadPresetForState() {
    if (selectedStateCode) {
        document.getElementById('presetStateCode').value = selectedStateCode;
    }
    showLoadPresetModal();
}

// Render Functions
function renderStatesList() {
    const container = document.getElementById('statesList');
    if (!container) return;

    if (statesData.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="64" height="64">
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/>
                        <circle cx="12" cy="10" r="3"/>
                    </svg>
                </div>
                <div class="empty-state-title">No states added yet</div>
                <p>Add state authorizations to track compliance.</p>
                <div class="empty-state-action">
                    <button class="btn btn-primary" onclick="showAddStateModal()">Add State</button>
                </div>
            </div>
        `;
        return;
    }

    container.innerHTML = statesData.map(state => `
        <div class="state-card ${selectedStateCode === state.state_code ? 'selected' : ''}"
             onclick="selectState('${state.state_code}')">
            <div class="state-card-info">
                <span class="state-code">${state.state_code}</span>
                <div>
                    <div class="state-name">${getStateName(state.state_code)}</div>
                    <div class="state-badges">
                        <span class="badge badge-${getStatusBadgeClass(state.authorization_status)}">${state.authorization_status}</span>
                        ${state.sara_member ? '<span class="badge badge-sara">SARA</span>' : ''}
                    </div>
                </div>
            </div>
            <div style="text-align:right;">
                ${state.renewal_date ? `<div class="text-sm ${isExpiringSoon(state.renewal_date) ? 'text-warning' : 'text-muted'}">Renews: ${formatDate(state.renewal_date)}</div>` : ''}
                <div class="mini-score">${state.readiness_score || 0}%</div>
            </div>
        </div>
    `).join('');
}

function renderStateDetails() {
    if (!selectedStateData) return;

    document.getElementById('stateDetailsPanel').style.display = 'block';
    document.getElementById('noStateSelected').style.display = 'none';

    const stateName = getStateName(selectedStateCode);
    document.getElementById('selectedStateName').textContent = `${stateName} (${selectedStateCode})`;

    // Render authorization tab
    renderAuthorizationTab();

    // Render catalog tab
    renderCatalogTab();

    // Render programs tab
    renderProgramsTab();

    // Render readiness
    renderReadinessPanel();
}

function renderAuthorizationTab() {
    const auth = selectedStateData.authorization;
    const container = document.getElementById('authorizationContent');

    container.innerHTML = `
        <div class="auth-details">
            <div class="detail-row">
                <span class="detail-label">Status</span>
                <span class="badge badge-${getStatusBadgeClass(auth.authorization_status)}">${auth.authorization_status || 'N/A'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">SARA Member</span>
                <span>${auth.sara_member ? 'Yes' : 'No'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Effective Date</span>
                <span>${auth.effective_date ? formatDate(auth.effective_date) : 'N/A'}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">Renewal Date</span>
                <span class="${isExpiringSoon(auth.renewal_date) ? 'text-warning' : ''}">${auth.renewal_date ? formatDate(auth.renewal_date) : 'N/A'}</span>
            </div>
            ${auth.renewal_date && isExpiringSoon(auth.renewal_date) ? `
                <div class="renewal-warning ${daysUntil(auth.renewal_date) <= 30 ? 'urgent' : ''}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 6v6l4 2"/>
                    </svg>
                    Renewal due in ${daysUntil(auth.renewal_date)} days
                </div>
            ` : ''}
            <div class="detail-row">
                <span class="detail-label">Contact Agency</span>
                <span>${auth.contact_agency || 'N/A'}</span>
            </div>
            ${auth.contact_url ? `
                <div class="detail-row">
                    <span class="detail-label">Website</span>
                    <a href="${auth.contact_url}" target="_blank" class="text-accent">${auth.contact_url}</a>
                </div>
            ` : ''}
            ${auth.notes ? `
                <div class="detail-row">
                    <span class="detail-label">Notes</span>
                    <span>${auth.notes}</span>
                </div>
            ` : ''}
        </div>
    `;
}

function renderCatalogTab() {
    const requirements = selectedStateData.requirements;
    const compliance = selectedStateData.compliance;
    const container = document.getElementById('catalogContent');
    const countEl = document.getElementById('catalogCount');

    // Create compliance map
    const compMap = {};
    compliance.forEach(c => { compMap[c.requirement_id] = c; });

    if (requirements.length === 0) {
        countEl.textContent = '';
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-title">No requirements loaded</div>
                <p>Load a preset to get started.</p>
                <div class="empty-state-action">
                    <button class="btn btn-secondary" onclick="loadPresetForState()">Load Preset</button>
                </div>
            </div>
        `;
        return;
    }

    const satisfied = compliance.filter(c => c.status === 'satisfied').length;
    countEl.textContent = `${satisfied} of ${requirements.length} satisfied`;

    container.innerHTML = requirements.map(req => {
        const comp = compMap[req.id] || {status: 'missing'};
        return `
            <div class="requirement-item">
                <div class="requirement-info">
                    <div class="requirement-name">${req.requirement_name}</div>
                    <div class="requirement-category">${req.category || 'General'}</div>
                    ${req.requirement_text ? `<div class="text-sm text-muted mt-xs">${req.requirement_text}</div>` : ''}
                </div>
                <div class="requirement-status">
                    <select class="form-select form-select-sm" onchange="updateCompliance('${req.id}', this.value)" style="width:auto;">
                        <option value="missing" ${comp.status === 'missing' ? 'selected' : ''}>Missing</option>
                        <option value="partial" ${comp.status === 'partial' ? 'selected' : ''}>Partial</option>
                        <option value="satisfied" ${comp.status === 'satisfied' ? 'selected' : ''}>Satisfied</option>
                    </select>
                    <div class="status-icon ${comp.status}">
                        ${getStatusIcon(comp.status)}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function renderProgramsTab() {
    const approvals = selectedStateData.approvals;
    const container = document.getElementById('programsContent');
    const countEl = document.getElementById('programsCount');

    if (approvals.length === 0) {
        countEl.textContent = '';
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-title">No program approvals</div>
                <p>Add program-level licensing board approvals.</p>
                <div class="empty-state-action">
                    <button class="btn btn-primary btn-sm" onclick="showAddProgramModal()">Add Program</button>
                </div>
            </div>
        `;
        return;
    }

    const approved = approvals.filter(a => a.approved).length;
    countEl.textContent = `${approved} of ${approvals.length} approved`;

    container.innerHTML = `
        <table class="programs-table">
            <thead>
                <tr>
                    <th>Program</th>
                    <th>Board</th>
                    <th>Status</th>
                    <th>Expiration</th>
                    <th>Pass Rate</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${approvals.map(a => `
                    <tr>
                        <td>${getProgramName(a.program_id)}</td>
                        <td>${a.board_url ? `<a href="${a.board_url}" target="_blank">${a.board_name}</a>` : a.board_name}</td>
                        <td><span class="badge badge-${a.approved ? 'success' : 'danger'}">${a.approved ? 'Approved' : 'Not Approved'}</span></td>
                        <td class="${isExpiringSoon(a.expiration_date) ? 'text-warning' : ''}">${a.expiration_date ? formatDate(a.expiration_date) : 'N/A'}</td>
                        <td>
                            <span class="pass-rate ${a.current_pass_rate >= a.min_pass_rate ? 'passing' : 'failing'}">
                                ${a.current_pass_rate || 0}%
                            </span>
                            <span class="text-muted">/ ${a.min_pass_rate || 0}%</span>
                        </td>
                        <td>
                            <button class="btn btn-ghost btn-sm" onclick="deleteProgramApproval('${a.id}')" title="Delete">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                    <path d="M3 6h18M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                                </svg>
                            </button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function renderReadinessPanel() {
    const readiness = selectedStateData.readiness;
    const total = readiness.total || 0;

    document.getElementById('stateReadinessRing').innerHTML = renderReadinessRing(total);

    document.getElementById('readinessBreakdown').innerHTML = `
        <div class="breakdown-item">
            <div class="breakdown-label">Authorization</div>
            <div class="breakdown-value ${getScoreClass(readiness.authorization || 0)}">${readiness.authorization || 0}%</div>
        </div>
        <div class="breakdown-item">
            <div class="breakdown-label">Catalog</div>
            <div class="breakdown-value ${getScoreClass(readiness.catalog || 0)}">${readiness.catalog || 0}%</div>
        </div>
        <div class="breakdown-item">
            <div class="breakdown-label">Programs</div>
            <div class="breakdown-value ${getScoreClass(readiness.programs || 0)}">${readiness.programs || 0}%</div>
        </div>
    `;
}

function renderReadinessRing(score) {
    const circumference = 2 * Math.PI * 45;
    const offset = circumference - (score / 100) * circumference;
    const color = score >= 80 ? 'var(--success)' : score >= 50 ? 'var(--warning)' : 'var(--danger)';

    return `
        <svg width="120" height="120" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="45" fill="none" stroke="var(--bg-secondary)" stroke-width="8"/>
            <circle cx="50" cy="50" r="45" fill="none" stroke="${color}" stroke-width="8"
                    stroke-linecap="round" stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"
                    transform="rotate(-90 50 50)"/>
            <text x="50" y="50" text-anchor="middle" dy="0.35em"
                  style="font-size:24px;font-weight:700;fill:${color}">${score}%</text>
        </svg>
    `;
}

function renderSummaryCards() {
    const total = statesData.length;
    const authorized = statesData.filter(s => s.authorization_status === 'authorized').length;
    const pending = statesData.filter(s => s.authorization_status === 'pending').length;
    const expiring = statesData.filter(s => isExpiringSoon(s.renewal_date)).length;

    document.getElementById('totalStatesCount').textContent = total;
    document.getElementById('authorizedCount').textContent = authorized;
    document.getElementById('pendingCount').textContent = pending;
    document.getElementById('expiringCount').textContent = expiring;
}

function clearStateDetails() {
    document.getElementById('stateDetailsPanel').style.display = 'none';
    document.getElementById('noStateSelected').style.display = 'block';
}

// Selection
function selectState(stateCode) {
    selectedStateCode = stateCode;
    renderStatesList();
    loadStateDetails(stateCode);
}

function deleteCurrentState() {
    if (selectedStateCode) {
        deleteAuthorization(selectedStateCode);
    }
}

// Tab Navigation
function switchTab(tabName) {
    document.querySelectorAll('.state-tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    document.querySelector(`.state-tab[onclick="switchTab('${tabName}')"]`).classList.add('active');
    document.getElementById(`tab-${tabName}`).classList.add('active');
}

// Modal Functions
function showAddStateModal() {
    document.getElementById('addStateForm').reset();
    document.getElementById('addStateModal').style.display = 'flex';
}

function hideAddStateModal() {
    document.getElementById('addStateModal').style.display = 'none';
}

function showEditAuthModal() {
    if (!selectedStateData || !selectedStateData.authorization) return;
    const auth = selectedStateData.authorization;

    document.getElementById('editAuthStatus').value = auth.authorization_status || 'pending';
    document.getElementById('editSaraMember').checked = auth.sara_member || false;
    document.getElementById('editEffectiveDate').value = auth.effective_date || '';
    document.getElementById('editRenewalDate').value = auth.renewal_date || '';
    document.getElementById('editContactAgency').value = auth.contact_agency || '';
    document.getElementById('editContactUrl').value = auth.contact_url || '';
    document.getElementById('editNotes').value = auth.notes || '';

    document.getElementById('editAuthModal').style.display = 'flex';
}

function hideEditAuthModal() {
    document.getElementById('editAuthModal').style.display = 'none';
}

function showLoadPresetModal() {
    document.getElementById('loadPresetModal').style.display = 'flex';
}

function hideLoadPresetModal() {
    document.getElementById('loadPresetModal').style.display = 'none';
}

function showAddProgramModal() {
    document.getElementById('addProgramForm').reset();
    document.getElementById('addProgramModal').style.display = 'flex';
}

function hideAddProgramModal() {
    document.getElementById('addProgramModal').style.display = 'none';
}

// Form Handlers
function handleAddStateSubmit(e) {
    e.preventDefault();
    addState({
        state_code: document.getElementById('addStateCode').value,
        authorization_status: document.getElementById('addAuthStatus').value,
        sara_member: document.getElementById('addSaraMember').checked,
        effective_date: document.getElementById('addEffectiveDate').value || null,
        renewal_date: document.getElementById('addRenewalDate').value || null,
        contact_agency: document.getElementById('addContactAgency').value || null,
        contact_url: document.getElementById('addContactUrl').value || null,
        notes: document.getElementById('addNotes').value || null
    });
}

function handleEditAuthSubmit(e) {
    e.preventDefault();
    updateAuthorization(selectedStateCode, {
        authorization_status: document.getElementById('editAuthStatus').value,
        sara_member: document.getElementById('editSaraMember').checked,
        effective_date: document.getElementById('editEffectiveDate').value || null,
        renewal_date: document.getElementById('editRenewalDate').value || null,
        contact_agency: document.getElementById('editContactAgency').value || null,
        contact_url: document.getElementById('editContactUrl').value || null,
        notes: document.getElementById('editNotes').value || null
    });
}

function handleAddProgramSubmit(e) {
    e.preventDefault();
    addProgramApproval(selectedStateCode, {
        program_id: document.getElementById('addProgramId').value,
        board_name: document.getElementById('addBoardName').value,
        board_url: document.getElementById('addBoardUrl').value || null,
        approved: document.getElementById('addApproved').checked,
        approval_date: document.getElementById('addApprovalDate').value || null,
        expiration_date: document.getElementById('addExpirationDate').value || null,
        license_exam: document.getElementById('addLicenseExam').value || null,
        min_pass_rate: parseFloat(document.getElementById('addMinPassRate').value) || 0,
        current_pass_rate: parseFloat(document.getElementById('addCurrentPassRate').value) || 0
    });
}

// Helper Functions
function getStateName(code) {
    const state = US_STATES.find(s => s.code === code);
    return state ? state.name : code;
}

function getProgramName(programId) {
    const prog = programsData.find(p => p.id === programId);
    return prog ? prog.name : programId;
}

function getStatusBadgeClass(status) {
    switch (status) {
        case 'authorized':
        case 'satisfied':
            return 'success';
        case 'pending':
        case 'partial':
            return 'warning';
        case 'restricted':
        case 'denied':
        case 'missing':
            return 'danger';
        default:
            return 'secondary';
    }
}

function getStatusIcon(status) {
    switch (status) {
        case 'satisfied':
            return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="14" height="14"><polyline points="20 6 9 17 4 12"/></svg>';
        case 'partial':
            return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="14" height="14"><path d="M12 9v2m0 4h.01"/></svg>';
        default:
            return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" width="14" height="14"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>';
    }
}

function getScoreClass(score) {
    if (score >= 80) return 'good';
    if (score >= 50) return 'fair';
    return 'poor';
}

function formatDate(isoDate) {
    if (!isoDate) return '';
    const date = new Date(isoDate);
    return date.toLocaleDateString('en-US', {month: 'short', day: 'numeric', year: 'numeric'});
}

function daysUntil(isoDate) {
    if (!isoDate) return Infinity;
    const now = new Date();
    const target = new Date(isoDate);
    return Math.ceil((target - now) / (1000 * 60 * 60 * 24));
}

function isExpiringSoon(isoDate) {
    return daysUntil(isoDate) <= 90 && daysUntil(isoDate) > 0;
}

function showToast(message, type = 'info') {
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
    } else {
        console.log(`[${type}] ${message}`);
    }
}
