/**
 * Observability Dashboard JavaScript
 * Fetches metrics from API and updates UI panels
 */

(function() {
    'use strict';

    // State
    let costChart = null;
    let refreshInterval = null;
    const REFRESH_MS = 30000; // 30 seconds

    // DOM Elements
    const elements = {
        lastUpdated: document.getElementById('last-updated'),
        statusDot: document.getElementById('status-dot'),
        timeRange: document.getElementById('time-range'),
        refreshBtn: document.getElementById('refresh-btn'),
        // Health
        dbSize: document.getElementById('db-size'),
        uptime: document.getElementById('uptime'),
        instCount: document.getElementById('inst-count'),
        docCount: document.getElementById('doc-count'),
        // Costs
        totalCost: document.getElementById('total-cost'),
        costPeriod: document.getElementById('cost-period'),
        callCount: document.getElementById('call-count'),
        inputTokens: document.getElementById('input-tokens'),
        outputTokens: document.getElementById('output-tokens'),
        modelBreakdown: document.getElementById('model-breakdown'),
        costChart: document.getElementById('cost-chart'),
        // Activity
        activeCount: document.getElementById('active-count'),
        completedCount: document.getElementById('completed-count'),
        failedCount: document.getElementById('failed-count'),
        batchList: document.getElementById('batch-list'),
        // Performance
        queueDepth: document.getElementById('queue-depth'),
        avgDuration: document.getElementById('avg-duration'),
        throughput: document.getElementById('throughput'),
    };

    /**
     * Format bytes to human-readable size
     */
    function formatSize(mb) {
        if (mb < 1) return `${Math.round(mb * 1024)} KB`;
        if (mb < 1024) return `${mb.toFixed(1)} MB`;
        return `${(mb / 1024).toFixed(2)} GB`;
    }

    /**
     * Format seconds to human-readable uptime
     */
    function formatUptime(seconds) {
        if (seconds < 60) return `${seconds}s`;
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        if (hours < 24) return `${hours}h ${mins}m`;
        const days = Math.floor(hours / 24);
        return `${days}d ${hours % 24}h`;
    }

    /**
     * Format number with commas
     */
    function formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    }

    /**
     * Format currency
     */
    function formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
        }).format(amount);
    }

    /**
     * Update System Health panel
     */
    function updateHealthPanel(health) {
        elements.dbSize.textContent = formatSize(health.database_size_mb || 0);
        elements.uptime.textContent = formatUptime(health.uptime_seconds || 0);

        const counts = health.table_counts || {};
        elements.instCount.textContent = formatNumber(counts.institutions || 0);
        elements.docCount.textContent = formatNumber(counts.documents || 0);
    }

    /**
     * Update AI Costs panel
     */
    function updateCostsPanel(costs, days) {
        elements.totalCost.textContent = formatCurrency(costs.total_cost || 0);
        elements.costPeriod.textContent = `Last ${days} days`;
        elements.callCount.textContent = formatNumber(costs.call_count || 0);
        elements.inputTokens.textContent = formatNumber(costs.input_tokens || 0);
        elements.outputTokens.textContent = formatNumber(costs.output_tokens || 0);

        // Model breakdown
        const models = costs.by_model || [];
        if (models.length > 0) {
            elements.modelBreakdown.innerHTML = models.map(m => `
                <div class="model-row">
                    <span class="model-name">${m.model}</span>
                    <span class="model-cost">${formatCurrency(m.cost)} (${m.calls} calls)</span>
                </div>
            `).join('');
        } else {
            elements.modelBreakdown.innerHTML = '<div class="empty-state">No API calls in period</div>';
        }

        // Daily trend chart
        updateCostChart(costs.daily_trend || []);
    }

    /**
     * Update cost trend chart
     */
    function updateCostChart(dailyData) {
        const ctx = elements.costChart.getContext('2d');

        const labels = dailyData.map(d => d.date);
        const data = dailyData.map(d => d.cost);

        if (costChart) {
            costChart.data.labels = labels;
            costChart.data.datasets[0].data = data;
            costChart.update();
        } else {
            costChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Daily Cost',
                        data: data,
                        borderColor: '#c9a84c',
                        backgroundColor: 'rgba(201, 168, 76, 0.1)',
                        fill: true,
                        tension: 0.3,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false },
                    },
                    scales: {
                        x: {
                            display: true,
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: { color: '#9ca3af', maxTicksLimit: 7 },
                        },
                        y: {
                            display: true,
                            grid: { color: 'rgba(255,255,255,0.1)' },
                            ticks: {
                                color: '#9ca3af',
                                callback: (val) => '$' + val.toFixed(2),
                            },
                        },
                    },
                },
            });
        }
    }

    /**
     * Update Agent Activity panel
     */
    function updateActivityPanel(activity) {
        elements.activeCount.textContent = activity.active_count || 0;
        elements.completedCount.textContent = activity.completed_24h || 0;
        elements.failedCount.textContent = activity.failed_24h || 0;

        // Recent batches
        const batches = activity.recent_batches || [];
        if (batches.length > 0) {
            elements.batchList.innerHTML = batches.map(b => `
                <div class="batch-item">
                    <span class="batch-type">${b.operation_type} (${b.completed_count}/${b.document_count})</span>
                    <span class="batch-status ${b.status}">${b.status}</span>
                </div>
            `).join('');
        } else {
            elements.batchList.innerHTML = '<div class="empty-state">No recent batches</div>';
        }
    }

    /**
     * Update Performance panel
     */
    function updatePerformancePanel(perf) {
        elements.queueDepth.textContent = formatNumber(perf.queue_depth || 0);
        elements.avgDuration.textContent = perf.avg_batch_duration_ms
            ? formatNumber(Math.round(perf.avg_batch_duration_ms))
            : '--';
        elements.throughput.textContent = formatNumber(perf.throughput_per_hour || 0);
    }

    /**
     * Load all metrics from API
     */
    async function loadMetrics() {
        const days = parseInt(elements.timeRange.value, 10);

        try {
            const response = await fetch(`/api/observability/metrics?days=${days}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const metrics = await response.json();

            // Update panels
            updateHealthPanel(metrics.system_health || {});
            updateCostsPanel(metrics.ai_costs || {}, days);
            updateActivityPanel(metrics.agent_activity || {});
            updatePerformancePanel(metrics.performance || {});

            // Update status
            elements.statusDot.classList.remove('error');
            elements.lastUpdated.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;

        } catch (error) {
            console.error('Failed to load metrics:', error);
            elements.statusDot.classList.add('error');
            elements.lastUpdated.textContent = `Error loading metrics: ${error.message}`;
        }
    }

    /**
     * Initialize auto-refresh
     */
    function startAutoRefresh() {
        if (refreshInterval) clearInterval(refreshInterval);
        refreshInterval = setInterval(loadMetrics, REFRESH_MS);
    }

    /**
     * Initialize event listeners
     */
    function initEventListeners() {
        // Time range change
        elements.timeRange.addEventListener('change', loadMetrics);

        // Manual refresh
        elements.refreshBtn.addEventListener('click', loadMetrics);
    }

    /**
     * Initialize dashboard
     */
    function init() {
        initEventListeners();
        loadMetrics();
        startAutoRefresh();
    }

    // Start on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
