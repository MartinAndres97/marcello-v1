(function () {
  'use strict';
  const form = document.getElementById('login');
  const error = document.getElementById('error');
  form.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    error.textContent = '';
    const body = JSON.stringify({
      username: document.getElementById('username').value,
      password: document.getElementById('password').value,
    });
    try {
      const res = await fetch('/api/admin/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body, credentials: 'same-origin',
      });
      if (res.ok) { location.href = '/admin'; return; }
      const data = await res.json().catch(() => ({}));
      error.textContent = typeof data.detail === 'string' ? data.detail : 'No se pudo iniciar sesión.';
    } catch (e) {
      error.textContent = 'Error de conexión.';
    }
  });
})();
