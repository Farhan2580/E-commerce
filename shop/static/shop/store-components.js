(() => {
    'use strict';
    const toast = (text, error = false) => {
        const node = document.querySelector('.gf-toast');
        if (!node) return;
        node.textContent = text;
        node.dataset.tone = error ? 'error' : 'success';
        node.hidden = false;
        clearTimeout(node._timeout);
        node._timeout = setTimeout(() => node.hidden = true, error ? 8000 : 4500);
    };
    const syncCount = count => {
        document.querySelectorAll('[data-cart-count]').forEach(node => node.textContent = count);
        document.querySelectorAll('[data-cart-unit]').forEach(node => node.textContent = count === 1 ? 'item' : 'items');
        document.querySelectorAll('.gf-cart').forEach(node => node.setAttribute('aria-label', 'Cart, ' + count + (count === 1 ? ' item' : ' items')));
    };
    // Session mutations share one queue, preventing overlapping writes in this page.
    let mutations = Promise.resolve();
    const enqueue = task => {
        const result = mutations.then(task, task);
        mutations = result.catch(() => {});
        return result;
    };
    const requestJSON = async (url, options = {}) => {
        const response = await fetch(url, {...options, credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json', ...options.headers}});
        if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Unable to update. Refresh the page and try again.');
        return {response, data: await response.json()};
    };
    const restoreCartFocus = (root, key) => {
        const rows = [...root.querySelectorAll('[data-cart-key]')];
        const row = rows.find(node => node.dataset.cartKey === key) || rows[0];
        const target = row?.querySelector('input[type="number"]') || root.querySelector('a, button');
        target?.focus({preventScroll: true});
    };
    const applyCartState = (data, detail = {}) => {
        if (!data.drawer_html) return;
        syncCount(data.cart_count);
        const page = document.querySelector('[data-cart-page]');
        if (page && data.cart_html) {
            const activeKey = page.contains(document.activeElement) ? document.activeElement.closest('[data-cart-key]')?.dataset.cartKey : null;
            page.innerHTML = data.cart_html;
            if (detail.fromPage || activeKey) restoreCartFocus(page, detail.key || activeKey);
        }
        document.dispatchEvent(new CustomEvent('gf-cart-updated', {detail: {...detail, state: data}}));
    };
    const publish = type => {
        try { localStorage.setItem('gf-shopping-change', JSON.stringify({type, at: Date.now(), nonce: Math.random()})); } catch (_) {}
    };
    const syncWishlist = ids => {
        document.querySelectorAll('[data-wishlist-count]').forEach(node => node.textContent = ids.length);
        document.querySelectorAll('.gf-wishlist-link').forEach(node => node.setAttribute('aria-label', 'Wishlist, ' + ids.length + ' saved products'));
        document.querySelectorAll('[data-wishlist-form]').forEach(form => {
            const saved = ids.includes(Number(form.dataset.productId));
            const button = form.querySelector('button');
            button.setAttribute('aria-pressed', String(saved));
            button.setAttribute('aria-label', (saved ? 'Remove ' : 'Save ') + form.dataset.productName + (saved ? ' from wishlist' : ' to wishlist'));
            form.querySelector('[name="action"]').value = saved ? 'remove' : 'save';
            button.querySelector('[data-wishlist-icon]').textContent = saved ? '♥' : '♡';
            const label = button.querySelector('[data-wishlist-label]');
            if (label) label.textContent = saved ? 'Saved to wishlist' : 'Save to wishlist';
        });
    };
    window.gfShopping = {enqueue, requestJSON, applyCartState, restoreCartFocus, syncWishlist, notify: toast, publish};
    const wishlistPending = new Set();
    document.addEventListener('submit', async event => {
        const form = event.target.closest('[data-wishlist-form]');
        if (!form) return;
        event.preventDefault();
        const id = form.dataset.productId;
        if (wishlistPending.has(id)) return;
        wishlistPending.add(id);
        const data = new FormData(form);
        const restoreWishlistFocus = !!form.closest('[data-wishlist-grid]') && form.contains(document.activeElement);
        const matchingButtons = () => [...document.querySelectorAll('[data-wishlist-form]')].filter(item => item.dataset.productId === id).map(item => item.querySelector('button'));
        matchingButtons().forEach(button => button.disabled = true);
        try {
            await enqueue(async () => {
                const result = await requestJSON(form.getAttribute('action'), {method: 'POST', body: data});
                if (result.response.status === 401) {
                    let link = form.parentElement.querySelector('[data-wishlist-signin]');
                    if (!link) {
                        link = document.createElement('a');
                        link.dataset.wishlistSignin = '';
                        link.className = 'gf-button gf-button-secondary';
                        form.after(link);
                    }
                    link.href = result.data.login_url;
                    link.textContent = 'Sign in to save your wishlist';
                    link.focus();
                    throw new Error('Sign in to save products to your account.');
                }
                if (!result.response.ok || !result.data.success) throw new Error(result.data.error || 'Unable to update your wishlist. Please try again.');
                syncWishlist(result.data.wishlist_ids);
                const grid = document.querySelector('[data-wishlist-grid]');
                if (grid && !result.data.saved) {
                    const card = [...grid.querySelectorAll('.gf-card')].find(node => node.dataset.productId === id);
                    const restore = restoreWishlistFocus || card?.contains(document.activeElement);
                    card?.remove();
                    const empty = document.querySelector('[data-wishlist-empty]');
                    empty.hidden = !!grid.querySelector('.gf-card');
                    if (restore) (grid.querySelector('[data-wishlist-form] button') || empty.querySelector('a'))?.focus();
                }
                toast(result.data.saved ? 'Saved to your wishlist.' : 'Removed from your wishlist.');
                publish('wishlist');
            });
        } catch (error) {
            toast(error.message, true);
        } finally {
            wishlistPending.delete(id);
            matchingButtons().forEach(button => button.disabled = false);
        }
    });
    document.addEventListener('click', event => {
        const button = event.target.closest('[data-quantity-step]');
        if (!button || button.disabled) return;
        const form = button.closest('form');
        const input = form.querySelector('input[type="number"]');
        input.value = Math.max(0, Math.min(Number(input.max), Number(input.value) + Number(button.dataset.quantityStep)));
        form.requestSubmit(form.querySelector('button[type="submit"]'));
    });
    document.addEventListener('submit', async event => {
        const form = event.target.closest('[data-cart-form], [data-cart-change]');
        if (!form) return;
        event.preventDefault();
        if (form.dataset.busy) return;
        const isAdd = form.hasAttribute('data-cart-form');
        const button = form.querySelector('button[type="submit"], button:not([type])');
        const label = button.textContent;
        const data = new FormData(form);
        const detail = {openDrawer: isAdd, source: button, fromPage: !!form.closest('[data-cart-page]'),
            fromDrawer: !!form.closest('#gf-cart-drawer'), key: form.closest('[data-cart-key]')?.dataset.cartKey};
        const controls = [...form.querySelectorAll('button')].map(node => [node, node.disabled]);
        form.dataset.busy = 'true';
        form.setAttribute('aria-busy', 'true');
        controls.forEach(([node]) => node.disabled = true);
        button.textContent = isAdd ? 'Adding…' : 'Updating…';
        document.querySelectorAll('[data-drawer-status], [data-cart-page-status]').forEach(node => node.hidden = true);
        try {
            await enqueue(async () => {
                const result = await requestJSON(form.getAttribute('action'), {method: 'POST', body: data});
                if (!result.response.ok || !result.data.success) {
                    applyCartState(result.data, {...detail, openDrawer: false});
                    throw new Error(result.data.error || 'Unable to update your bag. Please try again.');
                }
                applyCartState(result.data, detail);
                toast(isAdd ? 'Added to your bag.' : 'Shopping bag updated.');
                const status = form.querySelector('.gf-form-status');
                if (status) status.textContent = 'Added to your bag.';
                publish('cart');
            });
        } catch (error) {
            toast(error.message, true);
            const status = form.querySelector('.gf-form-status');
            if (status) status.textContent = error.message;
            document.querySelectorAll('[data-drawer-status], [data-cart-page-status]').forEach(node => {
                node.textContent = error.message;
                node.hidden = false;
            });
        } finally {
            delete form.dataset.busy;
            form.removeAttribute('aria-busy');
            button.textContent = label;
            controls.forEach(([node, disabled]) => node.disabled = disabled);
            if (isAdd) form.dispatchEvent(new Event('cart-complete'));
        }
    });

    document.querySelectorAll('[data-checkout-form]').forEach(form => {
        const button = form.querySelector('[data-place-order]');
        const updatePayment = () => {
            if (form.dataset.processing === 'true') return;
            const selected = form.querySelector('[name="payment_method"]:checked:not(:disabled)');
            button.disabled = !selected || button.hasAttribute('data-payments-disabled');
            button.textContent = ['COD', 'BKASH'].includes(selected?.value) ? 'Place Order' : button.dataset.payLabel;
            form.querySelectorAll('[data-payment-help]').forEach(help => {
                const input = form.querySelector(`[name="payment_method"][value="${help.dataset.paymentHelp}"]`);
                help.hidden = !input.disabled && input !== selected;
            });
        };
        form.addEventListener('change', updatePayment);
        form.addEventListener('submit', event => {
            if (form.dataset.processing === 'true') { event.preventDefault(); return; }
            if (event.submitter?.value === 'preview') return;
            if (!form.querySelector('[name="payment_method"]:checked:not(:disabled)')) {
                event.preventDefault();
                form.querySelector('.gf-form-status').textContent = 'Choose an available payment method.';
                return;
            }
            form.dataset.processing = 'true';
            form.setAttribute('aria-busy', 'true');
            button.disabled = true;
            button.textContent = 'Processing…';
            form.querySelector('.gf-form-status').textContent = 'Submitting your order. Please wait.';
        });
        window.addEventListener('pageshow', () => {
            delete form.dataset.processing;
            form.removeAttribute('aria-busy');
            form.querySelector('.gf-form-status').textContent = '';
            updatePayment();
        });
        updatePayment();
    });

    document.querySelectorAll('[data-copy-receiver]').forEach(button => {
        button.addEventListener('click', async () => {
            const paragraph = button.closest('p');
            try {
                await navigator.clipboard.writeText(paragraph.querySelector('[data-copy-value]').textContent.trim());
                paragraph.querySelector('[data-copy-status]').textContent = 'Number copied.';
            } catch (_) {
                paragraph.querySelector('[data-copy-status]').textContent = 'Select the receiving number above to copy it.';
            }
        });
    });
    document.querySelectorAll('[data-payment-action]').forEach(form => {
        form.addEventListener('submit', event => {
            if (form.dataset.processing) { event.preventDefault(); return; }
            form.dataset.processing = 'true';
            form.setAttribute('aria-busy', 'true');
            form.querySelector('button').disabled = true;
        });
        window.addEventListener('pageshow', () => {
            delete form.dataset.processing;
            form.removeAttribute('aria-busy');
            form.querySelector('button').disabled = false;
        });
    });
    const mobile = document.querySelector('#mobile-menu');
    document.querySelectorAll('[data-open-menu]').forEach(link => link.addEventListener('click', event => {
        if (!mobile) return;
        event.preventDefault();
        mobile.open = true;
        mobile.querySelector('summary').focus();
    }));
    document.querySelectorAll('[data-close-menu]').forEach(button => button.addEventListener('click', () => {
        mobile.open = false;
        mobile.querySelector('summary').focus();
    }));
    document.addEventListener('click', event => {
        document.querySelectorAll('.gf-account[open], .gf-category-menu details[open], .gf-mobile-menu[open]').forEach(details => {
            if (!details.contains(event.target) && !event.target.closest('[data-open-menu]') && !event.target.closest('[data-mobile-menu-dialog]')) details.open = false;
        });
    });
    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        document.querySelectorAll('.gf-account[open], .gf-mobile-menu[open], .gf-category-menu details[open]').forEach(details => {
            details.open = false;
            details.querySelector('summary').focus();
        });
    });

    const search = document.querySelector('#nav-search');
    const suggestions = document.querySelector('#search-suggestions');
    if (search && suggestions) {
        let timer, controller;
        const close = () => {
            suggestions.hidden = true;
            search.setAttribute('aria-expanded', 'false');
        };
        const load = async () => {
            if (controller) controller.abort();
            const query = search.value.trim();
            if (query.length < 2) {
                close();
                return;
            }
            controller = new AbortController();
            const signal = controller.signal;
            suggestions.hidden = false;
            search.setAttribute('aria-expanded', 'true');
            const items = suggestions.querySelector('[data-suggestion-items]');
            const status = suggestions.querySelector('[role="status"]');
            items.replaceChildren();
            status.textContent = 'Searching…';
            try {
                const response = await fetch(search.dataset.suggestUrl + '?q=' + encodeURIComponent(query), {signal});
                if (!response.ok) throw new Error('Search unavailable');
                const data = await response.json();
                if (signal.aborted) return;
                status.textContent = data.products.length ? 'Matching products' : 'No matches. Try a different search.';
                data.products.forEach(product => {
                    const link = document.createElement('a');
                    link.href = product.url;
                    if (product.image) {
                        const image = document.createElement('img');
                        image.src = product.image;
                        image.alt = '';
                        image.width = 44;
                        image.height = 44;
                        link.append(image);
                    }
                    const text = document.createElement('span');
                    const name = document.createElement('strong');
                    name.textContent = product.name;
                    const price = document.createElement('small');
                    price.textContent = '৳' + product.price;
                    text.append(name, price);
                    link.append(text);
                    items.append(link);
                });
            } catch (error) {
                if (error.name !== 'AbortError') status.textContent = 'Suggestions unavailable. Press Search to browse results.';
            }
        };
        search.addEventListener('input', () => {
            clearTimeout(timer);
            if (controller) controller.abort();
            if (search.value.trim().length < 2) close();
            else timer = setTimeout(load, 200);
        });
        search.addEventListener('keydown', event => {
            if (event.key === 'ArrowDown' && !suggestions.hidden) {
                const first = suggestions.querySelector('a');
                if (first) {
                    event.preventDefault();
                    first.focus();
                }
            }
            if (event.key === 'Escape') {
                close();
            }
        });
        suggestions.addEventListener('keydown', event => {
            const links = [...suggestions.querySelectorAll('a')];
            const index = links.indexOf(document.activeElement);
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                const next = event.key === 'ArrowDown' ? index + 1 : index - 1;
                if (next < 0) search.focus(); else links[Math.min(next, links.length - 1)]?.focus();
            }
            if (event.key === 'Escape') {
                close();
                search.focus();
            }
        });
        document.addEventListener('click', event => {
            if (!event.target.closest('.gf-search-wrap')) close();
        });
    }

    document.querySelectorAll('[data-carousel]').forEach(carousel => {
        const slides = [...carousel.querySelectorAll('[data-slide]')];
        if (slides.length < 2) return;
        let index = 0;
        carousel.dataset.enhanced = 'true';
        carousel.tabIndex = 0;
        const show = next => {
            index = (next + slides.length) % slides.length;
            slides.forEach((slide, i) => {
                slide.hidden = i !== index;
            });
            carousel.querySelectorAll('[data-slide-index]').forEach((button, i) => button.setAttribute('aria-pressed', String(i === index)));
        };
        carousel.querySelector('[data-slide-prev]').addEventListener('click', () => show(index - 1));
        carousel.querySelector('[data-slide-next]').addEventListener('click', () => show(index + 1));
        carousel.querySelectorAll('[data-slide-index]').forEach(button => button.addEventListener('click', () => show(Number(button.dataset.slideIndex))));
        carousel.addEventListener('keydown', event => {
            if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
                event.preventDefault();
                show(index + (event.key === 'ArrowRight' ? 1 : -1));
            }
        });
    });

    document.querySelectorAll('[data-section-tab]').forEach(link => link.addEventListener('click', async event => {
        event.preventDefault();
        const section = link.closest('[data-product-section]');
        const grid = section.querySelector('[data-section-grid]');
        const status = section.querySelector('[role="status"]');
        if (section._controller) section._controller.abort();
        section._controller = new AbortController();
        const signal = section._controller.signal;
        grid.setAttribute('aria-busy', 'true');
        status.classList.remove('gf-sr-only');
        status.textContent = 'Loading products…';
        try {
            const response = await fetch(link.dataset.sectionTab, {signal});
            if (!response.ok) throw new Error('Could not load this category. Try again or follow the section’s View all link.');
            const data = await response.json();
            if (signal.aborted) return;
            grid.innerHTML = data.html;
            section.querySelectorAll('[data-section-tab]').forEach(tab => tab.removeAttribute('aria-current'));
            link.setAttribute('aria-current', 'true');
            status.textContent = 'Products updated.';
            status.classList.add('gf-sr-only');
            history.replaceState(null, '', link.href);
        } catch (error) {
            if (error.name !== 'AbortError') status.textContent = error.message;
        } finally {
            if (!signal.aborted) grid.removeAttribute('aria-busy');
        }
    }));

    const select = document.querySelector('#variant-select');
    if (select) {
        const variants = JSON.parse(document.querySelector('#product-variants').textContent);
        const form = select.closest('form');
        const button = form.querySelector('[data-detail-cart]');
        const qty = form.querySelector('[name="quantity"]');
        const money = value => new Intl.NumberFormat('en-US', {maximumFractionDigits:2}).format(Number(value));
        const update = () => {
            const variant = variants.find(variant => String(variant.id) === select.value);
            button.disabled = !variant || variant.stock === 0;
            const price = document.querySelector('[data-detail-price]');
            const original = document.querySelector('[data-detail-original]');
            const discount = document.querySelector('[data-detail-discount]');
            const currentPrice = variant ? Number(variant.price) : Number(price.dataset.basePrice);
            const originalPrice = variant ? Number(variant.original || 0) : Number(original.dataset.baseOriginal || 0);
            if (discount) {
                discount.hidden = originalPrice <= currentPrice;
                discount.textContent = '৳' + money(Math.max(0, originalPrice - currentPrice)) + ' OFF';
            }
            document.querySelectorAll('[data-variant-choice]').forEach(choice => choice.setAttribute('aria-pressed', String(choice.dataset.variantChoice === select.value)));
            if (!variant) {
                price.textContent = money(price.dataset.basePrice);
                original.hidden = !Number(original.dataset.baseOriginal) || Number(original.dataset.baseOriginal) <= Number(price.dataset.basePrice);
                original.textContent = '৳' + money(original.dataset.baseOriginal || 0);
                document.querySelector('[data-detail-sku]').textContent = 'Choose an option';
                document.querySelector('[data-detail-stock]').textContent = 'Select an option to see stock and price.';
                qty.max = 99;
                document.dispatchEvent(new CustomEvent('gf-product-image', {detail:{url:form.dataset.defaultImage}}));
                return;
            }
            price.textContent = money(variant.price);
            document.querySelector('[data-detail-sku]').textContent = variant.sku || 'Not provided';
            original.hidden = !variant.original || Number(variant.original) <= Number(variant.price);
            original.textContent = '৳' + money(variant.original || 0);
            document.dispatchEvent(new CustomEvent('gf-product-image', {detail:{url:variant.image || form.dataset.defaultImage}}));
            document.querySelector('[data-detail-stock]').textContent = variant.stock ? 'In stock · ' + variant.stock + ' available' : 'Out of stock';
            qty.max = Math.min(99, variant.stock);
            if (variant.stock && Number(qty.value) > variant.stock) qty.value = Math.min(99, variant.stock);
        };
        select.addEventListener('change', update);
        form.addEventListener('cart-complete', update);
        update();
    }
})();

(() => {
    const menus = [...document.querySelectorAll('.gf-category-menu')];
    const closeOthers = current => menus.forEach(menu => {
        const details = menu.querySelector('details');
        if (details && details !== current) details.open = false;
    });
    menus.forEach(menu => {
        const details = menu.querySelector('details');
        if (!details) return;
        menu.addEventListener('pointerenter', () => {
            if (!matchMedia('(hover: hover) and (pointer: fine)').matches) return;
            closeOthers(details);
            details.open = true;
        });
        menu.addEventListener('pointerleave', () => {
            if (matchMedia('(hover: hover) and (pointer: fine)').matches && !menu.contains(document.activeElement)) details.open = false;
        });
        menu.addEventListener('focusout', event => {
            if (!menu.contains(event.relatedTarget)) details.open = false;
        });
        details.querySelector('summary').addEventListener('click', () => closeOthers(details));
    });
})();
