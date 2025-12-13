import { GUID_PATTERN } from '../config.js';

// Validation utilities
export const validators = {
    validateGUID(value) {
        return GUID_PATTERN.test(value);
    },

    validateCredentials(tenantId, clientId, clientSecret) {
        if (!tenantId || !clientId || !clientSecret) {
            return { valid: false, message: 'All credential fields are required' };
        }

        if (!this.validateGUID(tenantId)) {
            return { valid: false, message: 'Tenant ID must be a valid GUID format' };
        }

        if (!this.validateGUID(clientId)) {
            return { valid: false, message: 'Client ID must be a valid GUID format' };
        }

        return { valid: true };
    },

    validateSubscriptions(container) {
        if (!container) {
            return { valid: false, message: 'Subscription list container not found' };
        }

        const subscriptionIdElements = Array.from(container.querySelectorAll('.subscription-id'));
        const subscriptionNameElements = Array.from(container.querySelectorAll('.subscription-name'));

        if (subscriptionIdElements.length === 0 || subscriptionNameElements.length === 0) {
            return { valid: false, message: 'No subscription fields found. Please set subscription count first.' };
        }

        const subscriptionIds = subscriptionIdElements
            .map(el => el.value ? el.value.trim() : '')
            .filter(val => val !== '');

        const subscriptionNames = subscriptionNameElements
            .map(el => el.value ? el.value.trim() : '')
            .filter(val => val !== '');

        if (subscriptionIds.length !== subscriptionIdElements.length) {
            return { valid: false, message: 'All subscription ID fields must be filled' };
        }

        if (subscriptionNames.length !== subscriptionNameElements.length) {
            return { valid: false, message: 'All subscription name fields must be filled' };
        }

        for (let i = 0; i < subscriptionIds.length; i++) {
            if (!this.validateGUID(subscriptionIds[i])) {
                return { valid: false, message: `Subscription ${i + 1} ID must be a valid GUID format` };
            }
        }

        const uniqueIds = new Set(subscriptionIds);
        if (uniqueIds.size !== subscriptionIds.length) {
            return { valid: false, message: 'Duplicate subscription IDs detected' };
        }

        return {
            valid: true,
            subscriptions: subscriptionIds.map((id, i) => ({
                id: id,
                name: subscriptionNames[i]
            }))
        };
    }
};