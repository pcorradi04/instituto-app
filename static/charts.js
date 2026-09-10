/* static/charts.js — todos los tipos de gráfico del sitio.

   Lo usan el post público (post.html) y el editor visual (admin_edit.html),
   así los dos dibujan exactamente lo mismo. Acá vive también la definición
   de cada tipo (CHART_SPECS): qué columnas lleva la tabla de datos, qué
   significan los "nombres de series", qué opciones tiene y un ejemplo. El
   editor arma su panel de carga leyendo eso. app.py solo valida que el tipo
   exista (lista CHART_TYPES): para agregar un tipo nuevo hay que sumarlo en
   los dos lados.

   Formato de datos, común a todos: una fila por línea, columnas separadas
   con "|". La primera columna siempre es texto (etiqueta); las demás son
   números salvo que el tipo diga otra cosa (ej. Sankey: origen | destino |
   valor). Valores vacíos o no numéricos = sin dato.

   API:
     renderPostChart(container, def, accentHex, {animate})
       container = el <div class="chart-wrap"> donde dibujar
       def       = {chart_type, labels, series, rows, series_names, color, options}
       accentHex = {blue:'#0000CC', orange:'#C1622E', ...}
     parseChartTable(texto) -> {labels, series, rows}   (misma regla que app.py)
     CHART_SPECS, CHART_GROUPS                           (para el editor)
*/
(function () {
  'use strict';

  const GRID = '#EAE5D8', INK = '#1A1A1A', SOFT = '#5B564C', LINE = '#DFDACD';
  // Colores secundarios, en orden, después del color principal del gráfico.
  const EXTRA = ['#3B0A0A', '#1F4E5F', '#0000CC', '#A63D2F', '#7C6A9C', '#8C7A4A', '#B9B4A6', '#E8C24A'];
  const nf = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 1 });
  const fmt = v => (v === null || v === undefined || isNaN(v)) ? '' : nf.format(v);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = v => { if (v === null || v === undefined || v === '') return null; const f = Number(v); return isNaN(f) ? null : f; };
  const hexRgb = hex => { const h = String(hex).replace('#', ''); return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; };
  const rgba = (hex, a) => { const [r, g, b] = hexRgb(hex); return `rgba(${r},${g},${b},${a})`; };
  const yes = v => /^(s[ií]|yes|1|true|x)$/i.test(String(v || '').trim());

  // ---- parseo de la tabla de texto (misma regla que parse_table en app.py) --
  window.parseChartTable = function (text) {
    const rows = String(text || '').split(/\r?\n/).map(l => l.trim()).filter(Boolean).map(l => l.split('|').map(p => p.trim()));
    if (!rows.length) return { labels: [], series: [], rows: [] };
    const labels = rows.map(r => r[0]);
    const nSeries = Math.max(...rows.map(r => r.length)) - 1;
    const series = [];
    for (let i = 0; i < nSeries; i++) series.push(rows.map(r => num(r[i + 1])));
    return { labels, series, rows };
  };

  // ---- definición de cada tipo ---------------------------------------------
  const GROUPS = ['Comparación', 'Evolución en el tiempo', 'Composición', 'Distribución e indicadores'];
  const OPT_Y = { key: 'y_title', label: 'Título eje Y', placeholder: 'USD millones' };
  const OPT_UNIT = { key: 'unit', label: 'Unidad', placeholder: 'USD M' };
  const NAMES_LEGEND = 'Nombres de las series (leyenda)';

  const SPECS = {
    bar_comparison: { label: 'Barras agrupadas', group: 'Comparación', kind: 'canvas',
      columns: 'Etiqueta | serie 1 | serie 2 | ...', names: NAMES_LEGEND, names_placeholder: 'Energía, INDEC',
      hint: 'Una barra por serie en cada etiqueta. Ideal para comparar dos fuentes mes a mes.',
      placeholder: 'Mayo 2026 | 959.1 | 1172\nJunio 2026 | 401.3 | 918', options: [OPT_Y] },
    bar_horizontal: { label: 'Barras horizontales (ranking)', group: 'Comparación', kind: 'canvas',
      columns: 'Etiqueta | valor', names: 'Título del eje de valores', names_placeholder: 'USD millones',
      hint: 'Barras horizontales, cómodas para rankings con nombres largos.',
      placeholder: 'YPF | 574.1\nVista Oil & Gas | 569\nChevron Argentina | 407.3',
      options: [{ key: 'sort', label: 'Ordenar de mayor a menor (si/no)', placeholder: 'si' }] },
    diverging_bar: { label: 'Barras divergentes (+ / −)', group: 'Comparación', kind: 'canvas',
      columns: 'Etiqueta | valor (positivo o negativo)', names: 'Título del eje de valores', names_placeholder: '% de brecha',
      hint: 'Barras horizontales desde el cero: las negativas en granate, las positivas en el color principal.',
      placeholder: 'Crudo Exp. May-26 | -18.2\nCrudo Exp. Jun-26 | -56.3\nGas Imp. Jun-26 | -5.8', options: [] },
    dumbbell: { label: 'Mancuernas (dos valores por fila)', group: 'Comparación', kind: 'html',
      columns: 'Etiqueta | valor A | valor B', names: 'Nombres de A y B (leyenda)', names_placeholder: 'Energía, INDEC',
      hint: 'Dos puntos unidos por una línea en cada fila: muestra la distancia entre dos valores.',
      placeholder: 'Crudo Exp. May-26 | 959.1 | 1172\nCrudo Exp. Jun-26 | 401.3 | 918\nGas Exp. May-26 | 30.4 | 52', options: [] },
    scatter: { label: 'Dispersión (puntos x, y)', group: 'Comparación', kind: 'canvas',
      columns: 'Serie | x | y', names: 'Títulos de los ejes: X, Y', names_placeholder: 'Energía (USD M), INDEC (USD M)',
      hint: 'Un punto por fila; las filas con el mismo nombre de serie comparten color.',
      placeholder: 'Crudo Export. | 959.1 | 1172\nCrudo Export. | 401.3 | 918\nGas Export. | 30.4 | 52',
      options: [{ key: 'diagonal', label: 'Línea y = x (si/no)', placeholder: 'si' }] },

    line: { label: 'Líneas', group: 'Evolución en el tiempo', kind: 'canvas',
      columns: 'Período | serie 1 | serie 2 | ...', names: NAMES_LEGEND, names_placeholder: 'Petróleo crudo, Gas natural',
      hint: 'Una línea por serie a lo largo del tiempo.',
      placeholder: '2026-01 | 463.1 | 22.96\n2026-02 | 386.6 | 24.61\n2026-03 | 720.7 | 34.19', options: [OPT_Y] },
    bar_line: { label: 'Barras + línea (eje derecho)', group: 'Evolución en el tiempo', kind: 'canvas',
      columns: 'Período | barra 1 | barra 2 | ... | línea (última columna)', names: NAMES_LEGEND, names_placeholder: 'Volumen, Precio',
      hint: 'La última columna se dibuja como línea con su propio eje a la derecha; las anteriores, como barras. Ej.: volumen y precio.',
      placeholder: 'Ene | 463.1 | 62.5\nFeb | 386.6 | 64.1\nMar | 720.7 | 68.9',
      options: [OPT_Y, { key: 'y2_title', label: 'Título eje derecho', placeholder: 'USD/bbl' }] },
    stacked_area: { label: 'Áreas apiladas', group: 'Evolución en el tiempo', kind: 'canvas',
      columns: 'Período | serie 1 | serie 2 | ...', names: NAMES_LEGEND, names_placeholder: 'Petróleo crudo, Gas natural',
      hint: 'Series apiladas: se ve el total y cómo cambia el peso de cada una.',
      placeholder: '2024 | 5200 | 380\n2025 | 6100 | 410\n2026 | 3670 | 151', options: [OPT_Y] },
    bump: { label: 'Ranking en el tiempo (bump)', group: 'Evolución en el tiempo', kind: 'canvas',
      columns: 'Período | posición A | posición B | ...', names: 'Nombres de lo que se rankea (leyenda)', names_placeholder: 'Pan American, YPF, Vista',
      hint: 'Cada columna es una empresa o país; cada valor, su posición (1 = primero). El eje va de 1 arriba hacia abajo.',
      placeholder: '2020 | 1 | 2 | 3\n2021 | 1 | 6 | 2\n2022 | 1 | 6 | 2\n2023 | 2 | 4 | 1', options: [] },
    heatmap: { label: 'Mapa de calor (matriz)', group: 'Evolución en el tiempo', kind: 'html',
      columns: 'Fila | columna 1 | columna 2 | ...', names: 'Etiquetas de las columnas', names_placeholder: '2020, 2021, 2022',
      hint: 'Matriz coloreada: filas (ej. meses) por columnas (ej. años). Más oscuro = valor más alto.',
      placeholder: 'Ene | 73.5 | 84.6 | 83.3\nFeb | 91.9 | 64 | 57.7\nMar | 114.5 | 88.8 | 130\nAbr | 66.7 | 101 | 112.2',
      options: [{ key: 'unit', label: 'Unidad (leyenda)', placeholder: 'USD millones/mes' }] },
    waterfall: { label: 'Cascada (descomposición)', group: 'Evolución en el tiempo', kind: 'canvas',
      columns: 'Etiqueta | valor', names: null,
      hint: 'La primera fila es el punto de partida; cada fila siguiente es una variación (positiva o negativa). La barra final con el total se agrega sola.',
      placeholder: 'Feb-26 (base) | 386.6\nEfecto precio | 111.1\nEfecto volumen | 223',
      options: [{ key: 'total_label', label: 'Etiqueta de la barra final', placeholder: 'Mar-26 (total)' }, OPT_Y] },
    fan_chart: { label: 'Pronóstico con bandas (fan)', group: 'Evolución en el tiempo', kind: 'canvas',
      columns: 'Período | real | pronóstico | banda 1 bajo | banda 1 alto | banda 2 bajo | banda 2 alto | banda 3 bajo | banda 3 alto',
      names: 'Leyenda: real, pronóstico, banda 1, banda 2, banda 3', names_placeholder: 'Real, Pronóstico, IC 50%, IC 80%, IC 95%',
      hint: 'Filas históricas: solo "real". Filas futuras: pronóstico y hasta tres bandas anidadas, de la más angosta a la más ancha. El pronóstico se une solo al último dato real.',
      placeholder: '2026-05 | 959.1\n2026-06 | 401.3\n2026-07 | | 536.2 | 481.3 | 591.1 | 422.5 | 649.8 | 330.4 | 741.9\n2026-08 | | 470 | 404.9 | 535.1 | 335.3 | 604.7 | 226.1 | 713.9',
      options: [OPT_Y] },

    stacked_bar: { label: 'Barras apiladas', group: 'Composición', kind: 'canvas',
      columns: 'Etiqueta | parte 1 | parte 2 | ...', names: NAMES_LEGEND, names_placeholder: 'Chile, Uruguay, Brasil',
      hint: 'Cada barra suma sus partes: se ve el total y la composición.',
      placeholder: '2024 | 310 | 39 | 0\n2025 | 340.8 | 5.1 | 2.5', options: [OPT_Y] },
    stacked_bar_100: { label: 'Barras 100 % apiladas', group: 'Composición', kind: 'canvas',
      columns: 'Etiqueta | parte 1 | parte 2 | ...', names: NAMES_LEGEND, names_placeholder: 'Chile, Uruguay, Brasil',
      hint: 'Cada barra suma 100 %: los valores se convierten a porcentaje solos, podés cargar montos.',
      placeholder: '2024 | 88.8 | 11.2 | 0\n2025 | 97.8 | 1.5 | 0.7\n2026 | 94.1 | 5.8 | 0.1', options: [] },
    treemap: { label: 'Treemap (bloques proporcionales)', group: 'Composición', kind: 'html',
      columns: 'Nombre | valor', names: null,
      hint: 'Bloques de tamaño proporcional al valor (ej. participación por empresa).',
      placeholder: 'YPF | 574.1\nVista Oil & Gas | 569\nChevron Argentina | 407.3\nOtras (10+ empresas) | 515.9', options: [OPT_UNIT] },
    sankey: { label: 'Sankey (flujos origen → destino)', group: 'Composición', kind: 'html',
      columns: 'Origen | Destino | valor', names: null,
      hint: 'Cintas de origen a destino con grosor proporcional al valor. Puede haber varios orígenes y varios destinos.',
      placeholder: 'Gas exportado 2025 | Chile | 340.8\nGas exportado 2025 | Uruguay | 5.1\nGas exportado 2025 | Brasil | 2.5', options: [OPT_UNIT] },
    shaded_list: { label: 'Mapa esquemático por zona (lista sombreada)', group: 'Composición', kind: 'html',
      columns: 'Zona | valor', names: null,
      hint: 'Lista de zonas sombreadas según el valor, en el orden que las cargues (ej. cuencas de norte a sur). Esquemático, no es un mapa real.',
      placeholder: 'Noroeste | 0.2\nCuyana | 0\nNeuquina | 72.4\nGolfo San Jorge | 20.8\nAustral | 6.6',
      options: [{ key: 'unit', label: 'Unidad', placeholder: '%' }] },

    boxplot: { label: 'Caja y bigotes (box plot)', group: 'Distribución e indicadores', kind: 'html',
      columns: 'Etiqueta | mínimo | cuartil 1 | mediana | cuartil 3 | máximo', names: null,
      hint: 'Caja entre los cuartiles, línea en la mediana, bigotes hasta el mínimo y el máximo.',
      placeholder: '2020 | 78.8 | 107.2 | 127.3 | 173.1 | 333.5\n2021 | 86.7 | 132.6 | 162.2 | 181.2 | 1616.5\n2022 | 136.3 | 169.8 | 268.9 | 356.1 | 1240.2',
      options: [{ key: 'y_title', label: 'Unidad del eje', placeholder: 'USD/mil m³' }] },
    bullet: { label: 'Bullet (indicador vs. referencia)', group: 'Distribución e indicadores', kind: 'html',
      columns: 'Nombre | valor | referencia | rango bajo | rango alto | máximo de la escala', names: 'Leyenda: valor, referencia, rango', names_placeholder: 'Pronóstico, Promedio histórico, Rango IC80',
      hint: 'Barra oscura = valor; marca vertical = referencia (ej. promedio histórico); fondo claro = rango esperado.',
      placeholder: 'Crudo Export (Jul-26) | 536.2 | 271 | 422.5 | 649.8 | 750\nGas Export (Jul-26) | 39.8 | 21.6 | 24.6 | 55.1 | 70', options: [OPT_UNIT] },
    gauge: { label: 'Velocímetro (síntesis cualitativa)', group: 'Distribución e indicadores', kind: 'html',
      columns: 'Texto de la lectura | valor de 0 a 100', names: null,
      hint: 'Velocímetro de tres zonas (verde, amarillo, granate) con una aguja. Es una pieza editorial: el texto es la lectura, el valor la posición.',
      placeholder: 'Estrés: medio-alto | 58',
      options: [{ key: 'left_label', label: 'Etiqueta izquierda', placeholder: 'Bajo' }, { key: 'right_label', label: 'Etiqueta derecha', placeholder: 'Alto' }] },
  };
  window.CHART_SPECS = SPECS;
  window.CHART_GROUPS = GROUPS;

  // ---- helpers de dibujo ----------------------------------------------------
  function canvasIn(container) {
    container.classList.remove('auto');
    let c = container.querySelector('canvas');
    if (!c) { container.innerHTML = ''; c = document.createElement('canvas'); container.appendChild(c); }
    const prev = Chart.getChart(c);
    if (prev) prev.destroy();
    return c;
  }
  function htmlIn(container, html) {
    const c = container.querySelector('canvas');
    if (c && window.Chart) { const p = Chart.getChart(c); if (p) p.destroy(); }
    container.classList.add('auto');
    container.innerHTML = html;
    return null;
  }
  const legendRow = items => '<div class="legend-row">' + items.map(([c, t]) => `<span><span class="dot" style="background:${c}"></span>${esc(t)}</span>`).join('') + '</div>';
  const seriesName = (def, i, fallback) => (def.series_names && def.series_names[i]) || fallback || ('Serie ' + (i + 1));
  const widthOf = c => Math.max(c.clientWidth || 600, 320);

  function baseOptions(animate) {
    return { responsive: true, maintainAspectRatio: false, animation: animate ? undefined : false,
      plugins: { legend: { position: 'top', labels: { boxWidth: 10 } } }, scales: {} };
  }
  const axis = (title, extra) => Object.assign({ grid: { color: GRID } }, title ? { title: { display: true, text: title } } : {}, extra || {});
  const noGrid = extra => Object.assign({ grid: { display: false } }, extra || {});

  const R = {};

  // ---- Chart.js -------------------------------------------------------------
  R.bar_comparison = (c, def, P, o) => {
    const opt = baseOptions(o.animate);
    opt.scales = { y: axis(def.options.y_title), x: noGrid() };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, i) => ({ label: seriesName(def, i), data: s, backgroundColor: P[i % P.length] })) } });
  };
  R.bar_horizontal = (c, def, P, o) => {
    let pairs = def.labels.map((l, i) => [l, def.series[0] ? def.series[0][i] : null]);
    if (yes(def.options.sort)) pairs = pairs.slice().sort((a, b) => (b[1] || 0) - (a[1] || 0));
    const opt = baseOptions(o.animate); opt.indexAxis = 'y'; opt.plugins.legend.display = false;
    opt.scales = { x: axis(def.series_names[0]), y: noGrid() };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: pairs.map(p => p[0]),
      datasets: [{ data: pairs.map(p => p[1]), backgroundColor: P[0] }] } });
  };
  R.diverging_bar = (c, def, P, o) => {
    const vals = def.series[0] || [];
    const opt = baseOptions(o.animate); opt.indexAxis = 'y'; opt.plugins.legend.display = false;
    opt.scales = { x: axis(def.series_names[0]), y: noGrid() };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: def.labels,
      datasets: [{ data: vals, backgroundColor: vals.map(v => (v || 0) < 0 ? '#A63D2F' : P[0]) }] } });
  };
  R.scatter = (c, def, P, o) => {
    const groups = new Map();
    def.rows.forEach(r => { const x = num(r[1]), y = num(r[2]); if (x == null || y == null) return;
      const k = r[0] || 'Serie'; if (!groups.has(k)) groups.set(k, []); groups.get(k).push({ x, y }); });
    const ds = [...groups.entries()].map(([k, pts], i) => ({ label: k, data: pts, backgroundColor: P[i % P.length], pointRadius: 6 }));
    if (yes(def.options.diagonal)) {
      const m = Math.max(0, ...[...groups.values()].flat().flatMap(p => [p.x, p.y])) * 1.05;
      ds.push({ label: 'y = x', data: [{ x: 0, y: 0 }, { x: m, y: m }], type: 'line', borderColor: '#999', borderDash: [4, 4], borderWidth: 1.3, pointRadius: 0, fill: false });
    }
    const opt = baseOptions(o.animate);
    opt.scales = { x: axis(def.series_names[0]), y: axis(def.series_names[1]) };
    return new Chart(canvasIn(c), { type: 'scatter', options: opt, data: { datasets: ds } });
  };
  R.line = (c, def, P, o) => {
    const opt = baseOptions(o.animate);
    opt.scales = { y: axis(def.options.y_title), x: noGrid() };
    return new Chart(canvasIn(c), { type: 'line', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, i) => ({ label: seriesName(def, i), data: s, borderColor: P[i % P.length], backgroundColor: 'transparent', borderWidth: 2.2, pointRadius: 2, tension: 0.2 })) } });
  };
  R.bar_line = (c, def, P, o) => {
    const n = def.series.length;
    const ds = def.series.map((s, i) => (n > 1 && i === n - 1)
      ? { type: 'line', label: seriesName(def, i), data: s, borderColor: EXTRA[0], backgroundColor: EXTRA[0], borderWidth: 2.2, pointRadius: 3, tension: 0.2, yAxisID: 'y2', order: 1 }
      : { type: 'bar', label: seriesName(def, i), data: s, backgroundColor: P[i % P.length], yAxisID: 'y', order: 2 });
    const opt = baseOptions(o.animate);
    opt.scales = { x: noGrid(), y: axis(def.options.y_title, { position: 'left' }) };
    if (n > 1) opt.scales.y2 = axis(def.options.y2_title, { position: 'right', grid: { drawOnChartArea: false } });
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: def.labels, datasets: ds } });
  };
  R.stacked_area = (c, def, P, o) => {
    const opt = baseOptions(o.animate);
    opt.scales = { y: axis(def.options.y_title, { stacked: true }), x: noGrid({ ticks: { maxTicksLimit: 12 } }) };
    return new Chart(canvasIn(c), { type: 'line', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, i) => ({ label: seriesName(def, i), data: s, borderColor: P[i % P.length], backgroundColor: rgba(P[i % P.length], 0.55), fill: true, borderWidth: 1, pointRadius: 0 })) } });
  };
  R.bump = (c, def, P, o) => {
    const maxRank = Math.max(def.series.length, ...def.series.flat().filter(v => v != null), 1);
    const opt = baseOptions(o.animate);
    opt.scales = { x: noGrid(), y: axis(null, { reverse: true, min: 1, max: maxRank, ticks: { stepSize: 1, callback: v => '#' + v } }) };
    return new Chart(canvasIn(c), { type: 'line', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, i) => ({ label: seriesName(def, i), data: s, borderColor: P[i % P.length], backgroundColor: P[i % P.length], borderWidth: 2.2, pointRadius: 4, tension: 0.15 })) } });
  };
  R.waterfall = (c, def, P, o) => {
    const vals = def.series[0] || [];
    if (!vals.length) return htmlIn(c, '');
    let level = vals[0] || 0;
    const bars = [[0, level]], colors = [EXTRA[1]], shown = [level];
    for (let i = 1; i < vals.length; i++) {
      const d = vals[i] || 0;
      bars.push([level, level + d]); colors.push(d >= 0 ? P[0] : '#A63D2F'); shown.push(d);
      level += d;
    }
    bars.push([0, level]); colors.push(EXTRA[2]); shown.push(level);
    const labels = def.labels.concat([def.options.total_label || 'Total']);
    const opt = baseOptions(o.animate); opt.plugins.legend.display = false;
    opt.plugins.tooltip = { callbacks: { label: ctx => fmt(shown[ctx.dataIndex]) } };
    opt.scales = { y: axis(def.options.y_title), x: noGrid() };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels, datasets: [{ data: bars, backgroundColor: colors }] } });
  };
  R.stacked_bar = (c, def, P, o) => {
    const opt = baseOptions(o.animate);
    opt.scales = { x: noGrid({ stacked: true }), y: axis(def.options.y_title, { stacked: true }) };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, i) => ({ label: seriesName(def, i), data: s, backgroundColor: P[i % P.length] })) } });
  };
  R.stacked_bar_100 = (c, def, P, o) => {
    const totals = def.labels.map((_, i) => def.series.reduce((s, ser) => s + (ser[i] || 0), 0));
    const opt = baseOptions(o.animate);
    opt.scales = { x: noGrid({ stacked: true }), y: axis('%', { stacked: true, max: 100 }) };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, k) => ({ label: seriesName(def, k), data: s.map((v, i) => totals[i] ? (v || 0) / totals[i] * 100 : null), backgroundColor: P[k % P.length] })) } });
  };
  R.fan_chart = (c, def, P, o) => {
    const real = (def.series[0] || []).slice(), pred = (def.series[1] || []).slice();
    const bands = [];
    for (let k = 0; k < 3; k++) {
      const lo = def.series[2 + 2 * k], hi = def.series[3 + 2 * k];
      if (lo && hi) bands.push({ lo: lo.slice(), hi: hi.slice(), name: seriesName(def, 2 + k, 'Banda ' + (k + 1)) });
    }
    // Unir el pronóstico y las bandas al último dato real.
    let anchor = -1;
    real.forEach((v, i) => { if (v != null) anchor = i; });
    if (anchor >= 0) {
      const a = real[anchor];
      if (pred[anchor] == null) pred[anchor] = a;
      bands.forEach(b => { if (b.lo[anchor] == null) b.lo[anchor] = a; if (b.hi[anchor] == null) b.hi[anchor] = a; });
    }
    const alphas = [0.32, 0.20, 0.12];
    const ds = [];
    for (let k = bands.length - 1; k >= 0; k--) {   // la banda más ancha abajo, la angosta arriba
      ds.push({ label: '_hi' + k, data: bands[k].hi, borderWidth: 0, pointRadius: 0, fill: false });
      ds.push({ label: bands[k].name, data: bands[k].lo, borderWidth: 0, pointRadius: 0, fill: '-1', backgroundColor: rgba(P[0], alphas[k]) });
    }
    ds.push({ label: seriesName(def, 1, 'Pronóstico'), data: pred, borderColor: P[0], borderDash: [5, 4], borderWidth: 2, pointRadius: 0 });
    ds.push({ label: seriesName(def, 0, 'Real'), data: real, borderColor: P[0], borderWidth: 2.2, pointRadius: 0 });
    const opt = baseOptions(o.animate);
    opt.plugins.legend.labels.filter = item => !String(item.text).startsWith('_');
    opt.scales = { x: noGrid({ ticks: { maxTicksLimit: 10 } }), y: axis(def.options.y_title) };
    return new Chart(canvasIn(c), { type: 'line', options: opt, data: { labels: def.labels, datasets: ds } });
  };

  // ---- HTML / SVG a mano ----------------------------------------------------
  R.dumbbell = (c, def, P) => {
    const a = def.series[0] || [], b = def.series[1] || [];
    const n = def.labels.length;
    if (!n) return htmlIn(c, '');
    const W = widthOf(c), rowH = 34, H = rowH * n + 12;
    const maxV = (Math.max(0, ...a.concat(b).filter(v => v != null)) * 1.12) || 1;
    const padL = Math.min(220, Math.max(90, W * 0.3)), padR = 24;
    const xs = v => padL + (v / maxV) * (W - padL - padR);
    const nA = seriesName(def, 0, 'A'), nB = seriesName(def, 1, 'B');
    let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="Georgia,serif">`;
    def.labels.forEach((lab, i) => {
      const y = i * rowH + rowH / 2 + 6, va = a[i], vb = b[i];
      svg += `<text x="${padL - 10}" y="${y + 4}" text-anchor="end" font-size="11" fill="${SOFT}">${esc(lab)}</text>`;
      if (va != null && vb != null) svg += `<line x1="${xs(va)}" y1="${y}" x2="${xs(vb)}" y2="${y}" stroke="#CFC9B8" stroke-width="3"/>`;
      if (va != null) svg += `<circle cx="${xs(va)}" cy="${y}" r="6" fill="${P[0]}"><title>${esc(nA)}: ${fmt(va)}</title></circle>`;
      if (vb != null) svg += `<circle cx="${xs(vb)}" cy="${y}" r="6" fill="${P[1]}"><title>${esc(nB)}: ${fmt(vb)}</title></circle>`;
    });
    return htmlIn(c, legendRow([[P[0], nA], [P[1], nB]]) + svg + '</svg>');
  };
  R.heatmap = (c, def, P) => {
    if (!def.series.length) return htmlIn(c, '');
    const maxV = Math.max(0, ...def.series.flat().filter(v => v != null)) || 1;
    const [r0, g0, b0] = hexRgb(P[0]);
    const colorFor = v => { const t = Math.min((v || 0) / maxV, 1);
      return `rgb(${Math.round(255 - t * (255 - r0))},${Math.round(245 - t * (245 - g0))},${Math.round(235 - t * (235 - b0))})`; };
    let html = `<div style="overflow-x:auto"><table style="border-collapse:collapse; font-size:10.5px; width:100%;"><tr><td></td>` +
      def.series.map((_, k) => `<td style="text-align:center; padding:3px; font-weight:700; color:${SOFT}">${esc(seriesName(def, k, 'Col ' + (k + 1)))}</td>`).join('') + '</tr>';
    def.labels.forEach((lab, i) => {
      html += `<tr><td style="padding:3px 8px 3px 0; color:${SOFT}; text-align:right; white-space:nowrap">${esc(lab)}</td>`;
      def.series.forEach((s, k) => { const v = s[i];
        html += `<td title="${esc(lab)} ${esc(seriesName(def, k, ''))}: ${fmt(v)}" style="background:${v == null ? '#fff' : colorFor(v)}; min-width:34px; height:22px; text-align:center; color:${(v || 0) > maxV * 0.55 ? '#fff' : '#333'}; font-size:9px;">${v != null ? fmt(Math.round(v)) : ''}</td>`; });
      html += '</tr>';
    });
    html += '</table></div>';
    if (def.options.unit) html += `<div class="legend-row" style="margin-top:8px"><span>${esc(def.options.unit)} — escala 0 a ${fmt(maxV)}</span></div>`;
    return htmlIn(c, html);
  };
  R.treemap = (c, def, P) => {
    const items = def.rows.map(r => ({ name: r[0], v: num(r[1]) })).filter(d => d.v > 0);
    const total = items.reduce((s, d) => s + d.v, 0);
    if (!total) return htmlIn(c, '');
    const unit = def.options.unit || '';
    let html = '<div style="display:flex; flex-wrap:wrap; gap:3px; min-height:240px;">';
    items.forEach((d, i) => { const pct = d.v / total * 100;
      html += `<div title="${esc(d.name)}: ${fmt(d.v)} ${esc(unit)} (${pct.toFixed(1)}%)" style="flex:${pct} 1 ${pct}%; min-width:72px; min-height:64px; background:${P[i % P.length]}; color:#fff; display:flex; align-items:flex-end; padding:6px; font-size:10.5px; line-height:1.25;">${esc(d.name)}<br><b>${fmt(d.v)} ${esc(unit)}</b></div>`; });
    return htmlIn(c, html + '</div>');
  };
  R.sankey = (c, def, P) => {
    const flows = def.rows.map(r => ({ s: r[0], t: r[1], v: num(r[2]) })).filter(f => f.s && f.t && f.v > 0);
    if (!flows.length) return htmlIn(c, '');
    const unit = def.options.unit || '';
    const srcs = [], tgts = [];
    const node = (arr, name) => { let n = arr.find(x => x.name === name); if (!n) { n = { name, total: 0, off: 0 }; arr.push(n); } return n; };
    flows.forEach(f => { node(srcs, f.s).total += f.v; node(tgts, f.t).total += f.v; });
    const total = flows.reduce((s, f) => s + f.v, 0);
    const W = widthOf(c), nMax = Math.max(srcs.length, tgts.length);
    const gap = 12, padT = 16, padB = 12;
    const H = Math.max(220, Math.min(460, 46 * nMax + 100));
    const k = (H - padT - padB - gap * (nMax - 1)) / total;
    const labW = Math.min(200, Math.max(100, W * 0.28)), bw = 14, x0 = labW, x1 = W - labW;
    let y = padT; srcs.forEach(n => { n.y = y; n.h = Math.max(n.total * k, 2); y += n.h + gap; });
    y = padT; tgts.forEach(n => { n.y = y; n.h = Math.max(n.total * k, 2); y += n.h + gap; });
    let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="Georgia,serif">`;
    flows.forEach(f => {
      const s = srcs.find(n => n.name === f.s), t = tgts.find(n => n.name === f.t);
      const h = f.v * k, sy = s.y + s.off, ty = t.y + t.off; s.off += h; t.off += h;
      const xa = x0 + bw, xb = x1, xm = (xa + xb) / 2;
      svg += `<path d="M${xa},${sy} C${xm},${sy} ${xm},${ty} ${xb},${ty} L${xb},${ty + h} C${xm},${ty + h} ${xm},${sy + h} ${xa},${sy + h} Z" fill="${P[tgts.indexOf(t) % P.length]}" opacity="0.7"><title>${esc(f.s)} → ${esc(f.t)}: ${fmt(f.v)} ${esc(unit)}</title></path>`;
    });
    srcs.forEach(n => { svg += `<rect x="${x0}" y="${n.y}" width="${bw}" height="${n.h}" fill="#333"/><text x="${x0 - 8}" y="${n.y + n.h / 2 + 4}" text-anchor="end" font-size="11.5" fill="${INK}">${esc(n.name)} — ${fmt(n.total)} ${esc(unit)}</text>`; });
    let last = -Infinity;
    tgts.forEach((n, i) => {   // etiquetas separadas al menos 15px para que no se pisen
      const cy = Math.max(n.y + n.h / 2, last + 15); last = cy;
      svg += `<rect x="${x1}" y="${n.y}" width="${bw}" height="${n.h}" fill="${P[i % P.length]}"/>`;
      if (Math.abs(cy - (n.y + n.h / 2)) > 1) svg += `<line x1="${x1 + bw}" y1="${n.y + n.h / 2}" x2="${x1 + bw + 6}" y2="${cy}" stroke="#999" stroke-width="1"/>`;
      svg += `<text x="${x1 + bw + 10}" y="${cy + 4}" font-size="11.5" fill="${INK}">${esc(n.name)} — ${fmt(n.total)} ${esc(unit)}</text>`;
    });
    return htmlIn(c, svg + '</svg>');
  };
  R.shaded_list = (c, def, P) => {
    const items = def.rows.map(r => ({ name: r[0], v: num(r[1]) })).filter(d => d.name);
    if (!items.length) return htmlIn(c, '');
    const maxV = Math.max(0, ...items.map(d => d.v || 0)) || 1;
    const unit = def.options.unit !== undefined && def.options.unit !== '' ? def.options.unit : '%';
    let html = '<div style="display:flex; flex-direction:column; gap:4px; max-width:360px; margin:0 auto;">';
    items.forEach(d => { const t = (d.v || 0) / maxV;
      html += `<div style="background:${rgba(P[0], 0.12 + t * 0.78)}; border:1px solid ${LINE}; padding:14px 16px; display:flex; justify-content:space-between; align-items:center; color:${t > 0.55 ? '#fff' : INK}"><span style="font-size:12.5px">${esc(d.name)}</span><b style="font-size:13px">${d.v != null ? fmt(d.v) + (unit === '%' ? '%' : ' ' + esc(unit)) : ''}</b></div>`; });
    return htmlIn(c, html + '</div>');
  };
  R.boxplot = (c, def, P) => {
    const items = def.rows.map(r => ({ l: r[0], min: num(r[1]), q1: num(r[2]), med: num(r[3]), q3: num(r[4]), max: num(r[5]) }))
      .filter(d => [d.min, d.q1, d.med, d.q3, d.max].every(v => v != null));
    if (!items.length) return htmlIn(c, '');
    const maxV = Math.max(...items.map(d => d.max)) * 1.05 || 1, minV = Math.min(0, ...items.map(d => d.min));
    const W = widthOf(c), H = 280, padB = 26, padT = 12, padL = 56, padR = 10;
    const colW = (W - padL - padR) / items.length;
    const ys = v => H - padB - ((v - minV) / (maxV - minV)) * (H - padB - padT);
    let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="Georgia,serif">`;
    for (let g = 0; g <= 4; g++) { const v = minV + (maxV - minV) * g / 4;
      svg += `<line x1="${padL}" y1="${ys(v)}" x2="${W - padR}" y2="${ys(v)}" stroke="${GRID}"/><text x="${padL - 6}" y="${ys(v) + 3.5}" text-anchor="end" font-size="9.5" fill="${SOFT}">${fmt(Math.round(v))}</text>`; }
    items.forEach((d, i) => {
      const cx = padL + i * colW + colW / 2, bw = Math.min(colW * 0.5, 60);
      svg += `<line x1="${cx}" y1="${ys(d.min)}" x2="${cx}" y2="${ys(d.max)}" stroke="${SOFT}" stroke-width="1.2"/>`;
      svg += `<line x1="${cx - bw / 4}" y1="${ys(d.min)}" x2="${cx + bw / 4}" y2="${ys(d.min)}" stroke="${SOFT}" stroke-width="1.2"/><line x1="${cx - bw / 4}" y1="${ys(d.max)}" x2="${cx + bw / 4}" y2="${ys(d.max)}" stroke="${SOFT}" stroke-width="1.2"/>`;
      svg += `<rect x="${cx - bw / 2}" y="${ys(d.q3)}" width="${bw}" height="${Math.max(ys(d.q1) - ys(d.q3), 1)}" fill="${rgba(EXTRA[1], 0.35)}" stroke="${EXTRA[1]}" stroke-width="1.2"><title>${esc(d.l)}: mín ${fmt(d.min)} · Q1 ${fmt(d.q1)} · mediana ${fmt(d.med)} · Q3 ${fmt(d.q3)} · máx ${fmt(d.max)}</title></rect>`;
      svg += `<line x1="${cx - bw / 2}" y1="${ys(d.med)}" x2="${cx + bw / 2}" y2="${ys(d.med)}" stroke="${P[0]}" stroke-width="2.2"/>`;
      svg += `<text x="${cx}" y="${H - 8}" text-anchor="middle" font-size="10.5" fill="${SOFT}">${esc(d.l)}</text>`;
    });
    const head = def.options.y_title ? `<div class="legend-row"><span>${esc(def.options.y_title)}</span></div>` : '';
    return htmlIn(c, head + svg + '</svg>');
  };
  R.bullet = (c, def, P) => {
    const items = def.rows.map(r => ({ name: r[0], v: num(r[1]), ref: num(r[2]), lo: num(r[3]), hi: num(r[4]), max: num(r[5]) })).filter(d => d.name && d.v != null);
    if (!items.length) return htmlIn(c, '');
    const unit = def.options.unit ? ' ' + esc(def.options.unit) : '';
    const nV = seriesName(def, 0, 'Valor'), nR = seriesName(def, 1, 'Referencia'), nRg = seriesName(def, 2, 'Rango');
    let html = legendRow([[P[0], nV], [EXTRA[0], nR], [rgba(P[0], 0.25), nRg]]);
    items.forEach(d => {
      const mx = d.max || (Math.max(d.v, d.ref || 0, d.hi || 0) * 1.1) || 1;
      const pct = v => Math.min(Math.max(v / mx * 100, 0), 100);
      html += `<div style="margin-bottom:16px"><div style="font-size:11.5px; margin-bottom:4px; color:${SOFT}">${esc(d.name)}</div><div style="position:relative; height:22px; background:#EFEDE7">` +
        (d.lo != null && d.hi != null ? `<div style="position:absolute; left:${pct(d.lo)}%; width:${pct(d.hi) - pct(d.lo)}%; top:0; bottom:0; background:${rgba(P[0], 0.25)}"></div>` : '') +
        `<div style="position:absolute; left:0; width:${pct(d.v)}%; top:6px; bottom:6px; background:${P[0]}"></div>` +
        (d.ref != null ? `<div style="position:absolute; left:${pct(d.ref)}%; top:-3px; bottom:-3px; width:2px; background:${EXTRA[0]}"></div>` : '') +
        `</div><div style="font-size:10.5px; color:${SOFT}; margin-top:3px">${esc(nV)}: <b>${fmt(d.v)}${unit}</b>` +
        (d.ref != null ? ` · ${esc(nR)}: ${fmt(d.ref)}` : '') + (d.lo != null && d.hi != null ? ` · ${esc(nRg)}: ${fmt(d.lo)}–${fmt(d.hi)}` : '') + '</div></div>';
    });
    return htmlIn(c, html);
  };
  R.gauge = (c, def) => {
    const r0 = def.rows[0] || [];
    const text = r0[0] || '';
    let v = num(r0[1]); if (v == null) v = 0;
    v = Math.min(Math.max(v, 0), 100) / 100;
    const W = 300, H = 192, cx = W / 2, cy = 160, r = 110;
    const pt = (p, rad) => { const a = Math.PI + p * Math.PI; return [cx + rad * Math.cos(a), cy + rad * Math.sin(a)]; };
    const arc = (p0, p1) => { const [xa, ya] = pt(p0, r), [xb, yb] = pt(p1, r); return `M${xa},${ya} A${r},${r} 0 0 1 ${xb},${yb}`; };
    const [nx, ny] = pt(v, r - 15);
    const svg = `<svg viewBox="0 0 ${W} ${H}" style="width:100%; max-width:360px; height:auto; display:block; margin:0 auto" font-family="Georgia,serif">
      <path d="${arc(0, 0.33)}" stroke="#8FBF8F" stroke-width="22" fill="none"/><path d="${arc(0.33, 0.66)}" stroke="#E8C24A" stroke-width="22" fill="none"/><path d="${arc(0.66, 1)}" stroke="#A63D2F" stroke-width="22" fill="none"/>
      <line x1="${cx}" y1="${cy}" x2="${nx}" y2="${ny}" stroke="${INK}" stroke-width="3"/><circle cx="${cx}" cy="${cy}" r="6" fill="${INK}"/>
      <text x="${cx}" y="${cy + 26}" text-anchor="middle" font-size="14" font-weight="700" fill="${INK}">${esc(text)}</text>
      <text x="16" y="${cy + 6}" font-size="10" fill="${SOFT}">${esc(def.options.left_label || 'Bajo')}</text>
      <text x="${W - 16}" y="${cy + 6}" text-anchor="end" font-size="10" fill="${SOFT}">${esc(def.options.right_label || 'Alto')}</text></svg>`;
    return htmlIn(c, svg);
  };

  // ---- punto de entrada -----------------------------------------------------
  window.renderPostChart = function (container, def, accentHex, opts) {
    opts = opts || {}; accentHex = accentHex || {};
    def = Object.assign({ chart_type: 'bar_comparison', labels: [], series: [], rows: null, series_names: [], color: 'orange', options: {} }, def);
    if (!def.options || typeof def.options !== 'object') def.options = {};
    if (!def.rows) def.rows = def.labels.map((l, i) => [l].concat(def.series.map(s => s[i])));
    const spec = SPECS[def.chart_type] || SPECS.bar_comparison;
    const fn = R[SPECS[def.chart_type] ? def.chart_type : 'bar_comparison'];
    const main = accentHex[def.color] || '#C1622E';
    const P = [main].concat(EXTRA.filter(x => x.toLowerCase() !== main.toLowerCase()));
    if (spec.kind === 'canvas') {
      if (typeof Chart === 'undefined') return null;
      Chart.defaults.font.family = "Georgia, 'Times New Roman', serif";
      Chart.defaults.color = SOFT;
      Chart.defaults.font.size = 11.5;
    }
    return fn(container, def, P, { animate: opts.animate !== false });
  };
})();
