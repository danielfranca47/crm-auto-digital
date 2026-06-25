/* Comportamento compartilhado: sidebar ativa, toggle mobile, tema, modais. */

(function () {
  const page = document.body.getAttribute('data-page');
  document.querySelectorAll('.sidebar-link[data-page]').forEach((link) => {
    if (link.getAttribute('data-page') === page) link.classList.add('active');
  });

  const toggleBtn = document.querySelector('[data-sidebar-toggle]');
  const sidebar = document.querySelector('.sidebar');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => sidebar.classList.toggle('open'));
  }

  const themeBtn = document.querySelector('[data-theme-toggle]');
  if (themeBtn) {
    const root = document.documentElement;
    const stored = localStorage.getItem('proto-theme');
    if (stored === 'light') root.classList.add('light');
    themeBtn.addEventListener('click', () => {
      root.classList.toggle('light');
      localStorage.setItem('proto-theme', root.classList.contains('light') ? 'light' : 'dark');
      renderIcons();
    });
  }
})();

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('open');
}
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('open');
}
document.addEventListener('click', (e) => {
  if (e.target.classList && e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
});
