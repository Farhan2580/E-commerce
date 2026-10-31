(() => {
    'use strict';
    document.querySelectorAll('[data-brand-logo]').forEach(image => {
        const fallback = () => {
            image.hidden = true;
            const label = image.parentElement.querySelector('[data-brand-fallback]');
            if (label) label.hidden = false;
        };
        image.addEventListener('error', fallback, {once:true});
        if (image.complete && !image.naturalWidth) fallback();
    });

    const select = document.querySelector('#variant-select');
    const groups = document.querySelector('[data-option-groups]');
    if (select && groups) {
        const variants = JSON.parse(document.querySelector('#product-variants').textContent);
        const buttons = Array.from(groups.querySelectorAll('[data-option-field]'));
        const fields = [...new Set(buttons.map(button => button.dataset.optionField))];
        const status = groups.querySelector('[data-option-status]');
        let chosen = {};
        const paint = () => {
            buttons.forEach(button => {
                const field = button.dataset.optionField, value = button.dataset.optionValue;
                button.setAttribute('aria-pressed', String(chosen[field] === value));
                const matches = variants.filter(variant => fields.every(key => variant[key] === (key === field ? value : chosen[key])));
                button.dataset.available = String(matches.some(variant => variant.stock > 0));
                button.title = matches.length ? matches.some(variant => variant.stock > 0) ? '' : 'This combination is out of stock' : 'Not offered with the other selected options';
            });
        };
        const sync = () => {
            const variant = variants.find(variant => String(variant.id) === select.value);
            if (variant) chosen = Object.fromEntries(fields.map(field => [field, variant[field]]));
            paint();
        };
        sync();
        groups.hidden = false;
        document.querySelector('[data-native-variant]').hidden = true;
        buttons.forEach(button => button.addEventListener('click', () => {
            chosen[button.dataset.optionField] = button.dataset.optionValue;
            const variant = variants.find(variant => fields.every(field => variant[field] === chosen[field]));
            select.value = variant ? String(variant.id) : '';
            select.dispatchEvent(new Event('change', {bubbles:true}));
            status.textContent = variant ? variant.stock > 0 ? '' : 'This option is out of stock. You can request a stock alert below.' : 'This combination is not offered. Choose different options.';
            paint();
        }));
        select.addEventListener('change', sync);
    }

    const nav = document.querySelector('[data-product-tabs]');
    if (!nav) return;
    const tabs = Array.from(nav.querySelectorAll('a[href^="#"]'));
    const panels = tabs.map(tab => document.getElementById(tab.hash.slice(1)));
    if (panels.some(panel => !panel)) return;
    nav.setAttribute('role', 'tablist');
    const activate = (id, focus=false, updateURL=false) => {
        const index = panels.findIndex(panel => panel.id === id);
        if (index === -1) return;
        tabs.forEach((tab, position) => {
            tab.setAttribute('aria-selected', String(position === index));
            tab.tabIndex = position === index ? 0 : -1;
            panels[position].hidden = position !== index;
        });
        if (focus) tabs[index].focus();
        if (updateURL) history.replaceState(null, '', '#' + id);
    };
    tabs.forEach((tab, index) => {
        tab.id = 'tab-' + panels[index].id;
        tab.setAttribute('role','tab');
        tab.setAttribute('aria-controls', panels[index].id);
        panels[index].setAttribute('role','tabpanel');
        panels[index].setAttribute('aria-labelledby', tab.id);
        panels[index].tabIndex = 0;
        tab.addEventListener('keydown', event => {
            const position = tabs.indexOf(document.activeElement);
            const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : event.key === 'ArrowRight' ? (position + 1) % tabs.length : event.key === 'ArrowLeft' ? (position + tabs.length - 1) % tabs.length : -1;
            if (next !== -1) { event.preventDefault(); activate(panels[next].id, true, true); }
        });
    });
    document.addEventListener('click', event => {
        const link = event.target.closest('a[href^="#"]');
        if (!link || !panels.some(panel => panel.id === link.hash.slice(1))) return;
        event.preventDefault();
        activate(link.hash.slice(1), nav.contains(link), true);
        if (!nav.contains(link)) nav.scrollIntoView({block:'start'});
    });
    window.addEventListener('hashchange', () => activate(location.hash.slice(1)));
    activate(nav.dataset.defaultTab === 'reviews' ? 'reviews' : panels.some(panel => panel.id === location.hash.slice(1)) ? location.hash.slice(1) : nav.dataset.defaultTab);
})();
