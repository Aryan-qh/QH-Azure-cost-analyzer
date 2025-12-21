// DOM manipulation utilities
export const domHelpers = {
    getElementById(id) {
        return document.getElementById(id);
    },

    querySelector(selector) {
        return document.querySelector(selector);
    },

    querySelectorAll(selector) {
        return document.querySelectorAll(selector);
    },

    show(element) {
        if (element) element.style.display = 'block';
    },

    hide(element) {
        if (element) element.style.display = 'none';
    },

    addClass(element, className) {
        if (element) element.classList.add(className);
    },

    removeClass(element, className) {
        if (element) element.classList.remove(className);
    },

    hasClass(element, className) {
        return element ? element.classList.contains(className) : false;
    },

    setInnerHTML(element, html) {
        if (element) element.innerHTML = html;
    },

    setValue(element, value) {
        if (element) element.value = value;
    },

    getValue(element) {
        return element ? element.value : '';
    },

    disable(element) {
        if (element) element.disabled = true;
    },

    enable(element) {
        if (element) element.disabled = false;
    },

    scrollIntoView(element, options = { behavior: 'smooth', block: 'start' }) {
        if (element) element.scrollIntoView(options);
    },

    clearInputs(selector) {
        this.querySelectorAll(selector).forEach(input => input.value = '');
    }
};