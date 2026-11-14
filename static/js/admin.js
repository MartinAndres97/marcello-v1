(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const NS = 'http://www.w3.org/2000/svg';
  const state = { page: 1, pageSize: 25, total: 0, includeTest: false, profiles: [] };

  async function api(path) {
    const res = await fetch(path, { credentials: 'same-origin' });
    if (res.status === 401) { location.href = '/admin/login'; throw new Error('401'); }
    if (!res.ok) throw new Error(String(res.status));
    return res.json();
  }
  const fmtDate = (iso) => new Date(iso).toLocaleString('es-CO', { timeZone: 'UTC', hour12: false }) ;

  function bars(el, items, { max, fmt } = {}) {
    el.replaceChildren();
    const top = max || Math.max(1, ...items.map((i) => i.value));
    if (!items.length) { el.append(h('p', { class: 'hint' }, 'Sin datos todavía.')); return; }
    for (const it of items) {
      const fill = h('div', { class: 'fill' });
      fill.style.width = Math.min(100, (it.value / top) * 100) + '%';
      el.append(h('div', { class: 'bar-row' }, h('span', { class: 'lbl', title: it.label }, it.label), h('div', { class: 'track' }, fill),
        h('span', { class: 'val' }, fmt ? fmt(it.value) : it.value)));
    }
  }

  function dateChart(el, data) {
    el.replaceChildren();
    if (!data.length) { el.append(h('p', { class: 'hint' }, 'Sin datos todavía.')); return; }
    const rows = data.slice(-60), W = 700, H = 220, L = 28, B = 46, T = 14;
    const max = Math.max(...rows.map((r) => r.count));
    const slot = (W - L) / rows.length;
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('class', 'chart'); svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Encuestas por fecha');
    const t = (x, y, txt, anchor) => { const n = document.createElementNS(NS, 'text'); n.setAttribute('x', x); n.setAttribute('y', y); if (anchor) n.setAttribute('text-anchor', anchor); n.textContent = txt; svg.append(n); return n; };
    t(L - 4, T + 6, String(max), 'end'); t(L - 4, H - B, '0', 'end');
    rows.forEach((r, i) => {
      const bh = ((H - B - T) * r.count) / max;
      const rect = document.createElementNS(NS, 'rect');
      rect.setAttribute('class', 'bar'); rect.setAttribute('x', L + i * slot + 1); rect.setAttribute('width', Math.max(1, slot - 2));
      rect.setAttribute('y', H - B - bh); rect.setAttribute('height', bh);
      const title = document.createElementNS(NS, 'title'); title.textContent = `${r.date}: ${r.count}`; rect.append(title); svg.append(rect);
    });
    const step = Math.ceil(rows.length / 8);
    rows.forEach((r, i) => { if (i % step === 0) t(L + i * slot + slot / 2, H - B + 14, r.date.slice(5), 'middle'); });
    el.append(svg);
  }

  async function loadDashboard() {
    const d = await api(`/api/admin/dashboard?include_test=${state.includeTest}`);
    const k = d.indicators;
    $('#kpis').replaceChildren(...[['Encuestas recibidas', k.total], ['Encuestas completadas', k.completed], ['Perfiles profesionales', k.profiles],
      ['Ciudades registradas', k.cities], ['Departamentos / regiones', k.regions], ['Países', k.countries]]
      .map(([label, v]) => h('div', { class: 'kpi' }, h('b', {}, v), h('span', {}, label))));
    bars($('#ch-profile'), d.by_profile.map((p) => ({ label: p.label, value: p.count })));
    dateChart($('#ch-date'), d.by_date);
    bars($('#ch-countries'), d.geography.countries.map((g) => ({ label: g.name, value: g.count })));
    bars($('#ch-regions'), d.geography.regions.map((g) => ({ label: g.name, value: g.count })));
    bars($('#ch-cities'), d.geography.cities.map((g) => ({ label: g.name, value: g.count })));
    const lk = $('#ch-likert'); lk.replaceChildren();
    bars(lk, d.likert.map((q) => ({ label: `${q.code} · ${q.text.replace(/^¿Qué tan importante es /, '').replace(/\?$/, '')}`, value: q.mean || 0 })), { max: 5, fmt: (v) => (v ? v.toFixed(2) : '—') });
    const multi = $('#ch-multi'); multi.replaceChildren();
    for (const q of [...d.multiple, ...d.single.filter((s) => s.code !== 'P1')]) {
      const box = h('div'); multi.append(h('div', {}, h('h3', {}, `${q.code} · ${q.text.replace(/ \(puede elegir.*\)$/, '')}`), box));
      bars(box, q.options.map((o) => ({ label: o.label, value: o.pct })), { max: 100, fmt: (v) => v.toFixed(1) + '%' });
    }
  }

  function params() {
    const p = new URLSearchParams({ page: state.page, page_size: state.pageSize, include_test: state.includeTest });
    for (const [id, key] of [['f-q', 'q'], ['f-profile', 'profile'], ['f-country', 'country'], ['f-region', 'region'], ['f-city', 'city'], ['f-from', 'date_from'], ['f-to', 'date_to']]) {
      const v = $('#' + id).value.trim(); if (v) p.set(key, v);
    }
    return p;
  }

  async function loadTable() {
    const d = await api('/api/admin/submissions?' + params());
    state.total = d.total;
    const pages = Math.max(1, Math.ceil(d.total / state.pageSize));
    $('#page-info').textContent = `Página ${state.page} de ${pages} · ${d.total} registros`;
    $('#prev').disabled = state.page <= 1; $('#next').disabled = state.page >= pages;
    const body = $('#table tbody'); body.replaceChildren();
    for (const r of d.items) {
      body.append(h('tr', {}, h('td', { title: r.id }, r.id.slice(0, 8), r.is_test ? h('span', { class: 'badge' }, 'prueba') : null),
        h('td', {}, r.profile || '—'), h('td', {}, fmtDate(r.submitted_at)), h('td', {}, r.country), h('td', {}, r.region), h('td', {}, r.city),
        h('td', {}, h('button', { class: 'btn', type: 'button', onclick: () => showDetail(r.id) }, 'Ver detalle'))));
    }
  }

  async function showDetail(id) {
    const d = await api('/api/admin/submissions/' + id);
    const body = $('#detail-body'); body.replaceChildren(
      h('h3', {}, 'Encuesta ' + d.id), h('p', { class: 'hint' }, `${fmtDate(d.submitted_at)} UTC · ${d.city}, ${d.region}, ${d.country} · estado: ${d.status}${d.is_test ? ' · DATO DE PRUEBA' : ''}`),
      d.answers.map((a) => [h('h4', {}, `${a.code}. ${a.text}`), h('ul', {}, a.selected.map((s) => h('li', {}, a.type === 'likert' ? `${s.value} — ${s.label}` : s.label)))]));
    $('#detail').showModal();
  }

  function updateExportLinks() {
    for (const f of ['xlsx', 'csv', 'json']) $('#x-' + f).href = `/api/admin/export/${f}?include_test=${state.includeTest}`;
  }

  async function init() {
    const survey = await (await fetch('/api/survey')).json();
    const p1 = survey.questions.find((q) => q.code === 'P1');
    for (const o of p1.options) $('#f-profile').append(h('option', { value: o.value }, o.label));
    $('#include-test').addEventListener('change', (e) => { state.includeTest = e.target.checked; state.page = 1; updateExportLinks(); loadDashboard(); loadTable(); });
    $('#filters').addEventListener('submit', (e) => { e.preventDefault(); state.page = 1; loadTable(); });
    $('#filters').addEventListener('reset', () => setTimeout(() => { state.page = 1; loadTable(); }, 0));
    $('#prev').addEventListener('click', () => { state.page -= 1; loadTable(); });
    $('#next').addEventListener('click', () => { state.page += 1; loadTable(); });
    $('#detail-close').addEventListener('click', () => $('#detail').close());
    $('#logout').addEventListener('click', async () => { await fetch('/api/admin/logout', { method: 'POST', credentials: 'same-origin' }); location.href = '/admin/login'; });
    updateExportLinks();
    await Promise.all([loadDashboard(), loadTable()]);
  }
  init().catch((e) => { if (e.message !== '401') document.querySelector('.admin-main').prepend(h('p', { class: 'error' }, 'No se pudo cargar el panel: ' + e.message)); });
})();
