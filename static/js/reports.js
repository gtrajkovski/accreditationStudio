/**
 * Reports Dashboard Manager
 * Handles executive summary visualization, data loading, and PDF generation
 */

class ReportsManager {
  constructor() {
    this.institutionId = window.INSTITUTION_ID;
    this.charts = {
      readiness: null,
      findings: null
    };
    this.readinessData = null;
    this.findingsData = null;
  }

  /**
   * Initialize dashboard
   */
  async init() {
    if (!this.institutionId) {
      this.showToast('Please select an institution first', 'warning');
      return;
    }

    await this.loadReadiness();
    await this.loadFindings();
    await this.loadReportHistory();
    this.initCharts();
    this.attachEventListeners();
  }

  /**
   * Load readiness scores
   */
  async loadReadiness() {
    try {
      const response = await fetch(`/api/readiness/institutions/${this.institutionId}`);
      if (!response.ok) throw new Error('Failed to load readiness data');

      this.readinessData = await response.json();
      this.populateHeroMetrics(this.readinessData);
    } catch (error) {
      console.error('Error loading readiness:', error);
      this.showToast('Failed to load readiness data', 'error');
    }
  }

  /**
   * Load findings data for severity chart
   */
  async loadFindings() {
    try {
      const response = await fetch(`/api/audits/institutions/${this.institutionId}/findings`);
      if (!response.ok) {
        // If no findings endpoint, use mock data
        this.findingsData = { critical: 0, high: 0, medium: 0, low: 0 };
        return;
      }

      const findings = await response.json();

      // Aggregate findings by severity
      this.findingsData = {
        critical: findings.filter(f => f.severity === 'critical').length,
        high: findings.filter(f => f.severity === 'high').length,
        medium: findings.filter(f => f.severity === 'medium').length,
        low: findings.filter(f => f.severity === 'low').length
      };
    } catch (error) {
      console.error('Error loading findings:', error);
      // Use default values if endpoint doesn't exist
      this.findingsData = { critical: 0, high: 0, medium: 0, low: 0 };
    }
  }

  /**
   * Load report history
   */
  async loadReportHistory() {
    try {
      const response = await fetch(`/api/reports/institutions/${this.institutionId}`);
      if (!response.ok) throw new Error('Failed to load report history');

      const reports = await response.json();
      this.populateReportTable(reports);
    } catch (error) {
      console.error('Error loading report history:', error);
      // Keep empty state visible
    }
  }

  /**
   * Populate hero metrics cards
   */
  populateHeroMetrics(data) {
    // Overall readiness (primary metric)
    const readinessScore = Math.round(data.total || 0);
    document.getElementById('readiness-score').textContent = readinessScore;

    // Color-code based on score
    const scoreCard = document.querySelector('.metric-card.primary');
    if (readinessScore >= 80) {
      scoreCard.style.borderColor = 'var(--success)';
    } else if (readinessScore >= 60) {
      scoreCard.style.borderColor = 'var(--warning)';
    } else {
      scoreCard.style.borderColor = 'var(--error)';
    }

    // Calculate trend (compare to historical data if available)
    // For now, show placeholder - would need historical data endpoint
    this.updateTrend(readinessScore);

    // Sub-scores
    this.updateSubScore('compliance', data.compliance || 0);
    this.updateSubScore('evidence', data.evidence || 0);
    this.updateSubScore('documents', data.documents || 0);
    this.updateSubScore('consistency', data.consistency || 0);
  }

  /**
   * Update individual sub-score card
   */
  updateSubScore(name, value) {
    const score = Math.round(value);
    document.getElementById(`${name}-score`).textContent = score;
    document.getElementById(`${name}-progress`).style.width = `${score}%`;

    // Color-code progress bar
    const progressBar = document.getElementById(`${name}-progress`);
    if (score >= 80) {
      progressBar.style.background = 'linear-gradient(90deg, var(--success), var(--success-hover))';
    } else if (score >= 60) {
      progressBar.style.background = 'linear-gradient(90deg, var(--warning), var(--warning-hover))';
    } else {
      progressBar.style.background = 'linear-gradient(90deg, var(--error), var(--error-hover))';
    }
  }

  /**
   * Update trend indicator
   */
  updateTrend(currentScore) {
    const trendElement = document.getElementById('readiness-trend');

    // Would compare with historical data - for now, show neutral
    // Example: const lastMonthScore = await this.getHistoricalScore();
    // const change = currentScore - lastMonthScore;

    // Placeholder: show trend based on absolute score
    if (currentScore >= 75) {
      trendElement.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>
          <polyline points="17 6 23 6 23 12"/>
        </svg>
        On Track
      `;
      trendElement.className = 'metric-trend positive';
    } else if (currentScore >= 50) {
      trendElement.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        Stable
      `;
      trendElement.className = 'metric-trend';
    } else {
      trendElement.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/>
          <polyline points="17 18 23 18 23 12"/>
        </svg>
        Needs Attention
      `;
      trendElement.className = 'metric-trend negative';
    }
  }

  /**
   * Initialize Chart.js visualizations
   */
  initCharts() {
    this.initReadinessChart();
    this.initFindingsChart();
  }

  /**
   * Create readiness breakdown doughnut chart
   */
  initReadinessChart() {
    const ctx = document.getElementById('readiness-chart');
    if (!ctx) return;

    if (this.charts.readiness) {
      this.charts.readiness.destroy();
    }

    const data = this.readinessData || {};

    this.charts.readiness = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Compliance', 'Evidence', 'Documents', 'Consistency'],
        datasets: [{
          data: [
            Math.round(data.compliance || 0),
            Math.round(data.evidence || 0),
            Math.round(data.documents || 0),
            Math.round(data.consistency || 0)
          ],
          backgroundColor: [
            '#4ade80', // success (compliance)
            '#3b82f6', // info (evidence)
            '#f59e0b', // warning (documents)
            '#a78bfa'  // accreditor purple (consistency)
          ],
          borderWidth: 0,
          hoverOffset: 8
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        cutout: '60%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              color: getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim(),
              padding: 16,
              font: {
                size: 13,
                family: getComputedStyle(document.documentElement).getPropertyValue('--font-sans').trim()
              }
            }
          },
          tooltip: {
            backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--bg-panel').trim(),
            titleColor: getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim(),
            bodyColor: getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim(),
            borderColor: getComputedStyle(document.documentElement).getPropertyValue('--border-medium').trim(),
            borderWidth: 1,
            padding: 12,
            callbacks: {
              label: function(context) {
                return `${context.label}: ${context.parsed}%`;
              }
            }
          }
        }
      }
    });
  }

  /**
   * Create findings by severity horizontal bar chart
   */
  initFindingsChart() {
    const ctx = document.getElementById('findings-chart');
    if (!ctx) return;

    if (this.charts.findings) {
      this.charts.findings.destroy();
    }

    const data = this.findingsData || {};

    this.charts.findings = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Critical', 'High', 'Medium', 'Low'],
        datasets: [{
          label: 'Findings',
          data: [
            data.critical || 0,
            data.high || 0,
            data.medium || 0,
            data.low || 0
          ],
          backgroundColor: [
            '#ef4444', // critical
            '#fb923c', // high
            '#fbbf24', // medium
            '#4ade80'  // low
          ],
          borderRadius: 4
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--bg-panel').trim(),
            titleColor: getComputedStyle(document.documentElement).getPropertyValue('--text-primary').trim(),
            bodyColor: getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim(),
            borderColor: getComputedStyle(document.documentElement).getPropertyValue('--border-medium').trim(),
            borderWidth: 1,
            padding: 12
          }
        },
        scales: {
          x: {
            beginAtZero: true,
            ticks: {
              stepSize: 1,
              color: getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim()
            },
            grid: {
              color: getComputedStyle(document.documentElement).getPropertyValue('--border-subtle').trim()
            }
          },
          y: {
            ticks: {
              color: getComputedStyle(document.documentElement).getPropertyValue('--text-secondary').trim()
            },
            grid: {
              display: false
            }
          }
        }
      }
    });
  }

  /**
   * Populate report history table
   */
  populateReportTable(reports) {
    const tbody = document.getElementById('reports-table-body');
    const emptyState = document.getElementById('reports-empty');

    if (!reports || reports.length === 0) {
      emptyState.style.display = '';
      return;
    }

    emptyState.style.display = 'none';

    // Clear existing rows (except empty state)
    const existingRows = tbody.querySelectorAll('tr:not(.empty-state)');
    existingRows.forEach(row => row.remove());

    reports.forEach(report => {
      const row = document.createElement('tr');

      const date = new Date(report.generated_at || report.created_at);
      const dateStr = date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });

      const statusBadge = this.getStatusBadge(report.status);

      row.innerHTML = `
        <td>${dateStr}</td>
        <td>${report.title || report.report_type || 'Compliance Report'}</td>
        <td>${statusBadge}</td>
        <td>
          <button class="btn-download" data-report-id="${report.id}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="7 10 12 15 17 10"/>
              <line x1="12" y1="15" x2="12" y2="3"/>
            </svg>
            Download
          </button>
        </td>
      `;

      tbody.appendChild(row);
    });

    // Attach download listeners
    tbody.querySelectorAll('.btn-download').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const reportId = e.currentTarget.dataset.reportId;
        this.downloadReport(reportId);
      });
    });
  }

  /**
   * Get status badge HTML
   */
  getStatusBadge(status) {
    const badges = {
      'completed': '<span class="chip chip-success">Completed</span>',
      'generating': '<span class="chip chip-pending">Generating</span>',
      'failed': '<span class="chip chip-error">Failed</span>'
    };
    return badges[status] || '<span class="chip">Unknown</span>';
  }

  /**
   * Generate new compliance report
   */
  async generateReport() {
    const btn = document.getElementById('generate-report-btn');
    const overlay = document.getElementById('loading-overlay');

    btn.disabled = true;
    overlay.style.display = 'flex';

    try {
      const response = await fetch(`/api/reports/institutions/${this.institutionId}/compliance`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) throw new Error('Failed to generate report');

      const result = await response.json();

      this.showToast('Report generated successfully', 'success');

      // Refresh report history
      await this.loadReportHistory();

      // Auto-download the generated report
      if (result.report_id) {
        setTimeout(() => {
          this.downloadReport(result.report_id);
        }, 500);
      }

    } catch (error) {
      console.error('Error generating report:', error);
      this.showToast('Failed to generate report', 'error');
    } finally {
      btn.disabled = false;
      overlay.style.display = 'none';
    }
  }

  /**
   * Download report PDF
   */
  downloadReport(reportId) {
    const url = `/api/reports/${reportId}/download`;
    window.open(url, '_blank');
  }

  /**
   * Show toast notification
   */
  showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type}`;
    toast.classList.add('show');

    setTimeout(() => {
      toast.classList.remove('show');
    }, 3000);
  }

  /**
   * Attach event listeners
   */
  attachEventListeners() {
    const generateBtn = document.getElementById('generate-report-btn');
    if (generateBtn) {
      generateBtn.addEventListener('click', () => this.generateReport());
    }
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  const manager = new ReportsManager();
  manager.init();
});
