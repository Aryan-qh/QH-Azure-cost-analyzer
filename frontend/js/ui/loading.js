import { domHelpers } from '../utils/domHelpers.js';

// Loading state management
export const loading = {
    showLoading(button, loadingText = 'Loading...') {
        if (!button) return;

        const btnText = button.querySelector('.btn-text');
        const spinner = button.querySelector('.spinner');

        domHelpers.disable(button);
        if (btnText) btnText.textContent = loadingText;
        if (spinner) domHelpers.show(spinner);
    },

    hideLoading(button, defaultText) {
        if (!button) return;

        const btnText = button.querySelector('.btn-text');
        const spinner = button.querySelector('.spinner');

        domHelpers.enable(button);
        if (btnText) btnText.textContent = defaultText;
        if (spinner) domHelpers.hide(spinner);
    },

    setButtonState(buttonId, isLoading, loadingText, defaultText) {
        const button = domHelpers.getElementById(buttonId);
        if (isLoading) {
            this.showLoading(button, loadingText);
        } else {
            this.hideLoading(button, defaultText);
        }
    }
};