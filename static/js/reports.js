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
    this.trendChart = null;
    this.trendData = [];
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
    await this.loadTrend(30);
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
   * Load readiness trend data
   */
  async loadTrend(days = 30) {
    try {
      const response = await fetch(`/api/reports/institutions/${this.institutionId}/trend?days=${days}`);
      const data = await response.json();

      if (data.success) {
        this.trendData = data.trend;
        this.renderTrendChart();
      }
    } catch (err) {
      console.error('Failed to load trend:', err);
    }
  }

  /**
   * Render trend chart with Chart.js
   */
  renderTrendChart() {
    const ctx = document.getElementById('trend-chart');
    if (!ctx) return;

    // Destroy previous chart if exists
    if (this.trendChart) {
      this.trendChart.destroy();
    }

    const labels = this.trendData.map(d => new Date(d.date).toLocaleDateString());
    const values = this.trendData.map(d => d.readiness);

    this.trendChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Readiness Score',
          data: values,
          borderColor: 'rgb(233, 69, 96)',  // var(--accent)
          backgroundColor: 'rgba(233, 69, 96, 0.1)',
          tension: 0.4,
          fill: true,
          pointRadius: 4,
          pointHoverRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            padding: 12,
            titleColor: '#fff',
            bodyColor: '#fff',
            callbacks: {
              title: (items) => {
                return new Date(this.trendData[items[0].dataIndex].date).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                });
              },
              label: (context) => {
                return `Readiness: ${context.parsed.y}`;
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            max: 100,
            ticks: {
              color: '#9ca3af'
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
            }
          },
          x: {
            ticks: {
              color: '#9ca3af',
              maxRotation: 45,
              minRotation: 45
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.1)'
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
   * Load schedules
   */
  async loadSchedules() {
    try {
      const response = await fetch(`/api/reports/schedules?institution_id=${this.institutionId}`);
      if (!response.ok) throw new Error('Failed to load schedules');

      const data = await response.json();
      this.populateSchedulesTable(data.schedules || []);
    } catch (error) {
      console.error('Error loading schedules:', error);
    }
  }

  /**
   * Populate schedules table
   */
  populateSchedulesTable(schedules) {
    const tbody = document.getElementById('schedules-tbody');
    const emptyState = document.getElementById('schedules-empty');

    if (!schedules || schedules.length === 0) {
      emptyState.style.display = '';
      return;
    }

    emptyState.style.display = 'none';

    // Clear existing rows (except empty state)
    const existingRows = tbody.querySelectorAll('tr:not(.empty-state)');
    existingRows.forEach(row => row.remove());

    schedules.forEach(schedule => {
      const row = document.createElement('tr');

      // Format schedule description
      const scheduleDesc = this.formatScheduleDescription(schedule);

      // Format recipients
      const recipientsList = Array.isArray(schedule.recipients) ? schedule.recipients : JSON.parse(schedule.recipients || '[]');
      const recipientsDisplay = recipientsList.length > 0 ? recipientsList[0] + (recipientsList.length > 1 ? ` +${recipientsList.length - 1}` : '') : 'None';

      // Format last run
      const lastRun = schedule.last_run_at ? new Date(schedule.last_run_at).toLocaleString() : 'Never';

      // Status badge
      let statusBadge = '<span class="chip chip-success">Active</span>';
      if (!schedule.enabled) {
        statusBadge = '<span class="chip chip-secondary">Paused</span>';
      } else if (schedule.last_status === 'failed') {
        statusBadge = '<span class="chip chip-error">Failed</span>';
      }

      row.innerHTML = `
        <td>${scheduleDesc}</td>
        <td>${schedule.schedule_hour}:00</td>
        <td title="${recipientsList.join(', ')}">${recipientsDisplay}</td>
        <td>${lastRun}</td>
        <td>${statusBadge}</td>
        <td>
          <div class="action-buttons">
            ${schedule.enabled
              ? `<button class="btn-icon btn-pause" data-schedule-id="${schedule.id}" title="Pause">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="6" y="4" width="4" height="16"/>
                    <rect x="14" y="4" width="4" height="16"/>
                  </svg>
                 </button>`
              : `<button class="btn-icon btn-resume" data-schedule-id="${schedule.id}" title="Resume">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polygon points="5 3 19 12 5 21 5 3"/>
                  </svg>
                 </button>`
            }
            <button class="btn-icon btn-delete" data-schedule-id="${schedule.id}" title="Delete">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
              </svg>
            </button>
          </div>
        </td>
      `;

      tbody.appendChild(row);
    });

    // Attach action listeners
    this.attachScheduleActionListeners();
  }

  /**
   * Format schedule description
   */
  formatScheduleDescription(schedule) {
    if (schedule.schedule_type === 'daily') {
      return 'Daily';
    } else if (schedule.schedule_type === 'weekly') {
      const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
      return `Weekly on ${days[schedule.schedule_day_of_week || 0]}`;
    } else if (schedule.schedule_type === 'monthly') {
      return `Monthly on day ${schedule.schedule_day_of_month || 1}`;
    }
    return 'Unknown';
  }

  /**
   * Attach schedule action listeners
   */
  attachScheduleActionListeners() {
    // Pause buttons
    document.querySelectorAll('.btn-pause').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const scheduleId = e.currentTarget.dataset.scheduleId;
        await this.pauseSchedule(scheduleId);
      });
    });

    // Resume buttons
    document.querySelectorAll('.btn-resume').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const scheduleId = e.currentTarget.dataset.scheduleId;
        await this.resumeSchedule(scheduleId);
      });
    });

    // Delete buttons
    document.querySelectorAll('.btn-delete').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        const scheduleId = e.currentTarget.dataset.scheduleId;
        if (confirm('Are you sure you want to delete this schedule?')) {
          await this.deleteSchedule(scheduleId);
        }
      });
    });
  }

  /**
   * Create new schedule
   */
  async createSchedule(formData) {
    try {
      const response = await fetch('/api/reports/schedules', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(formData)
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Failed to create schedule');
      }

      this.showToast('Schedule created successfully', 'success');
      await this.loadSchedules();
      this.closeScheduleModal();
    } catch (error) {
      console.error('Error creating schedule:', error);
      this.showToast(error.message, 'error');
    }
  }

  /**
   * Pause schedule
   */
  async pauseSchedule(scheduleId) {
    try {
      const response = await fetch(`/api/reports/schedules/${scheduleId}/pause`, {
        method: 'POST'
      });

      if (!response.ok) throw new Error('Failed to pause schedule');

      this.showToast('Schedule paused', 'success');
      await this.loadSchedules();
    } catch (error) {
      console.error('Error pausing schedule:', error);
      this.showToast('Failed to pause schedule', 'error');
    }
  }

  /**
   * Resume schedule
   */
  async resumeSchedule(scheduleId) {
    try {
      const response = await fetch(`/api/reports/schedules/${scheduleId}/resume`, {
        method: 'POST'
      });

      if (!response.ok) throw new Error('Failed to resume schedule');

      this.showToast('Schedule resumed', 'success');
      await this.loadSchedules();
    } catch (error) {
      console.error('Error resuming schedule:', error);
      this.showToast('Failed to resume schedule', 'error');
    }
  }

  /**
   * Delete schedule
   */
  async deleteSchedule(scheduleId) {
    try {
      const response = await fetch(`/api/reports/schedules/${scheduleId}`, {
        method: 'DELETE'
      });

      if (!response.ok) throw new Error('Failed to delete schedule');

      this.showToast('Schedule deleted', 'success');
      await this.loadSchedules();
    } catch (error) {
      console.error('Error deleting schedule:', error);
      this.showToast('Failed to delete schedule', 'error');
    }
  }

  /**
   * Show schedule modal
   */
  showScheduleModal() {
    const modal = document.getElementById('schedule-modal');
    modal.classList.remove('hidden');

    // Reset form
    document.getElementById('schedule-form').reset();
    document.getElementById('schedule-hour').value = 8;

    // Hide conditional fields
    document.getElementById('day-of-week-group').style.display = 'none';
    document.getElementById('day-of-month-group').style.display = 'none';
  }

  /**
   * Close schedule modal
   */
  closeScheduleModal() {
    const modal = document.getElementById('schedule-modal');
    modal.classList.add('hidden');
  }

  /**
   * Attach event listeners
   */
  attachEventListeners() {
    const generateBtn = document.getElementById('generate-report-btn');
    if (generateBtn) {
      generateBtn.addEventListener('click', () => this.generateReport());
    }

    // Trend button listeners
    document.querySelectorAll('.trend-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.trend-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        const days = parseInt(e.target.dataset.days);
        this.loadTrend(days);
      });
    });

    // Schedule modal triggers
    const newScheduleBtn = document.getElementById('new-schedule-btn');
    if (newScheduleBtn) {
      newScheduleBtn.addEventListener('click', () => this.showScheduleModal());
    }

    const closeModalBtn = document.getElementById('close-modal-btn');
    if (closeModalBtn) {
      closeModalBtn.addEventListener('click', () => this.closeScheduleModal());
    }

    // Modal backdrop close
    const modal = document.getElementById('schedule-modal');
    if (modal) {
      modal.querySelector('.modal-backdrop')?.addEventListener('click', () => this.closeScheduleModal());
    }

    // Schedule type change handler
    const scheduleTypeSelect = document.getElementById('schedule-type');
    if (scheduleTypeSelect) {
      scheduleTypeSelect.addEventListener('change', (e) => {
        const type = e.target.value;
        const weekGroup = document.getElementById('day-of-week-group');
        const monthGroup = document.getElementById('day-of-month-group');

        weekGroup.style.display = type === 'weekly' ? 'block' : 'none';
        monthGroup.style.display = type === 'monthly' ? 'block' : 'none';
      });
    }

    // Schedule form submission
    const scheduleForm = document.getElementById('schedule-form');
    if (scheduleForm) {
      scheduleForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = {
          institution_id: this.institutionId,
          report_type: 'compliance',
          schedule_type: document.getElementById('schedule-type').value,
          hour: parseInt(document.getElementById('schedule-hour').value),
          recipients: document.getElementById('schedule-recipients').value.split(',').map(e => e.trim())
        };

        if (formData.schedule_type === 'weekly') {
          formData.day_of_week = parseInt(document.getElementById('schedule-day-of-week').value);
        }

        if (formData.schedule_type === 'monthly') {
          formData.day_of_month = parseInt(document.getElementById('schedule-day-of-month').value);
        }

        await this.createSchedule(formData);
      });
    }
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  const manager = new ReportsManager();
  manager.init().then(() => {
    // Load schedules after dashboard initializes
    manager.loadSchedules();
  });
});
