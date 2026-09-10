/* Dibuja un gráfico del post con Chart.js.
   Lo usan el post público (post.html) y el editor visual (admin_edit.html),
   así los dos ven exactamente lo mismo.

   renderPostChart(canvas, def, accentHex, opts)
     def       = {chart_type, labels, series, series_names, color}
     accentHex = {blue:'#0000CC', orange:'#C1622E', ...}
     opts      = {animate: true|false}
   Devuelve la instancia de Chart (o null si Chart.js no cargó). */
(function () {
  const GRIDCLR = '#EAE5D8';

  function setup() {
    if (typeof Chart === 'undefined') return false;
    Chart.defaults.font.family = "Georgia, 'Times New Roman', serif";
    Chart.defaults.color = '#5B564C';
    Chart.defaults.font.size = 11.5;
    return true;
  }

  window.renderPostChart = function (canvas, def, accentHex, opts) {
    if (!setup()) return null;
    opts = opts || {};
    // Si ya había un gráfico en este canvas (el editor redibuja), se destruye.
    const prev = Chart.getChart(canvas);
    if (prev) prev.destroy();

    const mainColor = accentHex[def.color] || '#C1622E';
    const seriesColors = [mainColor, '#3B0A0A', '#1F4E5F'];
    const names = def.series_names || [];
    const series = def.series || [];
    const name = i => names[i] || ('Serie ' + (i + 1));
    const base = {
      responsive: true, maintainAspectRatio: false,
      animation: opts.animate === false ? false : undefined,
      plugins: { legend: { position: 'top', labels: { boxWidth: 10 } } },
      scales: { y: { grid: { color: GRIDCLR } }, x: { grid: { display: false } } },
    };

    let cfg;
    if (def.chart_type === 'line') {
      cfg = { type: 'line', options: base, data: { labels: def.labels, datasets: series.map((s, i) => ({
        label: name(i), data: s, borderColor: seriesColors[i % 3], backgroundColor: 'transparent',
        borderWidth: 2.2, pointRadius: 2, tension: 0.2 })) } };
    } else if (def.chart_type === 'stacked_area') {
      cfg = { type: 'line', data: { labels: def.labels, datasets: series.map((s, i) => ({
        label: name(i), data: s, borderColor: seriesColors[i % 3], backgroundColor: seriesColors[i % 3] + '88',
        fill: true, borderWidth: 1, pointRadius: 0 })) },
        options: Object.assign({}, base, { scales: { y: { stacked: true, grid: { color: GRIDCLR } }, x: { grid: { display: false } } } }) };
    } else {
      cfg = { type: 'bar', options: base, data: { labels: def.labels, datasets: series.map((s, i) => ({
        label: name(i), data: s, backgroundColor: seriesColors[i % 3] })) } };
    }
    return new Chart(canvas, cfg);
  };
})();
