// Configuration constants
export const CONFIG = {
    API_BASE_URL: 'http://localhost:8000/api',
    SESSION_STORAGE_KEY: 'azure_cost_session_id',
    MAX_SUBSCRIPTIONS: 20,
    MIN_SUBSCRIPTIONS: 1,
    DEFAULT_THRESHOLD: 25,
    DEFAULT_REPORT_DAYS: 7
};

export const GUID_PATTERN = /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

export const CLOUD_PROVIDERS = {
    AZURE: 'azure',
    GCP: 'gcp',
    AWS: 'aws'
};