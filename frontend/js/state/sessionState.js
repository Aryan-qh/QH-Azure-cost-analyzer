import { CONFIG } from '../config.js';

// Session state management
class SessionState {
    constructor() {
        this.sessionId = null;
        this.isConfigured = false;
    }

    setSession(sessionId) {
        this.sessionId = sessionId;
        this.isConfigured = true;
        sessionStorage.setItem(CONFIG.SESSION_STORAGE_KEY, sessionId);
        console.log('Session ID stored:', sessionId);
    }

    getSessionId() {
        return this.sessionId;
    }

    isSessionActive() {
        return this.isConfigured && this.sessionId !== null;
    }

    clearSession() {
        sessionStorage.removeItem(CONFIG.SESSION_STORAGE_KEY);
        this.sessionId = null;
        this.isConfigured = false;
    }

    getStoredSessionId() {
        return sessionStorage.getItem(CONFIG.SESSION_STORAGE_KEY);
    }
}

// Export singleton instance
export const sessionState = new SessionState();