import { domHelpers } from '../utils/domHelpers.js';

// Tab management
export const tabs = {
    init() {
        domHelpers.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                if (domHelpers.hasClass(tab, 'disabled')) return;
                this.switchTab(tab.dataset.tab);
            });
        });
    },

    switchTab(tabName) {
        // Remove active class from all tabs
        domHelpers.querySelectorAll('.tab').forEach(t => {
            domHelpers.removeClass(t, 'active');
        });

        // Add active class to clicked tab
        const activeTab = domHelpers.querySelector(`.tab[data-tab="${tabName}"]`);
        if (activeTab) {
            domHelpers.addClass(activeTab, 'active');
        }

        // Hide all tab contents
        domHelpers.querySelectorAll('.tab-content').forEach(c => {
            domHelpers.removeClass(c, 'active');
        });

        // Show selected tab content
        const activeContent = domHelpers.getElementById(`${tabName}-tab`);
        if (activeContent) {
            domHelpers.addClass(activeContent, 'active');
        }
    },

    enableTab(tabId) {
        const tab = domHelpers.getElementById(tabId);
        if (tab) {
            domHelpers.removeClass(tab, 'disabled');
        }
    },

    disableTab(tabId) {
        const tab = domHelpers.getElementById(tabId);
        if (tab) {
            domHelpers.addClass(tab, 'disabled');
        }
    },

    enableAllTabs() {
        this.enableTab('anomaly-tab-btn');
        this.enableTab('report-tab-btn');
    },

    disableAllTabs() {
        this.disableTab('anomaly-tab-btn');
        this.disableTab('report-tab-btn');

        // Switch to config tab if on a disabled tab
        const activeTab = domHelpers.querySelector('.tab.active');
        if (activeTab && activeTab.dataset.tab !== 'config') {
            this.switchToConfigTab();
        }
    },

    switchToConfigTab() {
        this.switchTab('config');
    }
};