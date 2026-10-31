(() => {
    document.querySelectorAll('img[data-image-fallback]').forEach(img => {
        const fallback = () => {
            const url = img.dataset.imageFallback;
            if (!url) return;
            delete img.dataset.imageFallback;
            if (img.hasAttribute('data-fallback-icon')) {
                img.style.transform = 'none';
                img.style.padding = '10px';
                img.alt = 'WhatsApp support';
            }
            img.src = url;
        };
        img.addEventListener('error', fallback, {once: true});
        if (img.complete && !img.naturalWidth) fallback();
    });
    const checkout = document.querySelector('[data-checkout-form]');
    checkout?.querySelector('[name="delivery_zone"]')?.addEventListener('change', () => {
        checkout.requestSubmit(checkout.querySelector('button[name="action"][value="preview"]'));
    });
    const estimator = document.querySelector('[data-delivery-estimator]');
    if (estimator) {
        const result = document.querySelector('[data-delivery-result]');
        let controller;
        const quote = async event => {
            event?.preventDefault();
            controller?.abort();
            controller = new AbortController();
            result.textContent = 'Checking delivery…';
            try {
                const url = new URL(estimator.action);
                url.search = new URLSearchParams(new FormData(estimator));
                const response = await fetch(url, {signal: controller.signal});
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || 'Delivery estimate is unavailable. Please try again.');
                const heading = document.createElement('strong');
                heading.textContent = `${data.area} · ৳${data.shipping}`;
                const estimate = document.createElement('span');
                estimate.textContent = data.estimate;
                const note = document.createElement('span');
                note.textContent = data.note;
                result.replaceChildren(heading, estimate, note);
            } catch (error) {
                if (error.name !== 'AbortError') result.textContent = error.message;
            }
        };
        estimator.addEventListener('submit', quote);
        estimator.addEventListener('change', quote);
    }
    const builder = document.querySelector('[data-pc-builder]');
    if (builder) {
        const summary = document.querySelector('[data-build-summary]');
        let controller;
        builder.addEventListener('change', async () => {
            controller?.abort();
            controller = new AbortController();
            const url = new URL(builder.action);
            url.search = new URLSearchParams(new FormData(builder));
            history.replaceState(null, '', url);
            url.searchParams.set('format', 'json');
            summary.setAttribute('aria-busy', 'true');
            // Disable the previous quote's submit button while a new build is loading.
            const add = summary.querySelector('button');
            if (add) add.disabled = true;
            try {
                const response = await fetch(url, {signal: controller.signal});
                if (!response.ok) throw new Error();
                const data = await response.json();
                summary.innerHTML = data.html;
                summary.removeAttribute('aria-busy');
            } catch (error) {
                if (error.name === 'AbortError') return;
                summary.removeAttribute('aria-busy');
                let notice = summary.querySelector('[data-build-error]');
                if (!notice) { notice = document.createElement('p'); notice.dataset.buildError = ''; notice.setAttribute('role', 'alert'); summary.append(notice); }
                notice.textContent = 'Could not update your build. Use “Update build & checks” to try again.';
            }
        });
    }
})();
