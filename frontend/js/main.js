import { domHelpers } from './utils/domHelpers.js';
import { tabs } from './components/tabs.js';
import { configuration } from './components/configuration.js';
import { agent } from './components/agent.js';
import { anomalyDetection } from './components/anomalyDetection.js';
import { costReport } from './components/costReport.js';

// Application initialization
class App {
    constructor() {
        this.initialized = false;
    }

    init() {
        if (this.initialized) {
            console.warn('App already initialized');
            return;
        }

        console.log('=== Azure Cost Analyzer Starting ===');

        // Set default date for anomaly detection (yesterday)
        this.setDefaultDate();

        // Initialize all components
        tabs.init();
        configuration.init();
        agent.init();  // NEW: Initialize AI agent
        anomalyDetection.init();
        costReport.init();

        this.initialized = true;
        console.log('=== Application Initialized Successfully ===');
    }

    setDefaultDate() {
        const yesterday = new Date();
        yesterday.setDate(yesterday.getDate() - 1);
        const targetDateInput = domHelpers.getElementById('target-date');
        if (targetDateInput) {
            targetDateInput.valueAsDate = yesterday;
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const app = new App();
    app.init();
});

// Export for debugging
window.App = App;