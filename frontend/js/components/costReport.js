import { CONFIG } from '../config.js';
import { sessionState } from '../state/sessionState.js';
import { apiService } from '../services/apiService.js';
import { domHelpers } from '../utils/domHelpers.js';
import { notifications } from '../ui/notifications.js';
import { loading } from '../ui/loading.js';
import { tabs } from './tabs.js';
import { configuration } from './configuration.js';

// Cost report component
export const costReport = {
    init() {
        this.setupEventListeners();
    },

    setupEventListeners() {
        const form = domHelpers.getElementById('report-form');
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
        const resultDiv = domHelpers.getElementById('report-result');

        loading.showLoading(submitBtn, 'Generating...');
        domHelpers.hide(resultDiv);

        const numDays = parseInt(domHelpers.getValue(domHelpers.getElementById('num-days')));

        try {
            const data = await apiService.generateCostReport(
                sessionState.getSessionId(),
                numDays
            );

            this.displayResult(data);

        } catch (error) {
            console.error('Error:', error);

            if (error.message.includes('Session expired')) {
                configuration.clearSession();
                notifications.alert(`${error.message}\n\nRedirecting to configuration...`);
                setTimeout(() => tabs.switchToConfigTab(), 1000);
            } else {
                notifications.alert(`Error: ${error.message}`);
            }
        } finally {
            loading.hideLoading(submitBtn, 'Generate Report');
        }
    },

    displayResult(data) {
        const resultDiv = domHelpers.getElementById('report-result');
        const messageEl = domHelpers.getElementById('report-message');
        const downloadLink = domHelpers.getElementById('download-link');

        if (messageEl) {
            messageEl.textContent = data.message;
        }

        if (downloadLink) {
            downloadLink.href = `${CONFIG.API_BASE_URL}${data.download_url}`;
            downloadLink.download = data.filename;
        }

        domHelpers.show(resultDiv);
        domHelpers.scrollIntoView(resultDiv, { behavior: 'smooth', block: 'nearest' });
    }
};