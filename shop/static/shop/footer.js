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
    });
    // Move the floating comparison shortcut into the document while the footer is visible.
    const footer = document.querySelector('.gf-footer-refresh');
    const comparison = document.querySelector('.gf-compare-bar');
    if (footer && comparison && 'IntersectionObserver' in window) {
        // Keep the in-flow control inside the footer, rather than creating a
        // separate light page section underneath it when it stops floating.
        footer.appendChild(comparison);
        new IntersectionObserver(entries => {
            comparison.style.position = entries[0].isIntersecting ? 'static' : '';
            comparison.style.width = entries[0].isIntersecting ? 'fit-content' : '';
            comparison.style.margin = entries[0].isIntersecting ? (mobile.matches ? '16px auto 90px' : '16px auto 0') : '';
        }).observe(footer);
    }
})();
