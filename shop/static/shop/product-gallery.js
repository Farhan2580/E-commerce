(() => {
    'use strict';
    const variantSelect = document.querySelector('#variant-select');
    const choices = document.querySelector('.gf-variant-choices');
    if (variantSelect && choices) {
        choices.hidden = false;
        choices.querySelectorAll('[data-variant-choice]').forEach(button => button.addEventListener('click', () => {
            variantSelect.value = button.dataset.variantChoice;
            variantSelect.dispatchEvent(new Event('change', {bubbles:true}));
        }));
    }
    const quantity = document.querySelector('#detail-quantity');
    document.querySelectorAll('[data-detail-quantity-step]').forEach(button => {
        button.hidden = false;
        button.addEventListener('click', () => {
            const maximum = Number(quantity.max || 99);
            if (maximum < 1) return;
            quantity.value = Math.min(maximum, Math.max(1, Number(quantity.value || 1) + Number(button.dataset.detailQuantityStep)));
            quantity.dispatchEvent(new Event('change', {bubbles:true}));
        });
    });
    const links = [...document.querySelectorAll('[data-gallery-image]')];
    const main = document.querySelector('#detail-image');
    const zoom = document.querySelector('[data-gallery-zoom]');
    const viewer = document.querySelector('#gf-image-viewer');
    if (!main || !links.length || !viewer) return;
    let index = 0;
    let suppressZoom = false;
    const show = next => {
        index = (next + links.length) % links.length;
        const link = links[index], image = link.querySelector('img');
        main.src = link.dataset.galleryImage;
        main.alt = image.alt;
        zoom.href = main.src;
        links.forEach((item, position) => {
            if (position === index) item.setAttribute('aria-current', 'true');
            else item.removeAttribute('aria-current');
        });
        const count = `${index + 1} / ${links.length}`;
        document.querySelector('[data-gallery-counter]').textContent = count;
        viewer.querySelector('[data-viewer-counter]').textContent = count;
        viewer.querySelector('img').src = main.src;
        viewer.querySelector('img').alt = main.alt;
    };
    links.forEach((link, position) => link.addEventListener('click', event => {
        event.preventDefault(); show(position);
    }));
    document.addEventListener('gf-product-image', event => {
        const position = links.findIndex(link => link.dataset.galleryImage === event.detail?.url);
        if (position !== -1) show(position);
    });
    zoom.addEventListener('click', event => {
        if (suppressZoom) { event.preventDefault(); suppressZoom = false; return; }
        if (typeof viewer.showModal !== 'function') return;
        event.preventDefault(); viewer.showModal(); document.body.classList.add('gf-dialog-open');
    });
    viewer.querySelector('[data-close-viewer]').addEventListener('click', () => viewer.close());
    viewer.querySelector('[data-viewer-prev]').addEventListener('click', () => show(index - 1));
    viewer.querySelector('[data-viewer-next]').addEventListener('click', () => show(index + 1));
    viewer.addEventListener('keydown', event => {
        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
            event.preventDefault(); show(index + (event.key === 'ArrowRight' ? 1 : -1));
        }
    });
    viewer.addEventListener('click', event => { if (event.target === viewer) viewer.close(); });
    viewer.addEventListener('close', () => {
        document.body.classList.toggle('gf-dialog-open', Boolean(document.querySelector('dialog[open]')));
        zoom.focus();
    });
    const surface = document.querySelector('.gf-main-image');
    let touch = null;
    surface.addEventListener('touchstart', event => {
        suppressZoom = false;
        if (event.touches.length === 1) touch = {x:event.touches[0].clientX, y:event.touches[0].clientY};
    }, {passive:true});
    surface.addEventListener('touchend', event => {
        if (!touch || !event.changedTouches.length) return;
        const dx = event.changedTouches[0].clientX - touch.x;
        const dy = event.changedTouches[0].clientY - touch.y;
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            suppressZoom = true;
            show(index + (dx < 0 ? 1 : -1));
        }
        touch = null;
    }, {passive:true});
    surface.addEventListener('touchcancel', () => { touch = null; }, {passive:true});
    show(0);
    if (variantSelect?.value) variantSelect.dispatchEvent(new Event('change', {bubbles:true}));
})();
