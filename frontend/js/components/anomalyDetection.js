import { sessionState } from '../state/sessionState.js';
import { apiService } from '../services/apiService.js';
import { formatters } from '../utils/formatters.js';
import { domHelpers } from '../utils/domHelpers.js';
import { notifications } from '../ui/notifications.js';
import { loading } from '../ui/loading.js';
import { tabs } from './tabs.js';
import { configuration } from './configuration.js';

// Anomaly detection component
export const anomalyDetection = {
    init() {
        this.setupEventListeners();
    },

    setupEventListeners() {
        const form = domHelpers.getElementById('anomaly-form');
        if (form) {
            form.addEventListener('submit', (e) => this.handleSubmit(e));
        }
    },

    async handleSubmit(e) {
        e.preventDefault();

        if (!sessionState.isSessionActive()) {
            notifications.alert('Please configure your credentials first');
            tabs.switchToConfigTab();
            return;
        }

        const submitBtn = e.target.querySelector('button[type="submit"]');
        loading.showLoading(submitBtn, 'Detecting...');

        // Clear previous results
        domHelpers.setInnerHTML(domHelpers.getElementById('anomaly-results'), '');

        const targetDate = domHelpers.getValue(domHelpers.getElementById('target-date'));
        const threshold = parseFloat(domHelpers.getValue(domHelpers.getElementById('threshold')));

        try {
            const data = await apiService.detectAnomalies(
                sessionState.getSessionId(),
                targetDate,
                threshold
            );

            this.displayResults(data);

        } catch (error) {
            console.error('Error:', error);

            if (error.message.includes('Session expired')) {
                configuration.clearSession();
                notifications.showError(`${error.message} Redirecting to configuration...`);
                setTimeout(() => tabs.switchToConfigTab(), 2000);
            } else {
                notifications.showError(`Error: ${error.message}`);
            }
        } finally {
            loading.hideLoading(submitBtn, 'Detect Anomalies');
        }
    },

    displayResults(data) {
        const resultsDiv = domHelpers.getElementById('anomaly-results');

        // Create base HTML structure
        resultsDiv.innerHTML = `
            <div id="summary-badge"></div>
            <h3>Detection Summary</h3>
            <div id="summary-content"></div>
            <h3>Subscription Results</h3>
            <div id="subscription-results" class="subscription-list-container"></div>
        `;

        const summaryBadge = domHelpers.getElementById('summary-badge');
        const summaryContent = domHelpers.getElementById('summary-content');
        const subscriptionResults = domHelpers.getElementById('subscription-results');

        domHelpers.show(resultsDiv);

        // Summary Badge
        const hasAnomalies = data.summary.anomaly_detected;
        summaryBadge.innerHTML = `
            <div class="badge ${hasAnomalies ? 'badge-danger' : 'badge-success'}">
                ${hasAnomalies ? 'Anomalies Detected' : 'All Normal'}
            </div>
        `;

        // Summary Stats
        summaryContent.innerHTML = `
            <div class="summary-stats">
                <div class="stat-box">
                    <div class="label">Target Date</div>
                    <div class="value">${formatters.formatDate(data.target_date)}</div>
                </div>
                <div class="stat-box">
                    <div class="label">Threshold</div>
                    <div class="value">${data.threshold}%</div>
                </div>
                <div class="stat-box">
                    <div class="label">Subscriptions Checked</div>
                    <div class="value">${data.summary.total_subscriptions}</div>
                </div>
                <div class="stat-box">
                    <div class="label">Anomalies Found</div>
                    <div class="value ${hasAnomalies ? 'change-positive' : ''}">${data.summary.subscriptions_with_anomalies}</div>
                </div>
            </div>
        `;

        // Subscription Results
        subscriptionResults.innerHTML = '';
        Object.entries(data.subscriptions).forEach(([subName, subData]) => {
            subscriptionResults.innerHTML += this.createSubscriptionCard(subName, subData);
        });

        domHelpers.scrollIntoView(resultsDiv);
    },

    createSubscriptionCard(name, data) {
        const hasAnomalies = data.has_anomalies;
        const daysInAverage = data.days_in_average;

        let tableRows = '';

        if (!data.results || data.results.length === 0) {
            tableRows = `
                <tr>
                    <td colspan="5" style="text-align: center; color: var(--text-secondary);">
                        No cost data available for this period
                    </td>
                </tr>
            `;
        } else {
            data.results.forEach(result => {
                let changeClass;
                const epsilon = 0.001;

                if (Math.abs(result.percent_change) < epsilon) {
                    changeClass = 'change-negative';
                } else if (result.percent_change > 0) {
                    changeClass = 'change-positive';
                } else {
                    changeClass = 'change-negative';
                }

                tableRows += `
                    <tr>
                        <td>${result.service}</td>
                        <td>${formatters.formatCurrency(result.average_cost)}</td>
                        <td>${formatters.formatCurrency(result.current_cost)}</td>
                        <td class="${changeClass}">${formatters.formatPercentChange(result.percent_change)}</td>
                        <td>
                            <span class="anomaly-indicator ${result.is_anomaly ? 'anomaly' : 'normal'}">
                                ${result.is_anomaly ? 'Anomaly' : 'Normal'}
                            </span>
                        </td>
                    </tr>
                `;
            });
        }

        return `
            <div class="card subscription-card ${hasAnomalies ? 'has-anomaly' : ''}">
                <div class="subscription-header">
                    <div class="subscription-name">${name.toUpperCase()}</div>
                    ${hasAnomalies ? '<div class="badge badge-danger">Action Required</div>' : '<div class="badge badge-success">Normal</div>'}
                </div>
                <div style="color: var(--text-secondary); margin-bottom: 1rem;">
                    Comparing <strong>${formatters.formatDate(data.target_date)}</strong> against ${daysInAverage}-day rolling average
                    <br>
                    <small>Average period: ${formatters.formatDate(data.start_date)} to ${formatters.formatDate(data.end_date)} (${daysInAverage} days)</small>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Service</th>
                            <th>Rolling Average</th>
                            <th>Current Cost</th>
                            <th>Change</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${tableRows}
                    </tbody>
                </table>
            </div>
        `;
    }
};