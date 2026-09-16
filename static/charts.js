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
     renderPostChart(container, def, accentHex, {animate, onSeriesClick})
       container = el <div class="chart-wrap"> donde dibujar
       def       = {chart_type, labels, series, rows, series_names, color, colors, options}
       accentHex = {blue:'#0000CC', orange:'#C1622E', ...}
       onSeriesClick(i, evento): solo el editor; se llama al hacer clic sobre
                   una serie (o su nombre en la leyenda) con el índice de color
     parseChartTable(texto) -> {labels, series, rows}   (misma regla que app.py)
     chartColorSlots(tipo, parsed, nombres) -> nombres de cada color a elegir
     chartColorHex(clave o "#RRGGBB") -> hex, o null si no vale
     CHART_SPECS, CHART_GROUPS, CHART_PALETTE, CHART_PALETTE_GROUPS (editor)
*/
(function () {
  'use strict';

  const GRID = '#EAE5D8', INK = '#1A1A1A', SOFT = '#5B564C', LINE = '#DFDACD';
  // Colores secundarios, en orden, después del color principal del gráfico.
  const EXTRA = ['#3B0A0A', '#1F4E5F', '#0000CC', '#A63D2F', '#7C6A9C', '#8C7A4A', '#B9B4A6', '#E8C24A'];
  // Paleta para elegir el color de cada serie en el editor (clave -> color).
  // Las claves se guardan en la base, así que no hay que renombrarlas. El
  // editor también acepta un color libre en hexadecimal ("#RRGGBB"): ver
  // colorHex(). Las cuatro primeras son las del sistema de diseño.
  const PALETTE = {};
  const group = (name, list) => list.forEach(([k, hex, label]) => { PALETTE[k] = { hex, label, group: name }; });
  group('Institucional', [
    ['blue', '#0000CC', 'Azul institucional'], ['orange', '#C1622E', 'Naranja (petróleo)'], ['navy', '#1F4E5F', 'Navy (gas)'],
    ['maroon', '#3B0A0A', 'Granate oscuro'], ['rust', '#A63D2F', 'Rojo óxido (alerta)'], ['gold', '#E8C24A', 'Dorado'],
    ['green', '#4E7D4E', 'Verde'], ['purple', '#7C6A9C', 'Violeta'], ['olive', '#8C7A4A', 'Oliva'], ['gray', '#B9B4A6', 'Gris'],
  ]);
  group('Vivos', [
    ['red', '#D0342C', 'Rojo'], ['coral', '#F2705D', 'Coral'], ['amber', '#F0A030', 'Ámbar'], ['yellow', '#F2D22E', 'Amarillo'],
    ['lime', '#9BC53D', 'Lima'], ['emerald', '#2E9E6B', 'Esmeralda'], ['teal', '#1F8A8A', 'Verde azulado'], ['cyan', '#2AB3D6', 'Celeste'],
    ['sky', '#4A90E2', 'Cielo'], ['indigo', '#3F51B5', 'Índigo'], ['violet', '#8E44AD', 'Violeta vivo'], ['magenta', '#C2185B', 'Magenta'],
    ['pink', '#E87DA8', 'Rosa'], ['brown', '#8B5A2B', 'Marrón'],
  ]);
  group('Pastel', [
    ['pastel_orange', '#E9B79A', 'Pastel naranja'], ['pastel_navy', '#9FBCC6', 'Pastel navy'], ['pastel_blue', '#AAB4EE', 'Pastel azul'],
    ['pastel_maroon', '#C9A0A0', 'Pastel granate'], ['pastel_rust', '#E0B0A8', 'Pastel óxido'], ['pastel_gold', '#F1DFA0', 'Pastel dorado'],
    ['pastel_green', '#B5D0B0', 'Pastel verde'], ['pastel_purple', '#C8BEDC', 'Pastel violeta'], ['pastel_teal', '#A8D5D0', 'Pastel turquesa'],
    ['pastel_gray', '#D9D4C7', 'Pastel gris'], ['pastel_pink', '#F4C2D0', 'Pastel rosa'], ['pastel_yellow', '#F6E7A3', 'Pastel amarillo'],
    ['pastel_lime', '#D5E3A0', 'Pastel lima'], ['pastel_sky', '#B9D6F2', 'Pastel cielo'], ['pastel_lilac', '#D9C7E8', 'Pastel lila'],
    ['pastel_coral', '#F5C1B0', 'Pastel coral'], ['pastel_mint', '#C4E6D1', 'Pastel menta'], ['pastel_sand', '#EAD9BF', 'Pastel arena'],
  ]);
  group('Tierra', [
    ['clay', '#A0522D', 'Arcilla'], ['sienna', '#C4763C', 'Siena'], ['sand', '#D9B98A', 'Arena'], ['khaki', '#B8A66B', 'Caqui'],
    ['moss', '#6E7B3A', 'Musgo'], ['forest', '#2F5D3A', 'Bosque'], ['slate', '#5C6B73', 'Pizarra'], ['taupe', '#8C8378', 'Topo'],
    ['chocolate', '#5B3A29', 'Chocolate'], ['wine', '#722F37', 'Vino'],
  ]);
  group('Oscuros', [
    ['dark_blue', '#0B2A6F', 'Azul marino'], ['dark_teal', '#0F4C5C', 'Petróleo'], ['dark_green', '#1B4D2B', 'Verde oscuro'],
    ['dark_red', '#7A1F1F', 'Rojo oscuro'], ['dark_purple', '#3E2A5C', 'Violeta oscuro'], ['charcoal', '#2F2F2F', 'Carbón'], ['black', '#1A1A1A', 'Negro'],
  ]);
  group('Grises', [
    ['gray_light', '#E6E2D8', 'Gris muy claro'], ['silver', '#C8C4BA', 'Plata'], ['stone', '#A39E93', 'Piedra'],
    ['ash', '#7D7870', 'Ceniza'], ['graphite', '#55514B', 'Grafito'],
  ]);
  window.CHART_PALETTE = PALETTE;
  window.CHART_PALETTE_GROUPS = ['Institucional', 'Vivos', 'Pastel', 'Tierra', 'Oscuros', 'Grises'];
  // Un color guardado puede ser una clave de la paleta o un "#RRGGBB" libre.
  const HEX_RE = /^#[0-9a-f]{6}$/i;
  const colorHex = k => PALETTE[k] ? PALETTE[k].hex : (HEX_RE.test(String(k || '')) ? String(k).toUpperCase() : null);
  window.chartColorHex = colorHex;
  const nf = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 1 });
  const fmt = v => (v === null || v === undefined || isNaN(v)) ? '' : nf.format(v);
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = v => { if (v === null || v === undefined || v === '') return null; const f = Number(v); return isNaN(f) ? null : f; };
  const hexRgb = hex => { const h = String(hex).replace('#', ''); return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; };
  const rgba = (hex, a) => { const [r, g, b] = hexRgb(hex); return `rgba(${r},${g},${b},${a})`; };
  const yes = v => /^(s[ií]|yes|1|true|x)$/i.test(String(v || '').trim());

  // ---- parseo de la tabla de texto (misma regla que parse_table en app.py) --
  // Columnas separadas por "|", coma, punto y coma o tabulación: se detecta
  // sola (o se fuerza con "sep": '|', ',', ';' o 'tab'). Celdas entre
  // comillas como en un CSV. Decimales con coma ("959,1") y miles con punto
  // ("1.172,5") pasan a la forma canónica ("959.1", "1172.5"). Una primera
  // fila con texto donde van los números es un encabezado: se descarta y se
  // devuelve en "header" (el editor la usa como nombres de las series).
  const SEPS = { '|': '|', ',': ',', ';': ';', tab: '\t' };
  const detectSep = text => ['\t', '|', ';', ','].find(s => text.includes(s)) || '|';
  const normCell = s => {
    const t = String(s == null ? '' : s).trim();
    if (/^-?\d{1,3}(\.\d{3})+(,\d+)?$/.test(t)) return t.replace(/\./g, '').replace(',', '.');
    if (/^-?\d+,\d+$/.test(t)) return t.replace(',', '.');
    if (/^-?\d{1,3}(,\d{3})+(\.\d+)?$/.test(t)) return t.replace(/,/g, '');
    return t;
  };
  // Una línea en celdas: la comilla doble solo es especial al principio de
  // la celda (como el módulo csv de Python).
  function splitLine(line, sep) {
    const cells = []; let cur = '', i = 0, quoted = false;
    while (i < line.length) {
      const ch = line[i];
      if (quoted) {
        if (ch === '"') { if (line[i + 1] === '"') { cur += '"'; i++; } else quoted = false; }
        else cur += ch;
      } else if (ch === '"' && cur.trim() === '') { quoted = true; cur = ''; }
      else if (ch === sep) { cells.push(cur); cur = ''; }
      else cur += ch;
      i++;
    }
    cells.push(cur);
    return cells;
  }
  const isHeaderRow = (r, chartType) => r.length >= 2 && (chartType === 'sankey' ? [r[r.length - 1]] : r.slice(1)).some(c => c !== '' && num(c) === null);
  // Las filas tal cual (sin descartar el encabezado ni normalizar números):
  // lo usa el editor para convertir un CSV subido.
  window.splitChartTable = function (text, sep) {
    text = String(text || '');
    const s = SEPS[sep] || detectSep(text);
    return text.split(/\r?\n/).map(l => l.trim()).filter(Boolean).map(l => {
      const cells = splitLine(l, s).map(c => c.trim());
      while (cells.length && cells[cells.length - 1] === '') cells.pop();
      return cells;
    }).filter(r => r.length);
  };
  window.parseChartTable = function (text, sep, chartType) {
    const rows = window.splitChartTable(text, sep).map(r => r.map(normCell));
    let header = null;
    if (rows.length && isHeaderRow(rows[0], chartType)) header = rows.shift();
    if (!rows.length) return { labels: [], series: [], rows: [], header };
    const labels = rows.map(r => r[0]);
    const nSeries = Math.max(...rows.map(r => r.length)) - 1;
    const series = [];
    for (let i = 0; i < nSeries; i++) series.push(rows.map(r => num(r[i + 1])));
    return { labels, series, rows, header };
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
    sankey: { label: 'Sankey (flujos origen → destino, con niveles)', group: 'Composición', kind: 'html',
      columns: 'Origen | destino | ... | valor   (cada fila es un camino; el valor recorre todo el camino)   —o—   Destino | valor   (un solo origen)', names: null,
      hint: 'Cintas de grosor proporcional al valor, con los niveles que hagan falta. Cada fila es un camino de nombres con el valor al final: "TGS | Oferta nacional | 74.1" (una entrada) o "Oferta nacional | Demanda interna | Usinas | 34.5" (una salida en dos pasos); los tramos que se repiten se suman. Lo más simple: "Destino | valor" y el nombre del origen en la opción de abajo. La plantilla Excel trae un balance de gas de ejemplo en dos bloques: entradas (Origen, Concepto, Valor) y salidas (Origen del Destino, Destino, Concepto, Valor).',
      placeholder: 'TGS | Oferta nacional | 74.1\nTGN | Oferta nacional | 42.2\nGPNK | Oferta nacional | 23.3\nFST | Oferta nacional | 15.8\nBolivia | Importación | 4.3\nGNL | Importación | 5.8\nOferta nacional | Demanda interna | Demanda prioritaria | 65.8\nOferta nacional | Demanda interna | Usinas | 34.5\nOferta nacional | Demanda interna | Industrias | 32\nOferta nacional | Demanda interna | GNC | 5.5\nImportación | Demanda interna | Combustible | 3.8\nImportación | Demanda interna | Tierra del Fuego | 0.6\nImportación | Demanda interna | Retenido en PSL | 7\nOferta nacional | Demanda interna | Resto | 8.8\nOferta nacional | Exportaciones | Chile | 6.9\nOferta nacional | Exportaciones | Uruguay | 0.5',
      // Plantilla Excel con la estructura de balance: dos bloques lado a lado.
      // Bloque 1 (entradas): Origen | Concepto | Valor = el concepto entra al
      // origen. Bloque 2 (salidas): Origen del Destino | Destino | Concepto |
      // Valor = camino de tres nombres. El editor la reconoce por el
      // encabezado "Origen del Destino" al importarla.
      template: [
        ['Origen', 'Concepto', 'Valor', 'Origen del Destino', 'Destino', 'Concepto', 'Valor'],
        ['Oferta nacional', 'TGS', 74.1, 'Oferta nacional', 'Demanda Interna', 'Demanda prioritaria', 65.8],
        ['Oferta nacional', 'TGN', 42.2, 'Oferta nacional', 'Demanda Interna', 'Usinas', 34.5],
        ['Oferta nacional', 'GPNK', 23.3, 'Oferta nacional', 'Demanda Interna', 'Industrias', 32],
        ['Oferta nacional', 'FST', 15.8, 'Oferta nacional', 'Demanda Interna', 'GNC', 5.5],
        ['Importación', 'Bolivia', 4.3, 'Importación', 'Demanda Interna', 'Combustible', 3.8],
        ['Importación', 'Chile', 0, 'Importación', 'Demanda Interna', 'Tierra del Fuego', 0.6],
        ['Importación', 'GNL', 5.8, 'Importación', 'Demanda Interna', 'Retenido en PSL', 7],
        ['', '', '', 'Oferta nacional', 'Demanda Interna', 'Resto', 8.8],
        ['', '', '', 'Oferta nacional', 'Exportaciones', 'Chile', 6.9],
        ['', '', '', 'Oferta nacional', 'Exportaciones', 'Uruguay', 0.5],
        ['', '', '', 'Oferta nacional', 'Exportaciones', 'Brasil', 0],
      ],
      options: [{ key: 'origin', label: 'Origen (si cargás Destino | valor)', placeholder: 'Gas exportado 2025' }, OPT_UNIT] },
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
  // Encabezado de la plantilla Excel de cada tipo (una columna por celda; la
  // cantidad coincide con el ejemplo "placeholder"). Al subir una planilla,
  // en los tipos de HEADER_NAMES la fila de encabezado pasa a ser los
  // nombres de las series (o títulos de ejes); en los demás solo se descarta.
  const HEADERS = {
    bar_comparison: ['Etiqueta', 'Serie 1', 'Serie 2'], bar_horizontal: ['Etiqueta', 'Valor'], diverging_bar: ['Etiqueta', 'Valor'],
    dumbbell: ['Etiqueta', 'Valor A', 'Valor B'], scatter: ['Serie', 'X', 'Y'], line: ['Período', 'Serie 1', 'Serie 2'],
    bar_line: ['Período', 'Barra', 'Línea'], stacked_area: ['Período', 'Serie 1', 'Serie 2'], bump: ['Período', 'A', 'B', 'C'],
    heatmap: ['Fila', '2020', '2021', '2022'], waterfall: ['Etiqueta', 'Valor'],
    fan_chart: ['Período', 'Real', 'Pronóstico', 'Banda 1 bajo', 'Banda 1 alto', 'Banda 2 bajo', 'Banda 2 alto', 'Banda 3 bajo', 'Banda 3 alto'],
    stacked_bar: ['Etiqueta', 'Parte 1', 'Parte 2', 'Parte 3'], stacked_bar_100: ['Etiqueta', 'Parte 1', 'Parte 2', 'Parte 3'],
    treemap: ['Nombre', 'Valor'], sankey: ['Destino', 'Valor'], shaded_list: ['Zona', 'Valor'],
    boxplot: ['Etiqueta', 'Mínimo', 'Cuartil 1', 'Mediana', 'Cuartil 3', 'Máximo'],
    bullet: ['Nombre', 'Valor', 'Referencia', 'Rango bajo', 'Rango alto', 'Máximo de la escala'], gauge: ['Lectura', 'Valor (0 a 100)'],
  };
  Object.entries(HEADERS).forEach(([k, h]) => { if (SPECS[k]) SPECS[k].header = h; });
  window.CHART_HEADER_NAMES = ['bar_comparison', 'line', 'bar_line', 'stacked_area', 'bump', 'stacked_bar', 'stacked_bar_100', 'heatmap', 'dumbbell', 'bar_horizontal', 'diverging_bar', 'scatter'];
  // Los gráficos de Chart.js aceptan un alto a medida (los de SVG/HTML tienen el suyo).
  const OPT_H = { key: 'height', label: 'Alto del gráfico (px)', placeholder: '360' };
  Object.values(SPECS).forEach(s => { if (s.kind === 'canvas') s.options = (s.options || []).concat([OPT_H]); });
  // Qué colores se eligen en el editor: uno por serie ("series"), uno por
  // bloque o destino ("items": treemap y Sankey), uno solo, o ninguno.
  const SERIES_TYPES = ['bar_comparison', 'line', 'bar_line', 'stacked_area', 'bump', 'stacked_bar', 'stacked_bar_100', 'scatter', 'dumbbell'];
  const ITEM_TYPES = ['treemap', 'sankey'];
  Object.entries(SPECS).forEach(([k, s]) => { s.colorMode = k === 'gauge' ? 'none' : (SERIES_TYPES.includes(k) ? 'series' : (ITEM_TYPES.includes(k) ? 'items' : 'single')); });
  const MAX_COLORS = 24;
  // Los "lugares" de color de un gráfico según sus datos: el nombre de cada
  // serie (o bloque, o destino), en el mismo orden en que se dibujan. El
  // índice de cada uno es el que se usa en def.colors y el que reciben los
  // clics sobre el gráfico (onSeriesClick).
  window.chartColorSlots = function (chartType, parsed, names) {
    names = names || [];
    const spec = SPECS[chartType] || SPECS.bar_comparison;
    const rows = parsed.rows || [];
    if (spec.colorMode === 'none') return [];
    if (spec.colorMode === 'single') return ['Color principal'];
    let out;
    if (chartType === 'scatter') out = [...new Set(rows.map(r => r[0]).filter(Boolean))];
    else if (chartType === 'dumbbell') out = [names[0] || 'A', names[1] || 'B'];
    else if (chartType === 'treemap') out = rows.filter(r => num(r[1]) > 0).map(r => r[0]);
    else if (chartType === 'sankey') out = sankeyTargets(sankeyFlows(rows, 'Origen'));
    else { const n = Math.max(1, parsed.series.length); out = []; for (let i = 0; i < n; i++) out.push(names[i] || ('Serie ' + (i + 1))); }
    if (!out.length) out = ['Serie 1'];
    return out.slice(0, MAX_COLORS);
  };
  window.chartSeriesCount = (chartType, parsed) => window.chartColorSlots(chartType, parsed, []).length || 1;
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
  // Leyenda a mano para los gráficos en HTML: [color, texto, índice de color]
  // (el índice va en data-si para que el editor sepa qué color se tocó).
  const legendRow = items => '<div class="legend-row">' + items.map(([c, t, si]) => `<span${si !== undefined ? ` data-si="${si}"` : ''}><span class="dot" style="background:${c}"></span>${esc(t)}</span>`).join('') + '</div>';
  const seriesName = (def, i, fallback) => (def.series_names && def.series_names[i]) || fallback || ('Serie ' + (i + 1));
  const widthOf = c => Math.max(c.clientWidth || 600, 320);

  // Opciones comunes de Chart.js. Si el que dibuja pasó onSeriesClick (el
  // editor), un clic sobre una barra, punto o nombre de la leyenda avisa qué
  // serie se tocó: cada dataset lleva su índice de color en "_si" (-1 = no
  // elegible, ej. la línea y = x del scatter). Sin onSeriesClick (el post
  // público) no cambia nada: la leyenda sigue ocultando series al tocarla.
  function baseOptions(o) {
    const opt = { responsive: true, maintainAspectRatio: false, animation: o.animate ? undefined : false,
      plugins: { legend: { position: 'top', labels: { boxWidth: 10 } } }, scales: {} };
    if (o.onSeriesClick) {
      const slot = (chart, idx) => { const ds = chart.data.datasets[idx]; return ds && ds._si !== undefined ? ds._si : idx; };
      opt.onClick = (evt, els, chart) => {
        let hit = els[0];
        if (!hit) {   // líneas finas: vale el punto más cercano si está a menos de 28 px
          const near = chart.getElementsAtEventForMode(evt.native, 'nearest', { intersect: false, axis: 'xy' }, false)[0];
          if (near && Math.hypot(near.element.x - evt.x, near.element.y - evt.y) < 28) hit = near;
        }
        if (hit) { const i = slot(chart, hit.datasetIndex); if (i >= 0) o.onSeriesClick(i, evt.native); }
      };
      opt.onHover = (evt, els) => { if (evt.native && evt.native.target) evt.native.target.style.cursor = els.length ? 'pointer' : ''; };
      opt.plugins.legend.onClick = (evt, item, legend) => { const i = slot(legend.chart, item.datasetIndex); if (i >= 0) o.onSeriesClick(i, evt.native); };
    }
    return opt;
  }
  const axis = (title, extra) => Object.assign({ grid: { color: GRID } }, title ? { title: { display: true, text: title } } : {}, extra || {});
  const noGrid = extra => Object.assign({ grid: { display: false } }, extra || {});

  const R = {};

  // ---- Chart.js -------------------------------------------------------------
  R.bar_comparison = (c, def, P, o) => {
    const opt = baseOptions(o);
    opt.scales = { y: axis(def.options.y_title), x: noGrid() };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, i) => ({ label: seriesName(def, i), data: s, backgroundColor: P[i % P.length], _si: i })) } });
  };
  R.bar_horizontal = (c, def, P, o) => {
    let pairs = def.labels.map((l, i) => [l, def.series[0] ? def.series[0][i] : null]);
    if (yes(def.options.sort)) pairs = pairs.slice().sort((a, b) => (b[1] || 0) - (a[1] || 0));
    const opt = baseOptions(o); opt.indexAxis = 'y'; opt.plugins.legend.display = false;
    opt.scales = { x: axis(def.series_names[0]), y: noGrid() };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: pairs.map(p => p[0]),
      datasets: [{ data: pairs.map(p => p[1]), backgroundColor: P[0], _si: 0 }] } });
  };
  R.diverging_bar = (c, def, P, o) => {
    const vals = def.series[0] || [];
    const opt = baseOptions(o); opt.indexAxis = 'y'; opt.plugins.legend.display = false;
    opt.scales = { x: axis(def.series_names[0]), y: noGrid() };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: def.labels,
      datasets: [{ data: vals, backgroundColor: vals.map(v => (v || 0) < 0 ? '#A63D2F' : P[0]), _si: 0 }] } });
  };
  R.scatter = (c, def, P, o) => {
    const groups = new Map();
    def.rows.forEach(r => { const x = num(r[1]), y = num(r[2]); if (x == null || y == null) return;
      const k = r[0] || 'Serie'; if (!groups.has(k)) groups.set(k, []); groups.get(k).push({ x, y }); });
    const ds = [...groups.entries()].map(([k, pts], i) => ({ label: k, data: pts, backgroundColor: P[i % P.length], pointRadius: 6, _si: i }));
    if (yes(def.options.diagonal)) {
      const m = Math.max(0, ...[...groups.values()].flat().flatMap(p => [p.x, p.y])) * 1.05;
      ds.push({ label: 'y = x', data: [{ x: 0, y: 0 }, { x: m, y: m }], type: 'line', borderColor: '#999', borderDash: [4, 4], borderWidth: 1.3, pointRadius: 0, fill: false, _si: -1 });
    }
    const opt = baseOptions(o);
    opt.scales = { x: axis(def.series_names[0]), y: axis(def.series_names[1]) };
    return new Chart(canvasIn(c), { type: 'scatter', options: opt, data: { datasets: ds } });
  };
  R.line = (c, def, P, o) => {
    const opt = baseOptions(o);
    opt.scales = { y: axis(def.options.y_title), x: noGrid() };
    return new Chart(canvasIn(c), { type: 'line', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, i) => ({ label: seriesName(def, i), data: s, borderColor: P[i % P.length], backgroundColor: 'transparent', borderWidth: 2.2, pointRadius: 2, tension: 0.2, _si: i })) } });
  };
  R.bar_line = (c, def, P, o) => {
    const n = def.series.length;
    const ds = def.series.map((s, i) => (n > 1 && i === n - 1)
      ? { type: 'line', label: seriesName(def, i), data: s, borderColor: P[i % P.length], backgroundColor: P[i % P.length], borderWidth: 2.2, pointRadius: 3, tension: 0.2, yAxisID: 'y2', order: 1, _si: i }
      : { type: 'bar', label: seriesName(def, i), data: s, backgroundColor: P[i % P.length], yAxisID: 'y', order: 2, _si: i });
    const opt = baseOptions(o);
    opt.scales = { x: noGrid(), y: axis(def.options.y_title, { position: 'left' }) };
    if (n > 1) opt.scales.y2 = axis(def.options.y2_title, { position: 'right', grid: { drawOnChartArea: false } });
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: def.labels, datasets: ds } });
  };
  R.stacked_area = (c, def, P, o) => {
    const opt = baseOptions(o);
    opt.scales = { y: axis(def.options.y_title, { stacked: true }), x: noGrid({ ticks: { maxTicksLimit: 12 } }) };
    return new Chart(canvasIn(c), { type: 'line', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, i) => ({ label: seriesName(def, i), data: s, borderColor: P[i % P.length], backgroundColor: rgba(P[i % P.length], 0.55), fill: true, borderWidth: 1, pointRadius: 0, _si: i })) } });
  };
  R.bump = (c, def, P, o) => {
    const maxRank = Math.max(def.series.length, ...def.series.flat().filter(v => v != null), 1);
    const opt = baseOptions(o);
    opt.scales = { x: noGrid(), y: axis(null, { reverse: true, min: 1, max: maxRank, ticks: { stepSize: 1, callback: v => '#' + v } }) };
    return new Chart(canvasIn(c), { type: 'line', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, i) => ({ label: seriesName(def, i), data: s, borderColor: P[i % P.length], backgroundColor: P[i % P.length], borderWidth: 2.2, pointRadius: 4, tension: 0.15, _si: i })) } });
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
    const opt = baseOptions(o); opt.plugins.legend.display = false;
    opt.plugins.tooltip = { callbacks: { label: ctx => fmt(shown[ctx.dataIndex]) } };
    opt.scales = { y: axis(def.options.y_title), x: noGrid() };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels, datasets: [{ data: bars, backgroundColor: colors, _si: 0 }] } });
  };
  R.stacked_bar = (c, def, P, o) => {
    const opt = baseOptions(o);
    opt.scales = { x: noGrid({ stacked: true }), y: axis(def.options.y_title, { stacked: true }) };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, i) => ({ label: seriesName(def, i), data: s, backgroundColor: P[i % P.length], _si: i })) } });
  };
  R.stacked_bar_100 = (c, def, P, o) => {
    const totals = def.labels.map((_, i) => def.series.reduce((s, ser) => s + (ser[i] || 0), 0));
    const opt = baseOptions(o);
    opt.scales = { x: noGrid({ stacked: true }), y: axis('%', { stacked: true, max: 100 }) };
    return new Chart(canvasIn(c), { type: 'bar', options: opt, data: { labels: def.labels,
      datasets: def.series.map((s, k) => ({ label: seriesName(def, k), data: s.map((v, i) => totals[i] ? (v || 0) / totals[i] * 100 : null), backgroundColor: P[k % P.length], _si: k })) } });
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
      ds.push({ label: '_hi' + k, data: bands[k].hi, borderWidth: 0, pointRadius: 0, fill: false, _si: -1 });
      ds.push({ label: bands[k].name, data: bands[k].lo, borderWidth: 0, pointRadius: 0, fill: '-1', backgroundColor: rgba(P[0], alphas[k]), _si: 0 });
    }
    ds.push({ label: seriesName(def, 1, 'Pronóstico'), data: pred, borderColor: P[0], borderDash: [5, 4], borderWidth: 2, pointRadius: 0, _si: 0 });
    ds.push({ label: seriesName(def, 0, 'Real'), data: real, borderColor: P[0], borderWidth: 2.2, pointRadius: 0, _si: 0 });
    const opt = baseOptions(o);
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
      if (va != null) svg += `<circle cx="${xs(va)}" cy="${y}" r="6" fill="${P[0]}" data-si="0"><title>${esc(nA)}: ${fmt(va)}</title></circle>`;
      if (vb != null) svg += `<circle cx="${xs(vb)}" cy="${y}" r="6" fill="${P[1]}" data-si="1"><title>${esc(nB)}: ${fmt(vb)}</title></circle>`;
    });
    return htmlIn(c, legendRow([[P[0], nA, 0], [P[1], nB, 1]]) + svg + '</svg>');
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
      html += `<div data-si="${i}" title="${esc(d.name)}: ${fmt(d.v)} ${esc(unit)} (${pct.toFixed(1)}%)" style="flex:${pct} 1 ${pct}%; min-width:72px; min-height:64px; background:${P[i % P.length]}; color:#fff; display:flex; align-items:flex-end; padding:6px; font-size:10.5px; line-height:1.25;">${esc(d.name)}<br><b>${fmt(d.v)} ${esc(unit)}</b></div>`; });
    return htmlIn(c, html + '</div>');
  };
  // Sankey de varios niveles. Cada fila de datos es un camino de nombres con
  // el valor al final ("TGS | Oferta nacional | 74.1"; "Oferta nacional |
  // Demanda interna | Usinas | 34.5"): el valor recorre todo el camino y los
  // tramos repetidos se suman. Con un solo nombre ("Chile | 340.8") el
  // origen es "single" (opción "origin" o título del gráfico). Devuelve los
  // tramos {s, t, v} en orden de aparición.
  window.sankeyFlows = function (rows, single) {
    const links = [], byKey = new Map();
    (rows || []).forEach(r => {
      const cells = r.map(x => String(x == null ? '' : x).trim());
      let last = cells.length - 1;
      while (last >= 0 && cells[last] === '') last--;
      if (last < 1) return;
      const v = num(cells[last]);
      if (!(v > 0)) return;
      let path = cells.slice(0, last).filter(Boolean);
      if (path.length === 1) path = [single || 'Origen', path[0]];
      for (let i = 0; i + 1 < path.length; i++) {
        if (path[i] === path[i + 1]) continue;
        const k = path[i] + ' ' + path[i + 1];
        if (!byKey.has(k)) { byKey.set(k, { s: path[i], t: path[i + 1], v: 0 }); links.push(byKey.get(k)); }
        byKey.get(k).v += v;
      }
    });
    return links;
  };
  // Los colores del Sankey son uno por nodo destino, en orden de aparición
  // (los nodos que solo son origen van en gris oscuro).
  const sankeyTargets = links => [...new Set(links.map(l => l.t))];
  R.sankey = (c, def, P) => {
    const links = sankeyFlows(def.rows, def.options.origin || def.title || 'Origen');
    if (!links.length) return htmlIn(c, '');
    const unit = def.options.unit || '';
    // Nodos en orden de aparición; nivel = camino más largo desde un origen.
    const nodes = [], byName = new Map();
    const node = name => { let n = byName.get(name); if (!n) { n = { name, in: 0, out: 0, depth: 0, inOff: 0, outOff: 0 }; byName.set(name, n); nodes.push(n); } return n; };
    links.forEach(l => { node(l.s).out += l.v; node(l.t).in += l.v; });
    for (let iter = 0; iter < nodes.length; iter++) {   // relajación acotada: un ciclo no cuelga
      let changed = false;
      links.forEach(l => { const s = byName.get(l.s), t = byName.get(l.t); if (t.depth < s.depth + 1 && s.depth + 1 < nodes.length) { t.depth = s.depth + 1; changed = true; } });
      if (!changed) break;
    }
    const targets = sankeyTargets(links);
    nodes.forEach(n => { n.total = Math.max(n.in, n.out); n.si = targets.indexOf(n.name); n.color = n.si >= 0 ? P[n.si % P.length] : '#333'; });
    const maxDepth = Math.max(...nodes.map(n => n.depth));
    const cols = []; for (let d = 0; d <= maxDepth; d++) cols.push(nodes.filter(n => n.depth === d));
    const W = widthOf(c), gap = 10, padT = 16, padB = 12, bw = 14;
    const maxN = Math.max(...cols.map(col => col.length));
    const H = Math.max(220, Math.min(560, 32 * maxN + 90));
    const valueTxt = n => `${fmt(n.total)}${unit ? ' ' + unit : ''}`;
    const label = n => `${n.name} — ${valueTxt(n)}`;
    const textW = (s, fs) => Math.round(s.length * (fs || 11.5) * 0.56) + 6;
    // Rótulos: primera columna a la izquierda y última a la derecha, en
    // negro sobre el margen blanco. Las columnas del medio son bloques
    // anchos con el nombre y el valor adentro, en blanco; si el rótulo no
    // entra en el bloque, va afuera (debajo del nodo) en negro.
    // Rótulos laterales: con unidad si entran en el margen (30 % del ancho);
    // si no, sin unidad; si no, solo el nombre (el valor queda en el tooltip).
    const cap = Math.floor(W * 0.3);
    const noUnit = n => `${n.name} — ${fmt(n.total)}`;
    const sideStyle = col => { const widest = f => Math.max(...col.map(n => textW(f(n)) + 12)); return widest(label) <= cap ? label : (widest(noUnit) <= cap ? noUnit : (n => n.name)); };
    const labelL = sideStyle(cols[0]), labelR = sideStyle(cols[maxDepth]);
    const labL = Math.max(90, Math.min(cap, Math.max(...cols[0].map(n => textW(labelL(n)) + 12))));
    const labR = Math.max(90, Math.min(cap, Math.max(...cols[maxDepth].map(n => textW(labelR(n)) + 12))));
    const firstX = labL, lastX = W - labR - bw, nMid = Math.max(0, maxDepth - 1);
    let nw = 0;   // ancho de los nodos intermedios: el rótulo más largo, sin comerse las cintas
    if (nMid) {
      const mids = cols.slice(1, maxDepth).flat();
      nw = Math.min(170, Math.max(60, ...mids.map(n => Math.max(textW(n.name), textW(valueTxt(n))) + 16)));
      nw = Math.max(24, Math.min(nw, (lastX - firstX - bw - 60 * maxDepth) / nMid));
    }
    const gapX = maxDepth ? (lastX - firstX - bw - nw * nMid) / maxDepth : 0;
    const colX = d => d === 0 ? firstX : (d === maxDepth ? lastX : firstX + bw + gapX * d + nw * (d - 1));
    const isMid = n => n.depth > 0 && n.depth < maxDepth;
    const fitsTwo = n => isMid(n) && n.h >= 30 && nw >= Math.max(textW(n.name), textW(valueTxt(n))) + 8;
    const fitsOne = n => isMid(n) && n.h >= 16 && nw >= textW(label(n), 10.5) + 8;
    // Rótulo debajo del nodo: se acorta para no pisar el de la columna vecina.
    const belowTxt = n => { const pitch = gapX + nw - 6; return textW(label(n), 10.5) <= pitch ? label(n) : (textW(noUnit(n), 10.5) <= pitch ? noUnit(n) : n.name); };
    // Escala: la columna más cargada tiene que entrar en el alto. Los nodos
    // cuyo rótulo va debajo reservan 16 px más; como eso cambia las alturas,
    // se itera hasta que la decisión no cambie.
    let k;
    for (let pass = 0; pass < 4; pass++) {
      k = Math.min(...cols.map(col => (H - padT - padB - col.reduce((s, n) => s + gap + (n.below ? 16 : 0), -gap)) / (col.reduce((s, n) => s + n.total, 0) || 1)));
      cols.forEach((col, d) => {
        let y = padT;
        col.forEach(n => { n.x = colX(d); n.w = isMid(n) ? nw : bw; n.y = y; n.h = Math.max(n.total * k, 2); y += n.h + gap + (n.below ? 16 : 0); });
      });
      let changed = false;
      nodes.forEach(n => { const below = isMid(n) && !fitsTwo(n) && !fitsOne(n); if (below !== !!n.below) { n.below = below; changed = true; } });
      if (!changed) break;
    }
    // Texto adentro: blanco, salvo sobre colores muy claros.
    const inkOn = hex => { const [r, g, b] = hexRgb(hex); return (0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.72 ? INK : '#fff'; };
    let svg = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="Georgia,serif">`;
    // Cintas: salen por la derecha del origen y entran por la izquierda del destino, en orden.
    links.forEach(l => {
      const s = byName.get(l.s), t = byName.get(l.t);
      const h = l.v * k, sy = s.y + s.outOff, ty = t.y + t.inOff; s.outOff += h; t.inOff += h;
      const xa = s.x + s.w, xb = t.x, xm = (xa + xb) / 2;
      svg += `<path d="M${xa},${sy} C${xm},${sy} ${xm},${ty} ${xb},${ty} L${xb},${ty + h} C${xm},${ty + h} ${xm},${sy + h} ${xa},${sy + h} Z" fill="${t.color}" opacity="0.62" data-si="${t.si}"><title>${esc(l.s)} → ${esc(l.t)}: ${fmt(l.v)} ${esc(unit)}</title></path>`;
    });
    cols.forEach((col, d) => {
      let last = -Infinity;
      col.forEach(n => {
        svg += `<rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" fill="${n.color}"${n.si >= 0 ? ` data-si="${n.si}"` : ''}><title>${esc(label(n))}</title></rect>`;
        const cx = n.x + n.w / 2, cy0 = n.y + n.h / 2;
        if (d === 0) {
          svg += `<text x="${n.x - 8}" y="${cy0 + 4}" text-anchor="end" font-size="11.5" fill="${INK}">${esc(labelL(n))}</text>`;
        } else if (d === maxDepth) {
          const cy = Math.max(cy0, last + 15); last = cy;   // etiquetas separadas al menos 15px
          if (Math.abs(cy - cy0) > 1) svg += `<line x1="${n.x + bw}" y1="${cy0}" x2="${n.x + bw + 6}" y2="${cy}" stroke="#999" stroke-width="1"/>`;
          svg += `<text x="${n.x + bw + 8}" y="${cy + 4}" font-size="11.5" fill="${INK}">${esc(labelR(n))}</text>`;
        } else if (fitsTwo(n)) {
          const ink = inkOn(n.color);
          svg += `<text x="${cx}" y="${cy0 - 3}" text-anchor="middle" font-size="11.5" font-weight="700" fill="${ink}">${esc(n.name)}</text>` +
            `<text x="${cx}" y="${cy0 + 11}" text-anchor="middle" font-size="11" fill="${ink}">${esc(valueTxt(n))}</text>`;
        } else if (fitsOne(n)) {
          svg += `<text x="${cx}" y="${cy0 + 4}" text-anchor="middle" font-size="10.5" font-weight="700" fill="${inkOn(n.color)}">${esc(label(n))}</text>`;
        } else {
          svg += `<text x="${cx}" y="${n.y + n.h + 12}" text-anchor="middle" font-size="10.5" fill="${INK}" stroke="#fff" stroke-width="2.5" paint-order="stroke" stroke-linejoin="round">${esc(belowTxt(n))}</text>`;
        }
      });
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
    // Colores por serie: los elegidos en el editor (def.colors: claves de la
    // paleta o "#RRGGBB"); donde no haya elección, el principal y luego los extra.
    const main = colorHex(def.color) || accentHex[def.color] || '#C1622E';
    const defaults = [main].concat(EXTRA.filter(x => x.toLowerCase() !== main.toLowerCase()));
    const chosen = Array.isArray(def.colors) ? def.colors : [];
    const P = [];
    for (let i = 0; i < Math.max(defaults.length, chosen.length); i++) {
      P.push((chosen[i] && colorHex(chosen[i])) || defaults[i] || EXTRA[i % EXTRA.length]);
    }
    const onSeriesClick = typeof opts.onSeriesClick === 'function' ? opts.onSeriesClick : null;
    if (spec.kind === 'canvas') {
      if (typeof Chart === 'undefined') return null;
      Chart.defaults.font.family = "Georgia, 'Times New Roman', serif";
      Chart.defaults.color = SOFT;
      Chart.defaults.font.size = 11.5;
      // Alto a medida (opción "height"); si no, el de la hoja de estilos.
      const h = parseInt(def.options.height, 10);
      container.style.height = (h >= 120 && h <= 1200) ? h + 'px' : '';
      container.onclick = null;
    } else {
      container.style.height = '';
      // En los gráficos de HTML/SVG el clic se resuelve acá: el elemento
      // tocado lleva data-si; si no lo lleva y el tipo tiene un solo color,
      // cualquier clic es sobre ese color.
      container.onclick = onSeriesClick ? (e => {
        const t = e.target && e.target.closest ? e.target.closest('[data-si]') : null;
        const i = t ? parseInt(t.dataset.si, 10) : (spec.colorMode === 'single' ? 0 : -1);
        if (i >= 0) onSeriesClick(i, e);
      }) : null;
    }
    container.classList.toggle('pickable', !!onSeriesClick);
    return fn(container, def, P, { animate: opts.animate !== false, onSeriesClick });
  };

  // ---- copiar / descargar una tarjeta de gráfico como PNG ------------------
  // Usa html2canvas (se carga desde el CDN recién cuando hace falta) para
  // rasterizar la tarjeta entera: título, gráfico, fuente y marca de agua.
  function loadHtml2Canvas() {
    if (window.html2canvas) return Promise.resolve(window.html2canvas);
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
      s.onload = () => resolve(window.html2canvas);
      s.onerror = () => reject(new Error('No se pudo cargar html2canvas'));
      document.head.appendChild(s);
    });
  }
  window.chartCardToPng = async function (card, mode) {
    const h2c = await loadHtml2Canvas();
    const canvas = await h2c(card, { scale: 2, backgroundColor: '#ffffff', useCORS: true, logging: false,
      ignoreElements: el => el.classList && el.classList.contains('chart-tools') });
    const blob = await new Promise(r => canvas.toBlob(r, 'image/png'));
    if (mode === 'copy' && navigator.clipboard && window.ClipboardItem) {
      await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]);
      return 'copied';
    }
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (card.dataset.filename || 'grafico') + '.png';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
    return 'downloaded';
  };
})();
