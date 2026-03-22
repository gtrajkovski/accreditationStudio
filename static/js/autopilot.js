/**
 * Autopilot JavaScript Controller
 * Handles autopilot operations: run-now, SSE progress, brief loading, settings management
 */

class AutopilotController {
  constructor(institutionId) {
    this.institutionId = institutionId;
    this.eventSource = null;
    this.briefDate = null;
    this.config = null;
  }

  /**
   * Initialize the controller
   */
  async init() {
    if (!this.institutionId) {
      console.warn('AutopilotController: No institution ID provided');
      return;
    }

    await this.loadLatestRun();
    await this.loadLatestBrief();
  }

  // =========================================================================
  // Run Now
  // =========================================================================

  /**
   * Trigger an autopilot run and connect to SSE for progress
   * @param {Object} options - Run options
   * @param {Function} options.onProgress - Progress callback (message, percent)
   * @param {Function} options.onComplete - Complete callback (data)
   * @param {Function} options.onError - Error callback (error)
   */
  async runNow({ onProgress, onComplete, onError } = {}) {
    try {
      // Start the async run
      const res = await fetch(`/api/autopilot/institutions/${this.institutionId}/run-now`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.error || 'Failed to start autopilot');
      }

      const data = await res.json();
      const runId = data.run_id;

      if (!runId) {
        throw new Error('No run ID returned');
      }

      // Connect to SSE
      this.connectSSE(runId, { onProgress, onComplete, onError });

      return { runId, status: 'running' };

    } catch (error) {
      console.error('Autopilot runNow error:', error);
      if (onError) onError(error);
      throw error;
    }
  }

  /**
   * Connect to SSE stream for progress updates
   */
  connectSSE(runId, { onProgress, onComplete, onError }) {
    // Close existing connection
    this.disconnectSSE();

    const url = `/api/autopilot/institutions/${this.institutionId}/runs/${runId}/progress`;
    this.eventSource = new EventSource(url);

    this.eventSource.addEventListener('progress', (e) => {
      try {
        const data = JSON.parse(e.data);
        if (onProgress) {
          onProgress(data.message, data.percent);
        }
      } catch (err) {
        console.error('Error parsing progress event:', err);
      }
    });

    this.eventSource.addEventListener('complete', (e) => {
      try {
        const data = JSON.parse(e.data);
        this.disconnectSSE();
        if (onComplete) {
          onComplete(data);
        }
      } catch (err) {
        console.error('Error parsing complete event:', err);
      }
    });

    this.eventSource.addEventListener('error', (e) => {
      let errorMsg = 'Connection error';
      try {
        if (e.data) {
          const data = JSON.parse(e.data);
          errorMsg = data.error || errorMsg;
        }
      } catch (err) {}

      this.disconnectSSE();
      if (onError) {
        onError(new Error(errorMsg));
      }
    });

    this.eventSource.onerror = () => {
      // Connection lost
      this.disconnectSSE();
    };
  }

  /**
   * Disconnect from SSE stream
   */
  disconnectSSE() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  // =========================================================================
  // Latest Run
  // =========================================================================

  /**
   * Load the latest autopilot run
   */
  async loadLatestRun() {
    try {
      const res = await fetch(`/api/autopilot/institutions/${this.institutionId}/latest`);
      if (!res.ok) return null;

      const data = await res.json();
      return data.run || null;

    } catch (error) {
      console.error('Error loading latest run:', error);
      return null;
    }
  }

  /**
   * Get run history
   * @param {number} limit - Number of runs to fetch
   */
  async getHistory(limit = 20) {
    try {
      const res = await fetch(`/api/autopilot/institutions/${this.institutionId}/history?limit=${limit}`);
      if (!res.ok) return [];

      const data = await res.json();
      return data.runs || [];

    } catch (error) {
      console.error('Error loading run history:', error);
      return [];
    }
  }

  // =========================================================================
  // Morning Brief
  // =========================================================================

  /**
   * Load the latest morning brief
   */
  async loadLatestBrief() {
    try {
      const res = await fetch(`/api/autopilot/institutions/${this.institutionId}/briefs/latest`);
      if (!res.ok) return null;

      const data = await res.json();
      if (data.brief) {
        this.briefDate = data.brief.date;
        return data.brief;
      }
      return null;

    } catch (error) {
      console.error('Error loading brief:', error);
      return null;
    }
  }

  /**
   * List available briefs
   * @param {number} days - Number of days to look back
   */
  async listBriefs(days = 30) {
    try {
      const res = await fetch(`/api/autopilot/institutions/${this.institutionId}/briefs?days=${days}`);
      if (!res.ok) return [];

      const data = await res.json();
      return data.briefs || [];

    } catch (error) {
      console.error('Error listing briefs:', error);
      return [];
    }
  }

  /**
   * Download a brief
   * @param {string} date - Brief date (YYYY-MM-DD)
   */
  downloadBrief(date = null) {
    const briefDate = date || this.briefDate;
    if (!briefDate) {
      console.error('No brief date available');
      return;
    }

    window.location.href = `/api/autopilot/institutions/${this.institutionId}/briefs/${briefDate}/download`;
  }

  /**
   * Parse brief content to extract blockers and actions
   * @param {string} content - Brief markdown content
   */
  parseBriefContent(content) {
    const lines = content.split('\n');
    const blockers = [];
    const actions = [];
    let inBlockers = false;
    let inActions = false;

    for (const line of lines) {
      const lower = line.toLowerCase();

      // Detect section headers
      if (lower.includes('blocker') || lower.includes('critical issue')) {
        inBlockers = true;
        inActions = false;
        continue;
      }
      if (lower.includes('next action') || lower.includes('recommended') || lower.includes('next best')) {
        inBlockers = false;
        inActions = true;
        continue;
      }

      // Parse list items
      const trimmed = line.trim();
      if (trimmed.startsWith('-') || trimmed.startsWith('*') || /^\d+\./.test(trimmed)) {
        const text = trimmed.replace(/^[-*]\s*/, '').replace(/^\d+\.\s*/, '');
        if (text) {
          if (inBlockers && blockers.length < 3) {
            // Try to detect severity
            let severity = 'medium';
            if (lower.includes('critical')) severity = 'critical';
            else if (lower.includes('high') || lower.includes('urgent')) severity = 'high';
            else if (lower.includes('low') || lower.includes('minor')) severity = 'low';

            blockers.push({ text, severity });
          } else if (inActions && actions.length < 3) {
            actions.push({ text });
          }
        }
      }
    }

    return { blockers, actions };
  }

  // =========================================================================
  // Settings
  // =========================================================================

  /**
   * Load autopilot config
   */
  async loadConfig() {
    try {
      const res = await fetch(`/api/autopilot/institutions/${this.institutionId}/config`);
      if (!res.ok) return null;

      this.config = await res.json();
      return this.config;

    } catch (error) {
      console.error('Error loading config:', error);
      return null;
    }
  }

  /**
   * Save autopilot config
   * @param {Object} config - Configuration object
   */
  async saveConfig(config) {
    try {
      const res = await fetch(`/api/autopilot/institutions/${this.institutionId}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.error || 'Failed to save config');
      }

      const data = await res.json();
      this.config = data.config;
      return data;

    } catch (error) {
      console.error('Error saving config:', error);
      throw error;
    }
  }

  // =========================================================================
  // Utilities
  // =========================================================================

  /**
   * Format a date string for display
   */
  formatDate(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString();
  }

  /**
   * Format a duration in seconds
   */
  formatDuration(seconds) {
    if (!seconds && seconds !== 0) return '-';
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  }

  /**
   * Calculate readiness delta
   */
  getReadinessDelta(before, after) {
    if (before === null || after === null) return null;
    return after - before;
  }

  /**
   * Format readiness delta for display
   */
  formatReadinessDelta(delta) {
    if (delta === null) return '';
    const sign = delta > 0 ? '+' : '';
    const cls = delta > 0 ? 'positive' : delta < 0 ? 'negative' : 'neutral';
    return { text: `${sign}${delta}`, className: cls };
  }
}

// =========================================================================
// Export / Global
// =========================================================================

// Make available globally
window.AutopilotController = AutopilotController;

// Auto-init if institution ID is available on page
document.addEventListener('DOMContentLoaded', () => {
  // Check for institution ID in various places
  const pageContext = document.getElementById('page-context');
  let institutionId = null;

  if (pageContext) {
    try {
      const ctx = JSON.parse(pageContext.textContent);
      institutionId = ctx.institution_id;
    } catch (e) {}
  }

  // Also check for global INSTITUTION_ID
  if (!institutionId && window.INSTITUTION_ID) {
    institutionId = window.INSTITUTION_ID;
  }

  // Initialize if we have an ID
  if (institutionId) {
    window.autopilot = new AutopilotController(institutionId);
    // Don't auto-init here - let the page do it when ready
  }
});
