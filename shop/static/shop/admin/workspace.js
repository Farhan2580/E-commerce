(() => {
  'use strict';
  const input = document.querySelector('[data-admin-directory-search]');
  if (!input) return;
  const groups = Array.from(document.querySelectorAll('[data-admin-section]'));
  const empty = document.querySelector('[data-admin-directory-empty]');
  const filter = () => {
    const query = input.value.trim().toLocaleLowerCase();
    let visible = 0;
    groups.forEach(group => {
      const groupMatches = group.querySelector('h2').textContent.toLocaleLowerCase().includes(query);
      const rows = Array.from(group.querySelectorAll('[data-admin-tool]'));
      rows.forEach(row => { row.hidden = !!query && !groupMatches && !row.textContent.toLocaleLowerCase().includes(query); });
      group.hidden = rows.every(row => row.hidden);
      if (!group.hidden) visible += 1;
    });
    empty.hidden = visible > 0;
  };
  input.addEventListener('input', filter);
  input.addEventListener('keydown', event => {
    if (event.key === 'Escape') { input.value = ''; filter(); }
  });
})();
