// User notification system
export const notifications = {
    alert(message) {
        alert(message);
    },

    confirm(message) {
        return confirm(message);
    },

    showTestResult(success, message, elementId = 'test-result') {
        const resultDiv = document.getElementById(elementId);
        if (!resultDiv) return;

        resultDiv.style.display = 'block';
        resultDiv.className = success ? 'test-success' : 'test-error';
        
        const icon = success 
            ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"></path></svg>'
            : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>';
        
        resultDiv.innerHTML = `
            <span>${icon}</span>
            <span>${message}</span>
        `;
    },

    showError(message, containerId = 'anomaly-results') {
        const resultsDiv = document.getElementById(containerId);
        if (!resultsDiv) return;

        resultsDiv.innerHTML = `
            <div class="card error-message">
                <h3>Error</h3>
                <p>${message}</p>
            </div>
        `;
        resultsDiv.style.display = 'block';
        resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
    },

    clearTestResult(elementId = 'test-result') {
        const resultDiv = document.getElementById(elementId);
        if (resultDiv) {
            resultDiv.style.display = 'none';
            resultDiv.innerHTML = '';
        }
    }
};