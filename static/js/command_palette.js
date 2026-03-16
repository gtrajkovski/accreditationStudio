/**
 * Global Command Palette for AccreditAI
 *
 * Keyboard shortcuts:
 * - Ctrl+K / Cmd+K: Open palette
 * - /: Focus search
 * - A: Run audit
 * - C: Run consistency check
 * - F: Fix finding
 * - E: Evidence explorer
 * - D: Documents
 * - W: Work queue
 * - S: Standards
 * - P: Packets
 * - ?: Show shortcuts
 */

window.CommandPalette = (function() {
    'use strict';

    // State
    let isOpen = false;
    let selectedIndex = 0;
    let filteredCommands = [];
    let allCommands = [];
    let context = {};

    // Two-key sequence state
    let pendingKey = null;
    let pendingKeyTime = 0;
    const KEY_SEQUENCE_TIMEOUT = 800; // ms

    // Dual-mode state (search vs command)
    const MODES = {
        SEARCH: 'search',
        COMMAND: 'command'
    };
    let currentMode = MODES.SEARCH;
    let searchResults = [];
    let currentSearchId = 0;  // For race condition prevention
    let searchTimeout = null;
    const DEBOUNCE_MS = 250;  // 200-300ms per CONTEXT.md

    // Recent searches (localStorage per institution)
    const RECENT_SEARCHES_KEY = 'accreditai_recent_searches';
    const MAX_RECENT = 5;

    // DOM elements
    let paletteEl = null;
    let inputEl = null;
    let resultsEl = null;
    let shortcutsEl = null;

    // Default commands (will be enriched from server)
    const defaultCommands = [
        // Navigation
        {
            id: 'nav_dashboard',
            title_key: 'commands.nav_dashboard',
            category_key: 'commands.category_navigation',
            shortcut: 'G D',
            icon: 'home',
            action_type: 'navigate',
            action_target: '/'
        },
        {
            id: 'nav_command_center',
            title_key: 'commands.nav_command_center',
            category_key: 'commands.category_navigation',
            shortcut: null,
            icon: 'home',
            action_type: 'navigate',
            action_target: '/institutions/{institution_id}'
        },
        {
            id: 'nav_work_queue',
            title_key: 'commands.nav_work_queue',
            category_key: 'commands.category_navigation',
            shortcut: 'W',
            icon: 'list',
            action_type: 'navigate',
            action_target: '/institutions/{institution_id}/work-queue'
        },
        {
            id: 'nav_documents',
            title_key: 'commands.nav_documents',
            category_key: 'commands.category_navigation',
            shortcut: 'D',
            icon: 'file',
            action_type: 'navigate',
            action_target: '/institutions/{institution_id}/documents'
        },
        {
            id: 'nav_evidence',
            title_key: 'commands.nav_evidence',
            category_key: 'commands.category_navigation',
            shortcut: 'E',
            icon: 'search',
            action_type: 'navigate',
            action_target: '/institutions/{institution_id}/evidence'
        },
        {
            id: 'nav_compliance',
            title_key: 'commands.nav_compliance',
            category_key: 'commands.category_navigation',
            shortcut: 'G C',
            icon: 'check',
            action_type: 'navigate',
            action_target: '/institutions/{institution_id}/compliance',
            when: { has_institution: true }
        },
        {
            id: 'nav_standards',
            title_key: 'commands.nav_standards',
            category_key: 'commands.category_navigation',
            shortcut: 'S',
            icon: 'book',
            action_type: 'navigate',
            action_target: '/standards'
        },
        {
            id: 'nav_packets',
            title_key: 'commands.nav_packets',
            category_key: 'commands.category_navigation',
            shortcut: 'P',
            icon: 'package',
            action_type: 'navigate',
            action_target: '/institutions/{institution_id}/packets'
        },
        {
            id: 'nav_settings',
            title_key: 'commands.nav_settings',
            category_key: 'commands.category_navigation',
            shortcut: null,
            icon: 'settings',
            action_type: 'navigate',
            action_target: '/settings'
        },

        // Actions
        {
            id: 'action_run_audit',
            title_key: 'commands.action_run_audit',
            description_key: 'commands.action_run_audit_desc',
            category_key: 'commands.category_actions',
            shortcut: 'A',
            icon: 'play',
            action_type: 'api_post',
            action_target: '/api/audits/run',
            when: { has_institution: true }
        },
        {
            id: 'action_run_consistency',
            title_key: 'commands.action_run_consistency',
            description_key: 'commands.action_run_consistency_desc',
            category_key: 'commands.category_actions',
            shortcut: 'C',
            icon: 'refresh',
            action_type: 'api_post',
            action_target: '/api/consistency/run',
            when: { has_institution: true }
        },
        {
            id: 'action_fix_finding',
            title_key: 'commands.action_fix_finding',
            category_key: 'commands.category_actions',
            shortcut: 'F',
            icon: 'tool',
            action_type: 'api_post',
            action_target: '/api/remediation/generate',
            when: { has_finding: true }
        },
        {
            id: 'action_upload_doc',
            title_key: 'commands.action_upload_doc',
            category_key: 'commands.category_actions',
            shortcut: 'U',
            icon: 'upload',
            action_type: 'navigate',
            action_target: '/institutions/{institution_id}/documents?action=upload',
            when: { has_institution: true }
        },
        {
            id: 'action_run_autopilot',
            title_key: 'commands.action_run_autopilot',
            description_key: 'commands.action_run_autopilot_desc',
            category_key: 'commands.category_actions',
            shortcut: null,
            icon: 'zap',
            action_type: 'api_post',
            action_target: '/api/institutions/{institution_id}/autopilot/run-now',
            when: { has_institution: true }
        },

        // Help
        {
            id: 'help_shortcuts',
            title_key: 'commands.help_shortcuts',
            category_key: 'commands.category_help',
            shortcut: '?',
            icon: 'help',
            action_type: 'open_modal',
            action_target: 'shortcuts'
        }
    ];

    // Icons (simple SVG paths)
    const icons = {
        home: '<path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
        list: '<line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>',
        file: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>',
        search: '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
        check: '<polyline points="20 6 9 17 4 12"/>',
        book: '<path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>',
        package: '<line x1="16.5" y1="9.4" x2="7.5" y2="4.21"/><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
        settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"/>',
        play: '<polygon points="5 3 19 12 5 21 5 3"/>',
        refresh: '<polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>',
        tool: '<path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/>',
        upload: '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
        zap: '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
        help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>'
    };

    /**
     * Initialize command palette
     */
    function init() {
        paletteEl = document.getElementById('command-palette');
        inputEl = document.getElementById('command-palette-input');
        resultsEl = document.getElementById('command-palette-results');
        shortcutsEl = document.getElementById('shortcuts-modal');

        if (!paletteEl || !inputEl || !resultsEl) {
            console.warn('Command palette elements not found');
            return;
        }

        // Read context from page
        const contextEl = document.getElementById('page-context');
        if (contextEl) {
            try {
                context = JSON.parse(contextEl.textContent);
            } catch (e) {
                context = {};
            }
        }

        // Load commands
        allCommands = defaultCommands;
        filteredCommands = filterCommands('');

        // Event listeners
        inputEl.addEventListener('input', handleInput);
        inputEl.addEventListener('keydown', handleKeydown);

        // Global keyboard shortcuts
        document.addEventListener('keydown', handleGlobalKeydown);

        // Load commands from server (optional enhancement)
        loadServerCommands();
    }

    /**
     * Load commands from server
     */
    async function loadServerCommands() {
        try {
            const response = await fetch('/api/ui/commands');
            if (response.ok) {
                const data = await response.json();
                if (data.commands) {
                    allCommands = [...defaultCommands, ...data.commands];
                }
            }
        } catch (e) {
            // Use default commands
        }
    }

    /**
     * localStorage helpers for recent searches
     */
    function saveRecentSearch(query) {
        if (!context.institution_id || !query || query.length < 2) return;
        const key = `${RECENT_SEARCHES_KEY}_${context.institution_id}`;
        let recent = JSON.parse(localStorage.getItem(key) || '[]');
        recent = recent.filter(r => r !== query);  // Remove duplicates
        recent.unshift(query);
        recent = recent.slice(0, MAX_RECENT);
        localStorage.setItem(key, JSON.stringify(recent));
    }

    function getRecentSearches() {
        if (!context.institution_id) return [];
        const key = `${RECENT_SEARCHES_KEY}_${context.institution_id}`;
        return JSON.parse(localStorage.getItem(key) || '[]');
    }

    /**
     * Open command palette
     */
    function open() {
        if (isOpen) return;
        isOpen = true;
        paletteEl.style.display = 'flex';
        inputEl.value = '';
        inputEl.focus();
        currentMode = MODES.SEARCH;
        selectedIndex = 0;
        filteredCommands = [];
        searchResults = [];
        renderRecentSearches();  // Show recent on open
    }

    /**
     * Close command palette
     */
    function close() {
        if (!isOpen) return;
        isOpen = false;
        paletteEl.style.display = 'none';
        inputEl.value = '';
    }

    /**
     * Toggle palette
     */
    function toggle() {
        if (isOpen) {
            close();
        } else {
            open();
        }
    }

    /**
     * Show shortcuts modal
     */
    function showShortcuts() {
        close();
        if (shortcutsEl) {
            shortcutsEl.style.display = 'flex';
        }
    }

    /**
     * Close shortcuts modal
     */
    function closeShortcuts() {
        if (shortcutsEl) {
            shortcutsEl.style.display = 'none';
        }
    }

    /**
     * Filter commands by query
     */
    function filterCommands(query) {
        query = query.toLowerCase().trim();

        return allCommands.filter(cmd => {
            // Check "when" conditions
            if (cmd.when) {
                if (cmd.when.has_institution && !context.institution_id) return false;
                if (cmd.when.has_document && !context.document_id) return false;
                if (cmd.when.has_finding && !context.finding_id) return false;
                if (cmd.when.page_type && context.page_type !== cmd.when.page_type) return false;
            }

            // Filter by query
            if (!query) return true;

            const title = t(cmd.title_key).toLowerCase();
            const desc = cmd.description_key ? t(cmd.description_key).toLowerCase() : '';

            return title.includes(query) || desc.includes(query) || cmd.id.includes(query);
        });
    }

    /**
     * Get translated string
     */
    function t(key) {
        if (window.AccreditAI && window.AccreditAI.i18n) {
            return window.AccreditAI.i18n.t(key);
        }
        // Fallback: return key without prefix
        return key.split('.').pop().replace(/_/g, ' ');
    }

    /**
     * Render command results
     */
    function render() {
        if (filteredCommands.length === 0) {
            resultsEl.innerHTML = `<div class="command-empty">${t('commands.no_results')}</div>`;
            return;
        }

        // Group by category
        const groups = {};
        filteredCommands.forEach(cmd => {
            const cat = cmd.category_key || 'commands.category_other';
            if (!groups[cat]) groups[cat] = [];
            groups[cat].push(cmd);
        });

        let html = '';
        let index = 0;

        for (const [category, commands] of Object.entries(groups)) {
            html += `<div class="command-group">`;
            html += `<div class="command-group-title">${t(category)}</div>`;

            commands.forEach(cmd => {
                const isSelected = index === selectedIndex;
                const icon = icons[cmd.icon] || icons.help;

                html += `
                    <div class="command-item ${isSelected ? 'selected' : ''}"
                         data-index="${index}"
                         onclick="CommandPalette.execute(${index})">
                        <svg class="command-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            ${icon}
                        </svg>
                        <div class="command-item-content">
                            <div class="command-item-title">${t(cmd.title_key)}</div>
                            ${cmd.description_key ? `<div class="command-item-description">${t(cmd.description_key)}</div>` : ''}
                        </div>
                        ${cmd.shortcut ? `<div class="command-item-shortcut"><kbd>${cmd.shortcut}</kbd></div>` : ''}
                    </div>
                `;
                index++;
            });

            html += `</div>`;
        }

        resultsEl.innerHTML = html;
    }

    /**
     * Handle input changes - dual-mode detection
     */
    function handleInput(e) {
        const query = e.target.value;

        // Detect mode
        if (query.startsWith('>')) {
            currentMode = MODES.COMMAND;
            const commandQuery = query.slice(1).trim();
            filteredCommands = filterCommands(commandQuery);
            searchResults = [];
            selectedIndex = 0;
            render();
        } else {
            currentMode = MODES.SEARCH;
            filteredCommands = [];

            if (query.length === 0) {
                renderRecentSearches();
            } else if (query.length === 1) {
                renderMinLengthHint();
            } else {
                // Debounced search
                if (searchTimeout) clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => search(query), DEBOUNCE_MS);
            }
        }
    }

    /**
     * Perform debounced search with race condition handling
     */
    async function search(query) {
        if (!context.institution_id) return;

        const searchId = ++currentSearchId;
        renderLoading();

        try {
            const response = await fetch(
                `/api/institutions/${context.institution_id}/global-search`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, limit: 20 })
                }
            );

            if (searchId !== currentSearchId) return;  // Stale result

            const data = await response.json();
            searchResults = data.results || [];
            selectedIndex = 0;
            saveRecentSearch(query);
            renderSearchResults(data);
        } catch (error) {
            if (searchId !== currentSearchId) return;
            renderSearchError();
        }
    }

    /**
     * Handle keyboard navigation in palette
     */
    function handleKeydown(e) {
        // Number keys for recent searches
        if (currentMode === MODES.SEARCH && searchResults.length > 0) {
            if (e.key >= '1' && e.key <= '5') {
                const idx = parseInt(e.key) - 1;
                if (searchResults[idx] && searchResults[idx].type === 'recent') {
                    e.preventDefault();
                    executeRecentSearch(searchResults[idx].query);
                    return;
                }
            }
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                const maxIndex = currentMode === MODES.COMMAND ? filteredCommands.length - 1 : searchResults.length - 1;
                selectedIndex = Math.min(selectedIndex + 1, maxIndex);
                if (currentMode === MODES.COMMAND) {
                    render();
                } else {
                    // Re-render search results with new selection
                    const recent = getRecentSearches();
                    if (searchResults.length > 0 && searchResults[0].type === 'recent') {
                        renderRecentSearches();
                    }
                }
                break;

            case 'ArrowUp':
                e.preventDefault();
                selectedIndex = Math.max(selectedIndex - 1, 0);
                if (currentMode === MODES.COMMAND) {
                    render();
                } else {
                    // Re-render search results with new selection
                    const recent = getRecentSearches();
                    if (searchResults.length > 0 && searchResults[0].type === 'recent') {
                        renderRecentSearches();
                    }
                }
                break;

            case 'Enter':
                e.preventDefault();
                execute(selectedIndex);
                break;

            case 'Escape':
                e.preventDefault();
                close();
                break;
        }
    }

    /**
     * Handle global keyboard shortcuts
     */
    function handleGlobalKeydown(e) {
        // Ignore if typing in input/textarea
        const tag = e.target.tagName.toLowerCase();
        const isTyping = tag === 'input' || tag === 'textarea' || e.target.isContentEditable;

        // Ctrl+K / Cmd+K always opens palette
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            toggle();
            return;
        }

        // Escape closes modals
        if (e.key === 'Escape') {
            if (shortcutsEl && shortcutsEl.style.display !== 'none') {
                closeShortcuts();
                return;
            }
            if (isOpen) {
                close();
                return;
            }
        }

        // Don't handle other shortcuts if typing
        if (isTyping) return;

        // Check for pending key sequence
        const now = Date.now();
        const hasPendingKey = pendingKey && (now - pendingKeyTime < KEY_SEQUENCE_TIMEOUT);

        // Handle G-prefix sequences
        if (hasPendingKey && pendingKey === 'g') {
            pendingKey = null;
            switch (e.key.toLowerCase()) {
                case 'd':
                    e.preventDefault();
                    executeById('nav_dashboard');
                    return;
                case 'c':
                    e.preventDefault();
                    if (context.institution_id) {
                        executeById('nav_compliance');
                    }
                    return;
            }
        }

        // Single key shortcuts
        switch (e.key) {
            case '/':
                e.preventDefault();
                open();
                break;

            case '?':
                e.preventDefault();
                showShortcuts();
                break;

            case 'g':
            case 'G':
                // Start G-prefix sequence
                e.preventDefault();
                pendingKey = 'g';
                pendingKeyTime = now;
                break;

            case 'a':
            case 'A':
                e.preventDefault();
                executeById('action_run_audit');
                break;

            case 'c':
            case 'C':
                e.preventDefault();
                executeById('action_run_consistency');
                break;

            case 'f':
            case 'F':
                if (context.finding_id) {
                    e.preventDefault();
                    executeById('action_fix_finding');
                }
                break;

            case 'w':
            case 'W':
                e.preventDefault();
                executeById('nav_work_queue');
                break;

            case 'd':
            case 'D':
                e.preventDefault();
                executeById('nav_documents');
                break;

            case 'e':
            case 'E':
                e.preventDefault();
                executeById('nav_evidence');
                break;

            case 's':
            case 'S':
                e.preventDefault();
                executeById('nav_standards');
                break;

            case 'p':
            case 'P':
                e.preventDefault();
                executeById('nav_packets');
                break;

            case 'u':
            case 'U':
                e.preventDefault();
                executeById('action_upload_doc');
                break;
        }
    }

    /**
     * Execute command or search result by index
     */
    function execute(index) {
        if (currentMode === MODES.COMMAND) {
            const cmd = filteredCommands[index];
            if (cmd) {
                close();
                executeCommand(cmd);
            }
        } else {
            const result = searchResults[index];
            if (result) {
                close();
                openSearchResult(result);
            }
        }
    }

    /**
     * Execute a recent search
     */
    function executeRecentSearch(query) {
        inputEl.value = query;
        search(query);
    }

    /**
     * Open a search result
     */
    function openSearchResult(item) {
        switch (item.source_type) {
            case 'document':
                window.location.href = `/institutions/${context.institution_id}/documents?highlight=${item.source_id}`;
                break;
            case 'standard':
                window.location.href = `/standards?highlight=${item.source_id}`;
                break;
            case 'finding':
                window.location.href = `/institutions/${context.institution_id}/compliance?finding=${item.source_id}`;
                break;
            case 'faculty':
                window.location.href = `/institutions/${context.institution_id}/faculty?highlight=${item.source_id}`;
                break;
            case 'knowledge_graph':
                window.location.href = `/institutions/${context.institution_id}/knowledge-graph?entity=${item.source_id}`;
                break;
            case 'truth_index':
                // Show in preview or navigate to relevant page
                console.log('Truth Index result:', item);
                break;
        }
    }

    /**
     * Execute command by ID
     */
    function executeById(id) {
        const cmd = allCommands.find(c => c.id === id);
        if (cmd) {
            executeCommand(cmd);
        }
    }

    /**
     * Execute a command
     */
    async function executeCommand(cmd) {
        // Replace placeholders in target
        let target = cmd.action_target;
        if (target) {
            target = target.replace('{institution_id}', context.institution_id || '');
            target = target.replace('{document_id}', context.document_id || '');
            target = target.replace('{finding_id}', context.finding_id || '');
            target = target.replace('{packet_id}', context.packet_id || '');
        }

        switch (cmd.action_type) {
            case 'navigate':
                window.location.href = target;
                break;

            case 'api_post':
                try {
                    const payload = {
                        institution_id: context.institution_id,
                        document_id: context.document_id,
                        finding_id: context.finding_id
                    };

                    const response = await fetch(target, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });

                    if (response.ok) {
                        window.toast && window.toast.success(t('commands.action_success'));
                    } else {
                        window.toast && window.toast.error(t('commands.action_failed'));
                    }
                } catch (e) {
                    window.toast && window.toast.error(t('commands.action_failed'));
                }
                break;

            case 'open_modal':
                if (target === 'shortcuts') {
                    showShortcuts();
                }
                break;
        }
    }

    /**
     * Helper functions for rendering
     */
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function escapeAttr(text) {
        return text.replace(/'/g, "\\'").replace(/"/g, '\\"');
    }

    function truncate(text, len) {
        if (!text) return '';
        return text.length > len ? text.slice(0, len) + '...' : text;
    }

    function getSourceIcon(type) {
        const iconPaths = {
            document: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>',
            standard: '<path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/>',
            finding: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
            faculty: '<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>',
            truth_index: '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
            knowledge_graph: '<circle cx="12" cy="12" r="3"/><line x1="12" y1="3" x2="12" y2="9"/><line x1="12" y1="15" x2="12" y2="21"/>'
        };
        return iconPaths[type] || iconPaths.document;
    }

    function formatSourceType(type) {
        const labels = {
            document: 'Doc',
            standard: 'Std',
            finding: 'Find',
            faculty: 'Fac',
            truth_index: 'Fact',
            knowledge_graph: 'KG'
        };
        return labels[type] || type;
    }

    /**
     * Render recent searches
     */
    function renderRecentSearches() {
        const recent = getRecentSearches();

        if (recent.length === 0) {
            resultsEl.innerHTML = `
                <div class="command-empty">
                    <p>${t('commands.search_hint')}</p>
                    <span class="command-hint-text">${t('commands.type_to_search')}</span>
                </div>
            `;
            return;
        }

        let html = '<div class="command-group">';
        html += `<div class="command-group-title">${t('commands.recent_searches')}</div>`;

        recent.forEach((query, idx) => {
            const isSelected = idx === selectedIndex;
            html += `
                <div class="command-item ${isSelected ? 'selected' : ''}"
                     data-index="${idx}"
                     onclick="CommandPalette.executeRecentSearch('${escapeAttr(query)}')">
                    <svg class="command-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <div class="command-item-content">
                        <div class="command-item-title">${escapeHtml(query)}</div>
                    </div>
                    <span class="command-item-shortcut"><kbd>${idx + 1}</kbd></span>
                </div>
            `;
        });

        html += '</div>';
        resultsEl.innerHTML = html;
        searchResults = recent.map(q => ({ type: 'recent', query: q }));
    }

    /**
     * Render min length hint
     */
    function renderMinLengthHint() {
        resultsEl.innerHTML = `
            <div class="command-empty">
                <p>${t('commands.min_length_hint')}</p>
            </div>
        `;
        searchResults = [];
    }

    /**
     * Render loading state
     */
    function renderLoading() {
        resultsEl.innerHTML = `
            <div class="command-loading">
                <div class="spinner"></div>
                <span>${t('commands.searching')}</span>
            </div>
        `;
    }

    /**
     * Render search results
     */
    function renderSearchResults(data) {
        if (!data.results || data.results.length === 0) {
            resultsEl.innerHTML = `
                <div class="command-empty">
                    <p>${t('commands.no_results')}</p>
                    <span class="command-hint-text">${t('commands.try_different')}</span>
                </div>
            `;
            return;
        }

        // For now, render flat list - tabs will be added in 13-03
        let html = '<div class="command-group">';
        html += `<div class="command-group-title">${data.total} ${t('commands.results')} (${data.query_time_ms}ms)</div>`;

        data.results.forEach((item, idx) => {
            const isSelected = idx === selectedIndex;
            const citation = item.citation || {};
            const sourceIcon = getSourceIcon(item.source_type);

            html += `
                <div class="command-item search-result ${isSelected ? 'selected' : ''}"
                     data-index="${idx}"
                     onclick="CommandPalette.execute(${idx})">
                    <svg class="command-item-icon source-${item.source_type}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        ${sourceIcon}
                    </svg>
                    <div class="command-item-content">
                        <div class="command-item-title">${escapeHtml(item.title)}</div>
                        <div class="command-item-snippet">${escapeHtml(truncate(item.snippet, 80))}</div>
                        <div class="command-item-citation">
                            ${citation.document ? `<span>${escapeHtml(citation.document)}</span>` : ''}
                            ${citation.page ? `<span>p. ${citation.page}</span>` : ''}
                        </div>
                    </div>
                    <div class="command-item-source">${formatSourceType(item.source_type)}</div>
                </div>
            `;
        });

        html += '</div>';
        resultsEl.innerHTML = html;
    }

    /**
     * Render search error
     */
    function renderSearchError() {
        resultsEl.innerHTML = `
            <div class="command-empty">
                <p>${t('commands.search_error')}</p>
            </div>
        `;
    }

    // Public API
    return {
        init,
        open,
        close,
        toggle,
        execute,
        executeRecentSearch,
        showShortcuts,
        closeShortcuts
    };
})();

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    CommandPalette.init();
});
