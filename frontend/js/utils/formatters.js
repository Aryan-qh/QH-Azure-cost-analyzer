// Formatting utilities
export const formatters = {
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    },

    formatCurrency(amount) {
        return `$${amount.toFixed(2)}`;
    },

    formatPercentChange(value) {
        const sign = value >= 0 ? '+' : '';
        return `${sign}${value.toFixed(2)}%`;
    }
};