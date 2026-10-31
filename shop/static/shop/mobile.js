(() => {
    'use strict';
    const phone = matchMedia('(max-width:760px)');
    if (typeof HTMLDialogElement === 'undefined') return;
    document.documentElement.classList.add('gf-mobile-ready');
    const syncScroll = () => document.body.classList.toggle('gf-dialog-open', !!document.querySelector('dialog[open]'));
    const closeIcon = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
    const menu = document.querySelector('#mobile-menu');
    const drawer = menu?.querySelector('.gf-mobile-drawer');
    if (menu && drawer) {
        const modal = document.createElement('dialog');
        modal.className = 'gf-mobile-menu-dialog';
        modal.id = 'gf-mobile-categories';
        modal.dataset.mobileMenuDialog = '';
        modal.setAttribute('aria-label', 'Browse GadgetFlow');
        document.body.append(modal);
        const summary = menu.querySelector(':scope > summary');
        drawer.querySelectorAll('.gf-mobile-category').forEach(group => {
            group.addEventListener('toggle', () => {
                if (!group.open || !phone.matches) return;
                drawer.querySelectorAll('.gf-mobile-category[open]').forEach(other => {
                    if (other !== group) other.open = false;
                });
            });
        });
        let opener = summary;
        document.addEventListener('click', event => {
            const target = event.target.closest('[data-open-menu], #mobile-menu > summary');
            if (target) opener = target;
        }, true);
        document.querySelectorAll('[data-open-menu], #mobile-menu > summary').forEach(node => {
            node.setAttribute('aria-controls', modal.id);
            node.setAttribute('aria-haspopup', 'dialog');
        });
        const syncMenu = () => {
            if (phone.matches && menu.open && !modal.open) {
                modal.append(drawer);
                modal.showModal();
                drawer.querySelector('[data-close-menu]').focus();
            } else if ((!menu.open || !phone.matches) && modal.open) modal.close();
            document.querySelector('[data-mobile-nav="categories"]')?.setAttribute('aria-expanded', String(menu.open));
            syncScroll();
        };
        menu.addEventListener('toggle', syncMenu);
        modal.addEventListener('close', () => {
            menu.append(drawer);
            menu.open = false;
            document.querySelector('[data-mobile-nav="categories"]')?.setAttribute('aria-expanded', 'false');
            syncScroll();
            const target = opener?.getClientRects().length ? opener : summary;
            if (target.getClientRects().length) target.focus({preventScroll:true});
        });
        modal.addEventListener('click', event => { if (event.target === modal) modal.close(); });
        phone.addEventListener('change', syncMenu);
    }
    const filters = document.querySelector('.gf-collection-filters');
    const filterButton = document.querySelector('[data-open-filters]');
    if (filters && filterButton) {
        const placeholder = document.createComment('Collection filters');
        filters.before(placeholder);
        const summary = filters.querySelector(':scope > summary');
        const modal = document.createElement('dialog');
        modal.className = 'gf-mobile-filter-dialog';
        modal.id = 'gf-mobile-filters';
        modal.setAttribute('aria-label', 'Product filters');
        filterButton.setAttribute('aria-controls', modal.id);
        filterButton.setAttribute('aria-haspopup', 'dialog');
        modal.innerHTML = `<div class="gf-mobile-filter-title"><h2>Refine your search</h2><button type="button" aria-label="Close filters">${closeIcon}</button></div>`;
        document.body.append(modal);
        const restore = () => {
            placeholder.after(filters);
            summary.hidden = false;
            filters.open = !matchMedia('(max-width:900px)').matches;
            syncScroll();
            if (phone.matches) filterButton.focus({preventScroll:true});
        };
        const sync = () => {
            filterButton.hidden = !phone.matches;
            if (!phone.matches && modal.open) modal.close();
        };
        filterButton.addEventListener('click', () => {
            modal.append(filters);
            summary.hidden = true;
            filters.open = true;
            modal.showModal();
            modal.querySelector('button').focus();
            syncScroll();
        });
        modal.querySelector('button').addEventListener('click', () => modal.close());
        modal.addEventListener('click', event => { if (event.target === modal) modal.close(); });
        modal.addEventListener('close', restore);
        phone.addEventListener('change', sync);
        sync();
    }
    const path = location.pathname;
    const active = path === '/' ? 'home' : path.startsWith('/cart') || path.startsWith('/checkout') ? 'cart' : path.startsWith('/wishlist') ? 'wishlist' : ['/profile', '/login', '/signup', '/register', '/order', '/my-orders', '/track-order'].some(prefix => path.startsWith(prefix)) ? 'account' : ['/product', '/pc-builder', '/offers'].some(prefix => path.startsWith(prefix)) ? 'categories' : '';
    document.querySelectorAll('[data-mobile-nav]').forEach(link => {
        if (link.dataset.mobileNav === active) link.setAttribute('aria-current', active === 'categories' ? 'true' : 'page');
        else link.removeAttribute('aria-current');
    });
    const checkoutBag = document.querySelector('.gf-checkout-bag-details');
    if (checkoutBag) {
        const syncBag = () => { checkoutBag.open = !phone.matches; };
        phone.addEventListener('change', syncBag);
        syncBag();
    }
    const bar = document.querySelector('[data-mobile-buybar]');
    const form = document.querySelector('.gf-buy-form');
    const original = form?.querySelector('[data-detail-cart]');
    if (bar && form && original && 'IntersectionObserver' in window) {
        const price = document.querySelector('[data-detail-price]');
        const variant = form.querySelector('[name="variant"]');
        const button = bar.querySelector('[data-mobile-buy]');
        let formVisible = false;
        const sync = () => {
            bar.hidden = !phone.matches || formVisible;
            bar.querySelector('[data-mobile-price]').textContent = '৳' + price.textContent.trim();
            button.disabled = original.disabled;
            button.firstChild.textContent = variant && !variant.value ? 'Choose option ' : original.disabled ? original.textContent.trim() + ' ' : 'Add to bag ';
        };
        new IntersectionObserver(entries => {
            formVisible = entries[0].isIntersecting && entries[0].intersectionRect.height >= 32;
            sync();
        }, {rootMargin:'-120px 0px -68px 0px', threshold:[0,.7,1]}).observe(original);
        new MutationObserver(sync).observe(original, {attributes:true, childList:true, subtree:true});
        new MutationObserver(sync).observe(price, {childList:true, subtree:true});
        form.addEventListener('change', sync);
        phone.addEventListener('change', sync);
        button.addEventListener('click', () => {
            if (variant && !variant.value) {
                form.scrollIntoView({block:'center', behavior:matchMedia('(prefers-reduced-motion:reduce)').matches ? 'instant' : 'smooth'});
                variant.focus({preventScroll:true});
                variant.reportValidity();
                return;
            }
            form.requestSubmit(original);
        });
        sync();
    }
    if (window.visualViewport) {
        const keyboard = () => {
            const editing = document.activeElement?.matches('input, textarea, select');
            document.body.classList.toggle('gf-mobile-keyboard', phone.matches && editing && visualViewport.height < innerHeight * .75);
        };
        visualViewport.addEventListener('resize', keyboard);
        document.addEventListener('focusin', keyboard);
        document.addEventListener('focusout', () => requestAnimationFrame(keyboard));
    }
})();
