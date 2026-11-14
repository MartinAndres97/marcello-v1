(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const state = {
    survey: null, step: 'question', index: 0, answers: {}, fromSummary: false, receipt: null,
  };

  function focusTitle() { const t = document.querySelector('[data-focus]'); if (t) t.focus(); }
  function progress(fraction) {
    const bar = h('div'); bar.style.width = Math.round(fraction * 100) + '%';
    return h('div', { class: 'progress', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100,
      'aria-valuenow': Math.round(fraction * 100) }, bar);
  }
  function validQuestion(q) {
    const a = state.answers[q.code] || [];
    if (a.length === 0) return 'Esta pregunta es obligatoria: seleccione una respuesta.';
    return '';
  }

  function viewQuestion() {
    const total = state.survey.questions.length;
    const q = state.survey.questions[state.index];
    const type = q.type === 'multiple' ? 'checkbox' : 'radio';
    const sel = new Set(state.answers[q.code] || []);
    const err = h('p', { class: 'error', role: 'alert' });
    const options = q.options.map((o) => {
      const id = `${q.code}_${o.value}`;
      const input = h('input', { type, id, name: q.code, value: o.value, checked: sel.has(o.value) });
      input.addEventListener('change', () => {
        if (type === 'radio') state.answers[q.code] = [o.value];
        else {
          const cur = new Set(state.answers[q.code] || []);
          if (input.checked) cur.add(o.value); else cur.delete(o.value);
          state.answers[q.code] = [...cur].sort((a, b) => a - b);
        }
        err.textContent = '';
      });
      return h('label', { class: 'option', for: id }, input, h('span', {}, q.type === 'likert' ? `${o.value}. ${o.label}` : o.label));
    });
    const goNext = () => {
      const m = validQuestion(q);
      if (m) { err.textContent = m; return; }
      if (state.fromSummary) { state.fromSummary = false; state.step = 'summary'; }
      else if (state.index < total - 1) state.index += 1;
      else state.step = 'summary';
      render();
    };
    const goPrev = () => {
      if (state.fromSummary) { state.fromSummary = false; state.step = 'summary'; }
      else if (state.index > 0) state.index -= 1;
      else { $('#survey').hidden = true; $('#landing').hidden = false; return; }
      render();
    };
    return h('div', {},
      progress((state.index + 1) / total),
      h('p', { class: 'step-label' }, `Pregunta ${state.index + 1} de ${total}`),
      h('h2', { class: 'q-title', tabindex: -1, 'data-focus': true }, q.text),
      h('fieldset', { class: 'options' + (q.type === 'likert' ? ' likert' : '') }, h('legend', { class: 'sr-only' }, q.text), options),
      err,
      h('div', { class: 'nav' }, h('button', { class: 'btn', type: 'button', onclick: goPrev }, 'Anterior'),
        h('button', { class: 'btn primary', type: 'button', onclick: goNext },
          state.fromSummary ? 'Guardar cambio' : (state.index === total - 1 ? 'Ver resumen' : 'Siguiente'))));
  }

  function labelsFor(q) {
    return (state.answers[q.code] || []).map((v) => q.options.find((o) => o.value === v).label);
  }

  function viewSummary() {
    const err = h('p', { class: 'error', role: 'alert' });
    const send = h('button', { class: 'btn primary', type: 'button' }, 'Enviar respuestas');
    send.addEventListener('click', async () => {
      const m = state.survey.questions.map(validQuestion).find(Boolean);
      if (m) { err.textContent = 'Faltan respuestas por completar.'; return; }
      send.disabled = true; err.textContent = '';
      try {
        const res = await Promise.resolve({ status: 201, json: async () => ({ id: 'DEMO-sin-guardar' }) });
        if (res.status === 201) { state.receipt = (await res.json()).id; state.step = 'done'; state.answers = {}; render(); return; }
        err.textContent = res.status === 429 ? 'Demasiados envíos desde esta conexión. Espere un minuto e intente de nuevo.'
          : res.status === 422 ? 'El servidor rechazó alguna respuesta. Revise el cuestionario.'
          : 'No se pudo guardar la encuesta. Intente de nuevo.';
      } catch (e) { err.textContent = 'Error de conexión. Intente de nuevo.'; }
      send.disabled = false;
    });
    const items = [];
    state.survey.questions.forEach((q, i) => {
      items.push(h('dt', {}, `${q.position}. ${q.text}`, h('button', { class: 'btn edit', type: 'button', onclick: () => { state.fromSummary = true; state.step = 'question'; state.index = i; render(); } }, 'Editar')));
      items.push(h('dd', {}, labelsFor(q).join(' · ')));
    });
    return h('div', { class: 'summary' }, progress(1), h('h2', { class: 'q-title', tabindex: -1, 'data-focus': true }, 'Resumen antes de enviar'),
      h('p', { class: 'step-label' }, 'Revise sus respuestas. Una vez enviadas no podrá modificarlas.'),
      h('dl', {}, items), err,
      h('div', { class: 'nav' }, h('button', { class: 'btn', type: 'button', onclick: () => { state.step = 'question'; state.index = state.survey.questions.length - 1; render(); } }, 'Anterior'), send));
  }

  function viewDone() {
    return h('div', { class: 'done' }, progress(1), h('h2', { class: 'q-title', tabindex: -1, 'data-focus': true }, '¡Gracias! Su encuesta fue enviada'),
      h('p', {}, 'Esto es una demostración: no se guardó ninguna respuesta.'), h('p', { class: 'step-label' }, 'Referencia del envío:'),
      h('p', { class: 'ref' }, state.receipt));
  }

  function render() {
    const root = $('#app');
    root.replaceChildren(state.step === 'question' ? viewQuestion() : state.step === 'summary' ? viewSummary() : viewDone());
    focusTitle();
  }

  $('#start').addEventListener('click', async () => {
    const btn = $('#start'); btn.disabled = true;
    try {
      if (!state.survey) {
        const res = await fetch('survey.json');
        if (!res.ok) throw new Error('survey');
        state.survey = await res.json();
      }
      $('#landing').hidden = true; $('#survey').hidden = false;
      if (state.step !== 'summary' && state.step !== 'done') { state.step = 'question'; }
      render();
    } catch (e) {
      alert('No se pudo cargar la encuesta. Intente de nuevo en unos minutos.');
    } finally { btn.disabled = false; }
  });
})();
