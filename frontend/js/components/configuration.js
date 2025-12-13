import { CONFIG } from '../config.js';
import { sessionState } from '../state/sessionState.js';
import { apiService } from '../services/apiService.js';
import { validators } from '../utils/validators.js';
import { domHelpers } from '../utils/domHelpers.js';
import { notifications } from '../ui/notifications.js';
import { loading } from '../ui/loading.js';
import { tabs } from './tabs.js';

// Configuration component
export const configuration = {
    init() {
        this.setupEventListeners();
        this.updateSubscriptionList();
        this.checkExistingSession();
    },

    setupEventListeners() {
        // Provider selection
        domHelpers.querySelectorAll('.provider-card:not(.disabled)').forEach(card => {
            card.addEventListener('click', () => {
                domHelpers.querySelectorAll('.provider-card').forEach(c => {
                    domHelpers.removeClass(c, 'selected');
                });
                domHelpers.addClass(card, 'selected');
            });
        });

        // Credential visibility toggle
        domHelpers.querySelectorAll('.toggle-visibility').forEach(button => {
            button.addEventListener('click', () => this.toggleVisibility(button));
        });

        // Subscription count change
        const subCount = domHelpers.getElementById('subscription-count');
        if (subCount) {
            subCount.addEventListener('change', () => this.updateSubscriptionList());
        }

        // Test connection button
        const testBtn = domHelpers.getElementById('test-connection-btn');
        if (testBtn) {
            testBtn.addEventListener('click', () => this.testConnection());
        }

        // Save configuration button
        const saveBtn = domHelpers.getElementById('save-config-btn');
        if (saveBtn) {
            saveBtn.onclick = (e) => {
                console.log('Save configuration button clicked!');
                e.preventDefault();
                e.stopPropagation();
                this.saveConfiguration();
            };
        }

        // Clear configuration button
        const clearBtn = domHelpers.getElementById('clear-config-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearConfiguration());
        }

        // Debug shortcut (Ctrl+Shift+D)
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.shiftKey && e.key === 'D') {
                this.debugConfiguration();
            }
        });
    },

    toggleVisibility(button) {
        const targetId = button.dataset.target;
        const input = domHelpers.getElementById(targetId);
        if (!input) return;

        const isPassword = input.type === 'password';
        input.type = isPassword ? 'text' : 'password';
        
        const eyeIcon = button.querySelector('.eye-icon');
        if (eyeIcon) {
            // Replace emoji with simple text
            eyeIcon.textContent = isPassword ? 'HIDE' : 'SHOW';
        }
    },

    updateSubscriptionList() {
        const count = parseInt(domHelpers.getValue(domHelpers.getElementById('subscription-count')));
        const container = domHelpers.getElementById('subscription-list');
        if (!container) return;

        // Preserve existing values
        const existingIds = Array.from(domHelpers.querySelectorAll('.subscription-id')).map(el => el.value);
        const existingNames = Array.from(domHelpers.querySelectorAll('.subscription-name')).map(el => el.value);

        // Clear container
        container.innerHTML = '';

        // Create subscription inputs
        for (let i = 0; i < count; i++) {
            const subscriptionItem = document.createElement('div');
            subscriptionItem.className = 'subscription-item';
            subscriptionItem.innerHTML = `
                <div class="form-group">
                    <label>Subscription ID ${i + 1}</label>
                    <input type="text" 
                           class="subscription-id" 
                           placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                           value="${existingIds[i] || ''}"
                           required>
                </div>
                <div class="form-group">
                    <label>Subscription Name ${i + 1}</label>
                    <input type="text" 
                           class="subscription-name" 
                           placeholder="e.g., Production, Development"
                           value="${existingNames[i] || ''}"
                           required>
                </div>
                ${i > 0 ? `<button type="button" class="remove-subscription-btn" onclick="window.removeSubscription(this)">✖</button>` : '<div></div>'}
            `;
            container.appendChild(subscriptionItem);
        }
    },

    async checkExistingSession() {
        const storedSessionId = sessionState.getStoredSessionId();

        if (!storedSessionId) {
            console.log('No existing session found');
            return;
        }

        console.log('Found existing session, validating...');

        try {
            const data = await apiService.validateSession(storedSessionId);

            if (data.valid) {
                sessionState.setSession(storedSessionId);
                tabs.enableAllTabs();
                this.updateConfigStatus(true, data);
                console.log('Session restored successfully');
            } else {
                this.clearSession();
            }
        } catch (error) {
            console.error('Error validating session:', error);
            this.clearSession();
        }
    },

    clearSession() {
        sessionState.clearSession();
        tabs.disableAllTabs();
        this.updateConfigStatus(false);
    },

    async testConnection() {
        const tenantId = domHelpers.getValue(domHelpers.getElementById('tenant-id')).trim();
        const clientId = domHelpers.getValue(domHelpers.getElementById('client-id')).trim();
        const clientSecret = domHelpers.getValue(domHelpers.getElementById('client-secret')).trim();

        const validation = validators.validateCredentials(tenantId, clientId, clientSecret);
        if (!validation.valid) {
            notifications.showTestResult(false, validation.message);
            return;
        }

        const button = domHelpers.getElementById('test-connection-btn');
        const saveButton = domHelpers.getElementById('save-config-btn');

        loading.showLoading(button, 'Testing...');
        domHelpers.disable(saveButton);

        try {
            const data = await apiService.testConnection({ tenantId, clientId, clientSecret });

            if (data.success) {
                notifications.showTestResult(true, data.message);
                domHelpers.enable(saveButton);
            } else {
                notifications.showTestResult(false, data.message);
                domHelpers.disable(saveButton);
            }
        } catch (error) {
            console.error('Error testing connection:', error);
            notifications.showTestResult(false, `Connection test failed: ${error.message}`);
            domHelpers.disable(saveButton);
        } finally {
            loading.hideLoading(button, 'Test Connection');
        }
    },

    async saveConfiguration() {
        console.log('Save Configuration clicked');

        const tenantId = domHelpers.getValue(domHelpers.getElementById('tenant-id')).trim();
        const clientId = domHelpers.getValue(domHelpers.getElementById('client-id')).trim();
        const clientSecret = domHelpers.getValue(domHelpers.getElementById('client-secret')).trim();

        // Validate credentials
        const credValidation = validators.validateCredentials(tenantId, clientId, clientSecret);
        if (!credValidation.valid) {
            notifications.alert(credValidation.message);
            return;
        }

        // Validate subscriptions
        const container = domHelpers.getElementById('subscription-list');
        const subValidation = validators.validateSubscriptions(container);
        if (!subValidation.valid) {
            notifications.alert(subValidation.message);
            return;
        }

        const button = domHelpers.getElementById('save-config-btn');

        if (button.disabled) {
            console.log('Button is disabled, cannot save');
            notifications.alert('Please test your connection first before saving.');
            return;
        }

        loading.showLoading(button, 'Saving...');

        try {
            const data = await apiService.saveConfiguration(
                { tenantId, clientId, clientSecret },
                subValidation.subscriptions
            );

            console.log('Configuration saved successfully:', data);

            sessionState.setSession(data.session_id);

            // Clear old results
            domHelpers.hide(domHelpers.getElementById('anomaly-results'));
            domHelpers.setInnerHTML(domHelpers.getElementById('anomaly-results'), '');
            domHelpers.hide(domHelpers.getElementById('report-result'));

            tabs.enableAllTabs();

            this.updateConfigStatus(true, {
                subscription_count: data.subscription_count,
                cloud_provider: 'azure'
            });

            notifications.alert(`Configuration saved successfully!\n\nYou can now use the Anomaly Detection and Cost Report features.`);

            tabs.switchTab('anomaly');

        } catch (error) {
            console.error('Error saving configuration:', error);
            notifications.alert(`Error: ${error.message}`);
            loading.hideLoading(button, 'Save Configuration');
        } finally {
            if (sessionState.isSessionActive()) {
                loading.hideLoading(button, 'Save Configuration');
            }
        }
    },

    async clearConfiguration() {
        if (!notifications.confirm('Are you sure you want to clear your configuration? This will remove your saved credentials and session.')) {
            return;
        }

        const button = domHelpers.getElementById('clear-config-btn');
        const btnText = button?.querySelector('.btn-text');

        domHelpers.disable(button);
        if (btnText) btnText.textContent = 'Clearing...';

        try {
            const sessionId = sessionState.getSessionId();
            if (sessionId) {
                await apiService.clearConfiguration(sessionId);
            }

            this.clearSession();

            // Reset form
            domHelpers.setValue(domHelpers.getElementById('tenant-id'), '');
            domHelpers.setValue(domHelpers.getElementById('client-id'), '');
            domHelpers.setValue(domHelpers.getElementById('client-secret'), '');

            domHelpers.clearInputs('#subscription-list input');
            domHelpers.setValue(domHelpers.getElementById('subscription-count'), '1');

            this.updateSubscriptionList();

            // Reset input types to password
            domHelpers.querySelectorAll('.credential-input-wrapper input').forEach(input => {
                input.type = 'password';
            });

            // Clear result displays
            notifications.clearTestResult();
            domHelpers.hide(domHelpers.getElementById('anomaly-results'));
            domHelpers.setInnerHTML(domHelpers.getElementById('anomaly-results'), '');
            domHelpers.hide(domHelpers.getElementById('report-result'));

            const saveBtn = domHelpers.getElementById('save-config-btn');
            if (saveBtn) domHelpers.disable(saveBtn);

            notifications.alert('Configuration cleared successfully');

        } catch (error) {
            console.error('Error clearing configuration:', error);
            notifications.alert(`Error: ${error.message}`);
        } finally {
            domHelpers.enable(button);
            if (btnText) btnText.textContent = 'Clear Configuration';
        }
    },

    updateConfigStatus(configured, data = null) {
        const statusDiv = domHelpers.getElementById('config-status');
        const detailsDiv = domHelpers.getElementById('config-status-details');

        domHelpers.show(statusDiv);

        if (configured && data) {
            statusDiv.className = 'config-status configured';
            detailsDiv.innerHTML = `
                <strong>Configured</strong><br>
                Cloud Provider: ${data.cloud_provider || 'Azure'}<br>
                Subscriptions: ${data.subscription_count || 0}<br>
                <small>Session expires after 30 minutes of inactivity</small>
            `;
        } else {
            statusDiv.className = 'config-status not-configured';
            detailsDiv.innerHTML = `
                <strong>Not Configured</strong><br>
                Please enter your credentials and save configuration to use the application.
            `;
        }
    },

    debugConfiguration() {
        console.log('=== Configuration Debug Info ===');
        console.log('Session ID:', sessionState.getSessionId());
        console.log('Is Configured:', sessionState.isSessionActive());
        console.log('SessionStorage:', sessionState.getStoredSessionId());

        const saveBtn = domHelpers.getElementById('save-config-btn');
        const testBtn = domHelpers.getElementById('test-connection-btn');

        console.log('Save Button:', {
            exists: !!saveBtn,
            disabled: saveBtn?.disabled,
            classList: saveBtn?.classList.toString()
        });

        console.log('Test Button:', {
            exists: !!testBtn,
            disabled: testBtn?.disabled,
            classList: testBtn?.classList.toString()
        });

        notifications.alert('Debug info logged to console. Press F12 to view.');
    }
};

// Global function for inline onclick handler
window.removeSubscription = function(button) {
    const currentCount = parseInt(domHelpers.getValue(domHelpers.getElementById('subscription-count')));
    if (currentCount > 1) {
        domHelpers.setValue(domHelpers.getElementById('subscription-count'), currentCount - 1);
        configuration.updateSubscriptionList();
    }
};