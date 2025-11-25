// Configuration
const API_BASE_URL = 'http://localhost:8000/api';

// Tab switching
document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
        const targetTab = tab.dataset.tab;
        
        // Update active tab
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        
        // Update active content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(`${targetTab}-tab`).classList.add('active');
    });
});

// Set today's date as default for anomaly detection
document.addEventListener('DOMContentLoaded', () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    document.getElementById('target-date').valueAsDate = yesterday;
});

// Anomaly Detection Form
document.getElementById('anomaly-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const btnText = submitBtn.querySelector('.btn-text');
    const spinner = submitBtn.querySelector('.spinner');
    
    // Show loading state
    submitBtn.disabled = true;
    btnText.textContent = 'Detecting...';
    spinner.style.display = 'inline-block';
    
    const targetDate = document.getElementById('target-date').value;
    const threshold = parseFloat(document.getElementById('threshold').value);
    
    try {
        const response = await fetch(`${API_BASE_URL}/anomaly/detect`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                target_date: targetDate || null,
                threshold_percent: threshold
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to detect anomalies');
        }
        
        const data = await response.json();
        displayAnomalyResults(data);
        
    } catch (error) {
        alert(`Error: ${error.message}`);
    } finally {
        // Reset button state
        submitBtn.disabled = false;
        btnText.textContent = 'Detect Anomalies';
        spinner.style.display = 'none';
    }
});

// Display Anomaly Results
function displayAnomalyResults(data) {
    const resultsDiv = document.getElementById('anomaly-results');
    const summaryBadge = document.getElementById('summary-badge');
    const summaryContent = document.getElementById('summary-content');
    const subscriptionResults = document.getElementById('subscription-results');
    
    resultsDiv.style.display = 'block';
    
    // Summary Badge
    const hasAnomalies = data.summary.anomaly_detected;
    summaryBadge.innerHTML = `
        <div class="badge ${hasAnomalies ? 'badge-danger' : 'badge-success'}">
            ${hasAnomalies ? '⚠️ Anomalies Detected' : '✓ All Normal'}
        </div>
    `;
    
    // Summary Stats
    summaryContent.innerHTML = `
        <div class="summary-stats">
            <div class="stat-box">
                <div class="label">Target Date</div>
                <div class="value">${formatDate(data.target_date)}</div>
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
        subscriptionResults.innerHTML += createSubscriptionCard(subName, subData);
    });
}

// Create Subscription Card
function createSubscriptionCard(name, data) {
    const hasAnomalies = data.has_anomalies;
    
    let tableRows = '';
    data.results.forEach(result => {
        const changeClass = result.percent_change >= 0 ? 'change-positive' : 'change-negative';
        tableRows += `
            <tr>
                <td>${result.category}</td>
                <td>$${result.average_cost.toFixed(2)}</td>
                <td>$${result.current_cost.toFixed(2)}</td>
                <td class="${changeClass}">${result.percent_change >= 0 ? '+' : ''}${result.percent_change.toFixed(2)}%</td>
                <td>
                    <span class="anomaly-indicator ${result.is_anomaly ? 'anomaly' : 'normal'}">
                        ${result.is_anomaly ? '⚠️ Anomaly' : '✓ Normal'}
                    </span>
                </td>
            </tr>
        `;
    });
    
    return `
        <div class="card subscription-card ${hasAnomalies ? 'has-anomaly' : ''}">
            <div class="subscription-header">
                <div class="subscription-name">${name}</div>
                ${hasAnomalies ? '<div class="badge badge-danger">⚠️ Action Required</div>' : '<div class="badge badge-success">✓ Normal</div>'}
            </div>
            <div style="color: var(--text-secondary); margin-bottom: 1rem;">
                Comparing ${formatDate(data.target_date)} against 7-day average (${formatDate(data.start_date)} to ${formatDate(data.end_date)})
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Category</th>
                        <th>7-Day Average</th>
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

// Cost Report Form
document.getElementById('report-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const btnText = submitBtn.querySelector('.btn-text');
    const spinner = submitBtn.querySelector('.spinner');
    const resultDiv = document.getElementById('report-result');
    
    // Show loading state
    submitBtn.disabled = true;
    btnText.textContent = 'Generating...';
    spinner.style.display = 'inline-block';
    resultDiv.style.display = 'none';
    
    const numDays = parseInt(document.getElementById('num-days').value);
    
    try {
        const response = await fetch(`${API_BASE_URL}/cost-report/generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                num_days: numDays
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to generate report');
        }
        
        const data = await response.json();
        displayReportResult(data);
        
    } catch (error) {
        alert(`Error: ${error.message}`);
    } finally {
        // Reset button state
        submitBtn.disabled = false;
        btnText.textContent = 'Generate Report';
        spinner.style.display = 'none';
    }
});

// Display Report Result
function displayReportResult(data) {
    const resultDiv = document.getElementById('report-result');
    const messageEl = document.getElementById('report-message');
    const downloadLink = document.getElementById('download-link');
    
    messageEl.textContent = data.message;
    downloadLink.href = `${API_BASE_URL}${data.download_url}`;
    downloadLink.download = data.filename;
    
    resultDiv.style.display = 'block';
    resultDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// Utility Functions
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric' 
    });
}