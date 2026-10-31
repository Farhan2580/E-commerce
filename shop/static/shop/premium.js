(() => {
    'use strict';
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    const fine = matchMedia('(hover: hover) and (pointer: fine)');
    const themeButton = document.querySelector('[data-theme-toggle]');
    const syncTheme = () => {
        const dark = document.documentElement.dataset.theme === 'dark';
        themeButton?.setAttribute('aria-pressed', String(dark));
        themeButton?.setAttribute('aria-label', dark ? 'Switch to light theme' : 'Switch to dark theme');
    };
    syncTheme();
    themeButton?.addEventListener('click', () => {
        const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = theme;
        try { localStorage.setItem('gf-theme-v2', theme); } catch (_) {}
        syncTheme();
    });
    let hoverFrame = 0;
    let hoverPoint = null;
    const paintHover = () => {
        hoverFrame = 0;
        if (!hoverPoint || reduced.matches || !fine.matches) return;
        const {card, clientX, clientY} = hoverPoint;
        const box = card.getBoundingClientRect();
        if (!box.width || !box.height) return;
        const x = (clientX - box.left) / box.width - .5;
        const y = (clientY - box.top) / box.height - .5;
        card.style.setProperty('--lx', `${(x + .5) * 100}%`);
        card.style.setProperty('--ly', `${(y + .5) * 100}%`);
        card.style.setProperty('--px', `${x * 10}px`);
        card.style.setProperty('--py', `${y * 8}px`);
    };
    document.addEventListener('pointermove', event => {
        if (reduced.matches || !fine.matches) return;
        const card = event.target.closest('.gf-card, .gf-banner:not(.gf-banner-upload)');
        if (!card) return;
        hoverPoint = {card, clientX:event.clientX, clientY:event.clientY};
        if (!hoverFrame) hoverFrame = requestAnimationFrame(paintHover);
    }, {passive: true});
    document.addEventListener('pointerout', event => {
        const card = event.target.closest('.gf-card, .gf-banner');
        if (!card || card.contains(event.relatedTarget)) return;
        if (hoverPoint?.card === card) hoverPoint = null;
        ['--px', '--py', '--lx', '--ly'].forEach(key => card.style.removeProperty(key));
    });
    const seen = new WeakSet();
    const observer = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (!entry.isIntersecting) return;
            if (!reduced.matches) entry.target.classList.add('gf-reveal');
            observer.unobserve(entry.target);
        });
    }, {threshold: .05}) : null;
    const observe = () => document.querySelectorAll('.gf-card, .gf-section-heading, .gf-category-tiles > a').forEach((node, index) => {
        if (seen.has(node)) return;
        seen.add(node);
        node.style.setProperty('--stagger', `${index % 5 * 45}ms`);
        observer?.observe(node);
    });
    observe();
    new MutationObserver(observe).observe(document.querySelector('main'), {childList: true, subtree: true});
    const shop = window.gfShopping;
    const modal = document.querySelector('#gf-modal');
    const drawer = document.querySelector('#gf-cart-drawer');
    const loading = '<div class="gf-skeleton" role="status">Loading your shopping bag…</div>';
    let quickController, drawerController, drawerReturn, quickReturn;
    const lockScroll = () => document.body.classList.toggle('gf-dialog-open', !!document.querySelector('dialog[open]'));
    const openDrawer = opener => {
        drawerReturn = modal?.open ? quickReturn : opener || drawerReturn || document.querySelector('[data-open-cart]');
        if (modal?.open) modal.close();
        if (!drawer.open) drawer.showModal();
        lockScroll();
        drawer.querySelector('[data-close-dialog]').focus();
    };
    const loadDrawer = async (showLoading = true) => {
        drawerController?.abort();
        drawerController = new AbortController();
        const signal = drawerController.signal;
        const content = drawer.querySelector('[data-drawer-content]');
        if (showLoading) {
            content.setAttribute('aria-busy', 'true');
            content.innerHTML = loading;
            drawer.querySelector('[data-drawer-status]').hidden = true;
        }
        try {
            const result = await shop.requestJSON(drawer.dataset.url, {signal});
            if (!result.response.ok || !result.data.success) throw new Error('Unable to load your bag.');
            if (!signal.aborted) shop.applyCartState(result.data, {fromLoad: true});
        } catch (error) {
            if (error.name === 'AbortError') return;
            if (showLoading) {
                content.innerHTML = '<div class="gf-drawer-empty"><p role="alert">Your bag could not load. Your items have not been removed.</p><button type="button" class="gf-button gf-button-secondary" data-retry-drawer>Try again</button></div>';
                const link = document.createElement('a');
                link.className = 'gf-button gf-button-secondary';
                link.href = document.querySelector('[data-open-cart]').href;
                link.textContent = 'View full cart';
                content.append(link);
            }
        } finally {
            if (!signal.aborted) content.setAttribute('aria-busy', 'false');
        }
    };
    document.addEventListener('gf-cart-updated', event => {
        const detail = event.detail;
        if (!detail?.state) return;
        if (!detail.fromLoad) drawerController?.abort();
        if (detail.openDrawer && drawer?.showModal) openDrawer(detail.source);
        if (drawer.open) {
            const content = drawer.querySelector('[data-drawer-content]');
            const activeKey = content.contains(document.activeElement) ? document.activeElement.closest('[data-cart-key]')?.dataset.cartKey : null;
            content.innerHTML = detail.state.drawer_html;
            content.setAttribute('aria-busy', 'false');
            if (detail.fromDrawer || activeKey) shop.restoreCartFocus(content, detail.key || activeKey);
        }
    });
    document.addEventListener('click', async event => {
        const close = event.target.closest('[data-close-dialog]');
        if (close) close.closest('dialog').close();
        if (event.target.closest('[data-retry-drawer]')) { loadDrawer(); return; }
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0) return;
        const cartLink = event.target.closest('[data-open-cart]');
        if (cartLink && drawer?.showModal) {
            event.preventDefault();
            openDrawer(cartLink);
            loadDrawer();
        }
        const quickLink = event.target.closest('[data-quick-view]');
        if (!quickLink || !modal?.showModal) return;
        event.preventDefault();
        quickReturn = quickLink;
        quickController?.abort();
        quickController = new AbortController();
        const signal = quickController.signal;
        const content = modal.querySelector('[data-modal-content]');
        content.innerHTML = '<div class="gf-skeleton" role="status">Loading product…</div>';
        if (!modal.open) modal.showModal();
        lockScroll();
        try {
            const response = await fetch(quickLink.href, {signal});
            if (!response.ok) throw new Error();
            const html = await response.text();
            if (!signal.aborted && modal.open) content.innerHTML = html;
        } catch (error) {
            if (error.name !== 'AbortError') content.textContent = 'Quick view could not load. Close this window and open the product details.';
        }
    });
    [modal, drawer].forEach(dialog => {
        dialog?.addEventListener('keydown', event => {
            if (event.key !== 'Tab') return;
            const controls = [...dialog.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex="0"]')]
                .filter(node => node.getClientRects().length);
            const first = controls[0], last = controls[controls.length - 1];
            if (!first) return;
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault(); last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault(); first.focus();
            }
        });
        dialog?.addEventListener('click', event => {
            const rect = dialog.getBoundingClientRect();
            if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
        });
        dialog?.addEventListener('close', () => {
            if (dialog === modal) quickController?.abort(); else drawerController?.abort();
            lockScroll();
            if (document.querySelector('dialog[open]')) return;
            const opener = dialog === modal ? quickReturn : drawerReturn;
            const fallback = document.querySelector('[data-open-cart]');
            requestAnimationFrame(() => (opener?.isConnected ? opener : fallback)?.focus({preventScroll: true}));
        });
    });
    document.addEventListener('change', event => {
        const select = event.target.closest('[data-quick-variant]');
        if (!select) return;
        const option = select.selectedOptions[0];
        const form = select.closest('form');
        const stock = Number(option.dataset.stock || 0);
        form.querySelector('button').disabled = !select.value || stock === 0;
        form.querySelector('[name="quantity"]').max = Math.min(99, stock);
        if (select.value) {
            modal.querySelector('[data-quick-price]').textContent = option.dataset.price;
            modal.querySelector('[data-quick-stock]').textContent = stock > 0 ? `${stock} available` : 'Out of stock';
        }
    });
    const updateCountdowns = () => document.querySelectorAll('[data-countdown]').forEach(node => {
        const remaining = new Date(node.dateTime).getTime() - Date.now();
        if (!Number.isFinite(remaining)) return;
        if (remaining <= 0) { node.textContent = 'Offer ended. Refresh for current offers.'; return; }
        const hours = Math.floor(remaining / 3600000);
        const minutes = Math.floor(remaining / 60000) % 60;
        node.textContent = `${hours}h ${minutes}m remaining`;
    });
    updateCountdowns();
    setInterval(updateCountdowns, 60000);
    const comparePending = new Set();
    const applyComparison = (data, focus = false) => {
        document.querySelectorAll('[data-compare-count]').forEach(node => node.textContent = data.ids.length);
        document.querySelectorAll('[data-compare-form][data-product-id]').forEach(form => {
            const label = form.querySelector('[data-compare-label]');
            if (!label) return;
            const selected = data.ids.includes(Number(form.dataset.productId));
            form.querySelector('button').setAttribute('aria-pressed', String(selected));
            form.querySelector('[name="action"]').value = selected ? 'remove' : 'add';
            label.textContent = selected ? 'Compared' : form.classList.contains('gf-detail-compare') ? 'Add to Compare' : 'Compare';
        });
        const content = document.querySelector('[data-compare-content]');
        if (content && data.html !== undefined) {
            const scroll = content.querySelector('.gf-comparison-scroll')?.scrollLeft || 0;
            content.innerHTML = data.html;
            const region = content.querySelector('.gf-comparison-scroll');
            if (region) region.scrollLeft = scroll;
            if (focus) {
                content.tabIndex = -1;
                (content.querySelector('[data-compare-form] button') || content).focus({preventScroll: true});
            }
        }
        const status = document.querySelector('[data-compare-status]');
        if (status) status.textContent = data.ids.length ? data.ids.length + ' products selected for comparison.' : 'Comparison cleared.';
    };
    document.addEventListener('submit', async event => {
        const form = event.target.closest('[data-compare-form]');
        if (!form) return;
        event.preventDefault();
        const key = form.dataset.productId || 'clear';
        if (comparePending.has(key)) return;
        comparePending.add(key);
        const button = form.querySelector('button');
        const data = new FormData(form);
        const restore = !!form.closest('[data-compare-content]');
        button.disabled = true;
        form.setAttribute('aria-busy', 'true');
        try {
            await shop.enqueue(async () => {
                const result = await shop.requestJSON(form.getAttribute('action'), {method: 'POST', body: data});
                if (result.data.ids) applyComparison(result.data, restore);
                if (!result.response.ok || !result.data.success) throw new Error(result.data.error || 'Unable to update your comparison.');
                shop.notify(result.data.ids.length ? 'Comparison updated.' : 'Comparison cleared.');
                shop.publish('compare');
            });
        } catch (error) {
            shop.notify(error.message, true);
        } finally {
            comparePending.delete(key);
            button.disabled = false;
            form.removeAttribute('aria-busy');
        }
    });
    const refreshComparison = () => {
        const url = document.querySelector('[data-compare-content]')?.dataset.url || document.querySelector('.gf-compare-bar a').href;
        shop.requestJSON(url).then(result => { if (result.response.ok) applyComparison(result.data); }).catch(() => {});
    };
    const refreshWishlist = () => {
        const grid = document.querySelector('[data-wishlist-grid]');
        const url = new URL(document.querySelector('.gf-wishlist-link').href);
        if (grid) url.searchParams.set('cards', '1');
        shop.requestJSON(url).then(result => {
            if (!result.response.ok) return;
            if (grid) {
                grid.innerHTML = result.data.html;
                document.querySelector('[data-wishlist-empty]').hidden = !!grid.querySelector('.gf-card');
            }
            shop.syncWishlist(result.data.wishlist_ids);
        }).catch(() => {});
    };
    // Shopping state refreshes across tabs and after browser-history restoration.
    window.addEventListener('storage', event => {
        if (event.key !== 'gf-shopping-change') return;
        let change;
        try { change = JSON.parse(event.newValue); } catch (_) { return; }
        if (change?.type === 'cart') loadDrawer(false);
        if (change?.type === 'compare') refreshComparison();
        if (change?.type === 'wishlist') refreshWishlist();
    });
    window.addEventListener('pageshow', event => {
        if (!event.persisted) return;
        loadDrawer(false);
        refreshComparison();
        refreshWishlist();
    });
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && (drawer.open || document.querySelector('[data-cart-page]'))) loadDrawer(false);
    });
})();

(() => {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)');
    document.querySelectorAll('.gf-product-slider').forEach(section => {
        const rail = section.querySelector('.gf-product-rail');
        const controls = section.querySelector('.gf-slider-controls');
        if (!rail || !controls) return;
        const previous = controls.querySelector('[data-products-prev]');
        const next = controls.querySelector('[data-products-next]');
        const update = () => {
            const last = rail.scrollWidth - rail.clientWidth;
            controls.hidden = last <= 2;
            previous.disabled = rail.scrollLeft <= 2;
            next.disabled = rail.scrollLeft >= last - 2;
        };
        const move = direction => rail.scrollBy({left:direction * (rail.querySelector('.gf-card')?.getBoundingClientRect().width + 18 || rail.clientWidth), behavior:reduced.matches ? 'instant' : 'smooth'});
        previous.addEventListener('click', () => move(-1));
        next.addEventListener('click', () => move(1));
        rail.addEventListener('scroll', update, {passive:true});
        new MutationObserver(() => { rail.scrollLeft = 0; update(); }).observe(rail, {childList:true});
        if ('ResizeObserver' in window) new ResizeObserver(update).observe(rail);
        else window.addEventListener('resize', update);
        update();
    });
})();

(() => {
    const filters = document.querySelector('.gf-collection-filters');
    if (filters) {
        const small = matchMedia('(max-width:900px)');
        const update = () => { filters.open = !small.matches; };
        small.addEventListener('change', update);
        update();
        document.querySelectorAll('[data-facet-search]').forEach(input => input.addEventListener('input', () => {
            const query = input.value.toLowerCase().trim();
            input.closest('.gf-filter-group').querySelectorAll('.gf-filter-checkbox').forEach(label => {
                label.hidden = !label.textContent.toLowerCase().includes(query);
            });
        }));
    }
    document.querySelector('#collection-sort')?.addEventListener('change', event => event.target.form.requestSubmit());
})();
