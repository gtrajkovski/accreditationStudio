/**
 * Compliance History Chart Component
 *
 * Renders a line chart showing readiness score trends over time.
 * Supports theme-aware colors, time range selection, and sub-score toggle.
 */
class ComplianceChart {
    constructor(canvasId, options = {}) {
        this.canvas = document.getElementById(canvasId);
        this.chart = null;
        this.options = {
            institutionId: options.institutionId || null,
            showSubScores: options.showSubScores || false,
            timeRange: options.timeRange || 30,
            ...options
        };
        this.data = [];
    }

    /**
     * Get theme-aware colors from CSS variables
     */
    getThemeColors() {
        const styles = getComputedStyle(document.documentElement);
        return {
            accent: styles.getPropertyValue('--accent').trim() || '#C9A84C',
            success: styles.getPropertyValue('--success').trim() || '#4ade80',
            warning: styles.getPropertyValue('--warning').trim() || '#fbbf24',
            info: styles.getPropertyValue('--info').trim() || '#3b82f6',
            accreditor: styles.getPropertyValue('--accreditor').trim() || '#a78bfa',
            text: styles.getPropertyValue('--text-primary').trim() || '#E6EDF3',
            muted: styles.getPropertyValue('--text-muted').trim() || '#8b949e',
            grid: styles.getPropertyValue('--border-subtle').trim() || '#30363d',
            bgCard: styles.getPropertyValue('--bg-card').trim() || '#1C2333',
        };
    }

    /**
     * Initialize the chart
     */
    async init() {
        if (!this.canvas) {
            console.error('ComplianceChart: Canvas element not found');
            return;
        }

        if (!this.options.institutionId) {
            console.error('ComplianceChart: institutionId is required');
            return;
        }

        // Load initial data
        await this.loadData(this.options.timeRange);

        // Set up theme change listener
        this.setupThemeListener();
    }

    /**
     * Load data from API
     */
    async loadData(days) {
        try {
            const response = await window.API.get(
                `/api/institutions/${this.options.institutionId}/readiness/history?days=${days}`
            );

            if (response.success) {
                this.data = response.history || [];
                this.render();
            } else {
                console.error('Failed to load history:', response.error);
                this.showEmptyState();
            }
        } catch (error) {
            console.error('Error loading compliance history:', error);
            this.showEmptyState();
        }
    }

    /**
     * Show empty state when no data available
     */
    showEmptyState() {
        const container = this.canvas.parentElement;
        const emptyState = container.querySelector('.chart-empty-state');

        if (emptyState) {
            emptyState.style.display = 'flex';
            this.canvas.style.display = 'none';
        } else {
            // Create empty state if it doesn't exist
            this.canvas.style.display = 'none';
            const empty = document.createElement('div');
            empty.className = 'chart-empty-state';
            empty.innerHTML = `
                <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" style="opacity: 0.5; margin-bottom: 12px;">
                    <path d="M3 3v18h18"/>
                    <path d="M7 16l4-4 4 4 5-6"/>
                </svg>
                <p style="margin: 0; font-weight: 500;">No compliance history yet</p>
                <p style="margin: 4px 0 0; font-size: 0.875rem; opacity: 0.7;">Historical data will appear as you use AccreditAI</p>
            `;
            container.appendChild(empty);
        }
    }

    /**
     * Hide empty state and show chart
     */
    hideEmptyState() {
        const container = this.canvas.parentElement;
        const emptyState = container.querySelector('.chart-empty-state');

        if (emptyState) {
            emptyState.style.display = 'none';
        }
        this.canvas.style.display = 'block';
    }

    /**
     * Render the chart
     */
    render() {
        if (this.data.length === 0) {
            this.showEmptyState();
            return;
        }

        this.hideEmptyState();

        const colors = this.getThemeColors();
        const ctx = this.canvas.getContext('2d');

        // Prepare data
        const labels = this.data.map(d => this.formatDate(d.created_at));
        const totalScores = this.data.map(d => d.total);

        // Build datasets
        const datasets = [
            {
                label: 'Total Score',
                data: totalScores,
                borderColor: colors.accent,
                backgroundColor: this.createGradient(ctx, colors.accent),
                fill: true,
                tension: 0.3,
                borderWidth: 2,
                pointRadius: this.data.length > 30 ? 0 : 3,
                pointHoverRadius: 5,
                pointBackgroundColor: colors.accent,
            }
        ];

        // Add sub-score lines if enabled
        if (this.options.showSubScores) {
            datasets.push(
                {
                    label: 'Documents',
                    data: this.data.map(d => d.documents),
                    borderColor: colors.info,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.3,
                    borderWidth: 1.5,
                    pointRadius: 0,
                },
                {
                    label: 'Compliance',
                    data: this.data.map(d => d.compliance),
                    borderColor: colors.success,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.3,
                    borderWidth: 1.5,
                    pointRadius: 0,
                },
                {
                    label: 'Evidence',
                    data: this.data.map(d => d.evidence),
                    borderColor: colors.warning,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.3,
                    borderWidth: 1.5,
                    pointRadius: 0,
                },
                {
                    label: 'Consistency',
                    data: this.data.map(d => d.consistency),
                    borderColor: colors.accreditor,
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.3,
                    borderWidth: 1.5,
                    pointRadius: 0,
                }
            );
        }

        // Chart configuration
        const config = {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        display: this.options.showSubScores,
                        position: 'bottom',
                        labels: {
                            color: colors.muted,
                            usePointStyle: true,
                            padding: 16,
                            font: { size: 11 }
                        }
                    },
                    tooltip: {
                        backgroundColor: colors.bgCard,
                        titleColor: colors.text,
                        bodyColor: colors.muted,
                        borderColor: colors.grid,
                        borderWidth: 1,
                        padding: 12,
                        displayColors: true,
                        callbacks: {
                            label: function(context) {
                                return `${context.dataset.label}: ${context.parsed.y}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            color: colors.grid,
                            drawBorder: false,
                        },
                        ticks: {
                            color: colors.muted,
                            maxTicksLimit: 8,
                            font: { size: 10 }
                        }
                    },
                    y: {
                        min: 0,
                        max: 100,
                        grid: {
                            color: colors.grid,
                            drawBorder: false,
                        },
                        ticks: {
                            color: colors.muted,
                            stepSize: 25,
                            font: { size: 10 },
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        };

        // Destroy existing chart if present
        if (this.chart) {
            this.chart.destroy();
        }

        this.chart = new Chart(ctx, config);
    }

    /**
     * Create gradient fill for the main score line
     */
    createGradient(ctx, color) {
        const gradient = ctx.createLinearGradient(0, 0, 0, 200);
        gradient.addColorStop(0, this.hexToRgba(color, 0.3));
        gradient.addColorStop(1, this.hexToRgba(color, 0.0));
        return gradient;
    }

    /**
     * Convert hex color to rgba
     */
    hexToRgba(hex, alpha) {
        // Handle CSS variable format or direct hex
        if (hex.startsWith('#')) {
            const r = parseInt(hex.slice(1, 3), 16);
            const g = parseInt(hex.slice(3, 5), 16);
            const b = parseInt(hex.slice(5, 7), 16);
            return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        }
        // Fallback for non-hex values
        return `rgba(201, 168, 76, ${alpha})`;
    }

    /**
     * Format date for chart labels
     */
    formatDate(isoDate) {
        const date = new Date(isoDate);
        const month = date.toLocaleDateString('en-US', { month: 'short' });
        const day = date.getDate();
        return `${month} ${day}`;
    }

    /**
     * Update time range and reload data
     */
    async updateTimeRange(days) {
        this.options.timeRange = days;
        await this.loadData(days);
    }

    /**
     * Toggle sub-scores visibility
     */
    toggleSubScores(show) {
        this.options.showSubScores = show;
        this.render();
    }

    /**
     * Set up listener for theme changes
     */
    setupThemeListener() {
        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                if (mutation.attributeName === 'data-theme') {
                    // Re-render with new theme colors
                    this.render();
                }
            }
        });

        observer.observe(document.documentElement, { attributes: true });
    }

    /**
     * Update chart colors for current theme
     */
    updateThemeColors() {
        if (this.chart) {
            this.render();
        }
    }
}

// Export for use in other scripts
window.ComplianceChart = ComplianceChart;
