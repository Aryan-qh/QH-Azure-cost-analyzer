import { CONFIG } from '../config.js';

// API service for all backend communication
export const apiService = {
    // Validate existing session
    async validateSession(sessionId) {
        const response = await fetch(`${CONFIG.API_BASE_URL}/config/validate?session_id=${sessionId}`);
        if (!response.ok) {
            throw new Error('Session validation failed');
        }
        return await response.json();
    },

    // Test connection
    async testConnection(credentials) {
        const response = await fetch(`${CONFIG.API_BASE_URL}/config/test`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                tenant_id: credentials.tenantId,
                client_id: credentials.clientId,
                client_secret: credentials.clientSecret
            })
        });
        return await response.json();
    },

    // Save configuration
    async saveConfiguration(credentials, subscriptions) {
        const response = await fetch(`${CONFIG.API_BASE_URL}/config/save`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                cloud_provider: 'azure',
                tenant_id: credentials.tenantId,
                client_id: credentials.clientId,
                client_secret: credentials.clientSecret,
                subscriptions: subscriptions
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to save configuration');
        }

        return await response.json();
    },

    // Clear configuration
    async clearConfiguration(sessionId) {
        await fetch(`${CONFIG.API_BASE_URL}/config/clear`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId })
        }).catch(e => console.warn('Backend clear failed', e));
    },

    // Detect anomalies
    async detectAnomalies(sessionId, targetDate, threshold) {
        const response = await fetch(`${CONFIG.API_BASE_URL}/anomaly/detect`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                target_date: targetDate || null,
                threshold_percent: threshold
            })
        });

        if (response.status === 401) {
            throw new Error('Session expired. Please reconfigure your credentials.');
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to detect anomalies');
        }

        return await response.json();
    },

    // Generate cost report
    async generateCostReport(sessionId, numDays) {
        const response = await fetch(`${CONFIG.API_BASE_URL}/cost-report/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                session_id: sessionId,
                num_days: numDays
            })
        });

        if (response.status === 401) {
            throw new Error('Session expired. Please reconfigure your credentials.');
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to generate report');
        }

        return await response.json();
    }
};