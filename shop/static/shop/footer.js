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
    // Move the floating comparison shortcut into the document while the footer is visible.
    const footer = document.querySelector('.gf-footer-refresh');
    const comparison = document.querySelector('.gf-compare-bar');
    if (footer && comparison && 'IntersectionObserver' in window) {
        new IntersectionObserver(entries => {
            comparison.style.position = entries[0].isIntersecting ? 'static' : '';
            comparison.style.width = entries[0].isIntersecting ? 'fit-content' : '';
            comparison.style.margin = entries[0].isIntersecting ? '16px auto 90px' : '';
        }).observe(footer);
    }
})();
