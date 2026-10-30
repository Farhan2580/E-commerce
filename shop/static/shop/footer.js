(() => {
    const sections = document.querySelectorAll('.gf-footer-section');
    const mobile = matchMedia('(max-width: 640px)');
    function update() {
        sections.forEach(section => { section.open = !mobile.matches; });
    }
    sections.forEach(section => section.addEventListener('click', event => {
        if (!mobile.matches && event.target.closest('summary')) event.preventDefault();
    }));
    mobile.addEventListener('change', update);
    update();
    const shortcut = document.querySelector('.gf-whatsapp-shortcut');
    document.body.classList.toggle('gf-has-whatsapp', Boolean(shortcut));
    shortcut?.querySelector('.gf-whatsapp-dismiss')?.addEventListener('click', () => {
        shortcut.hidden = true;
        document.body.classList.remove('gf-has-whatsapp');
        document.querySelector('.gf-compare-bar a, a.gf-compare-bar, .gf-brand')?.focus();
    });
    const purchase = document.querySelector('.gf-buy-form');
    if (purchase && 'IntersectionObserver' in window) {
        new IntersectionObserver(entries => {
            document.body.classList.toggle('gf-purchase-visible', entries[0].isIntersecting);
        }).observe(purchase);
    }
    // Both shortcuts remain in the same fixed stack even when the footer enters
    // the viewport; moving comparison into flow can collide with the portrait.
})();
