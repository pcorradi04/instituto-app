"""
De la base histórica al borrador del blog
=========================================
Dos partes:

1. `analizar()` — saca de cada serie los números que se repiten siempre:
   último dato, variación contra el período anterior, contra el mismo
   período del año pasado, promedio móvil, acumulado del año y máximo/mínimo
   de la ventana reciente. Nada de modelos: solo aritmética verificable.

2. `armar_borrador()` — escribe un post en estado **borrador** en la base del
   blog, con un gráfico por serie y un párrafo factual con esos números.

Sobre el texto: es a propósito seco y descriptivo (qué dato salió y cómo se
mueve), porque el criterio editorial del Instituto es que el análisis lo
escribe una persona. El borrador trae los datos, los gráficos y el aviso de
revisiones; la lectura la agrega quien publica.

Los bloques se arman pasándolos por `block_data_from_form()` de app.py — la
misma función que usa el editor visual al guardar. Así un gráfico creado por
el automático es indistinguible de uno cargado a mano y se puede editar
normalmente en el panel.
"""

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROYECTO = os.path.dirname(BASE_DIR)
if PROYECTO not in sys.path:
    sys.path.insert(0, PROYECTO)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ---------------------------------------------------------------------------
# Formato de números, a la argentina: miles con "." y decimales con ","
# ---------------------------------------------------------------------------

def fmt(valor, decimales=0):
    if valor is None:
        return "s/d"
    # Python formatea 1234.5 como "1,234.5"; acá se da vuelta a "1.234,5"
    # (el espacio es solo un paso intermedio: un número no tiene espacios).
    texto = f"{valor:,.{decimales}f}"
    return texto.replace(",", " ").replace(".", ",").replace(" ", ".")


def fmt_pct(nuevo, viejo, decimales=1):
    """Variación porcentual ya redactada: "+4,2 %" / "-1,8 %" / "sin cambios"."""
    if nuevo is None or viejo in (None, 0):
        return "s/d"
    var = (nuevo - viejo) / abs(viejo) * 100
    if abs(var) < 0.05:
        return "sin cambios"
    return f"{'+' if var > 0 else '-'}{fmt(abs(var), decimales)} %"


def periodo_largo(periodo, frecuencia):
    """"2026-09-26" (semanal) -> "la semana terminada el 26 de septiembre de 2026";
    "2026-07" (mensual) -> "julio de 2026"."""
    partes = periodo.split("-")
    try:
        anio = int(partes[0])
        mes = int(partes[1]) if len(partes) > 1 else 1
    except (ValueError, IndexError):
        return periodo
    if frecuencia == "weekly" and len(partes) > 2:
        return f"la semana terminada el {int(partes[2])} de {MESES[mes - 1]} de {anio}"
    if frecuencia == "annual" or len(partes) == 1:
        return str(anio)
    return f"{MESES[mes - 1]} de {anio}"


def fecha_larga(dt):
    return f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}"


# ---------------------------------------------------------------------------
# 1. Los números de cada serie
# ---------------------------------------------------------------------------

def analizar(datos, definicion):
    """`datos` = [(periodo, valor)] ordenado. Devuelve un dict de estadísticas
    (todas pueden ser None si la serie es corta: el texto se adapta)."""
    frecuencia = definicion.get("frecuencia", "monthly")
    por_anio = {"weekly": 52, "monthly": 12, "annual": 1}.get(frecuencia, 12)
    ventana_corta = 4 if frecuencia == "weekly" else 3     # promedio móvil
    ventana_extremos = 52 if frecuencia == "weekly" else 24

    valores = [v for _, v in datos]
    s = {
        "frecuencia": frecuencia,
        "periodos": len(datos),
        "primer_periodo": datos[0][0] if datos else None,
        "ultimo_periodo": datos[-1][0] if datos else None,
        "ultimo": valores[-1] if valores else None,
        "previo": valores[-2] if len(valores) > 1 else None,
        "hace_un_anio": valores[-1 - por_anio] if len(valores) > por_anio else None,
        "ventana_corta": ventana_corta,
    }

    if len(valores) >= ventana_corta:
        s["prom_corto"] = sum(valores[-ventana_corta:]) / ventana_corta
    else:
        s["prom_corto"] = None
    if len(valores) >= por_anio + ventana_corta:
        tramo = valores[-(por_anio + ventana_corta):-por_anio]
        s["prom_corto_anterior"] = sum(tramo) / len(tramo)
    else:
        s["prom_corto_anterior"] = None

    # Extremos de la ventana reciente.
    recientes = datos[-ventana_extremos:]
    if recientes:
        s["max_periodo"], s["max_valor"] = max(recientes, key=lambda p: p[1])
        s["min_periodo"], s["min_valor"] = min(recientes, key=lambda p: p[1])
        s["ventana_extremos"] = len(recientes)

    # Acumulado del año en curso contra el mismo tramo del año anterior.
    # Para un caudal (barriles por día) se promedia; para un volumen del
    # período (pies cúbicos del mes) se suma. Lo dice "agregacion".
    suma = definicion.get("agregacion", "suma") == "suma"
    if datos:
        anio_actual = datos[-1][0][:4]
        del_anio = [v for p, v in datos if p[:4] == anio_actual]
        anterior = str(int(anio_actual) - 1)
        # mismo número de períodos del año anterior, para que la comparación sea justa
        del_anio_anterior = [v for p, v in datos if p[:4] == anterior][:len(del_anio)]
        s["anio"] = anio_actual
        s["periodos_anio"] = len(del_anio)
        if del_anio:
            s["acum_anio"] = sum(del_anio) if suma else sum(del_anio) / len(del_anio)
        if len(del_anio_anterior) == len(del_anio) and del_anio_anterior:
            s["acum_anio_anterior"] = (sum(del_anio_anterior) if suma
                                       else sum(del_anio_anterior) / len(del_anio_anterior))
        else:
            s["acum_anio_anterior"] = None
        s["acumulado_es_suma"] = suma
    return s


def texto_serie(s, d):
    """El párrafo factual de una serie."""
    dec = d.get("decimales", 0)
    u = d.get("unidad", "")
    # "las últimas 4 semanas" / "los últimos 3 meses": concordancia según la
    # frecuencia de la serie.
    semanal = s["frecuencia"] == "weekly"
    ultimas, periodos = ("las últimas", "semanas") if semanal else ("los últimos", "meses")
    partes = []
    partes.append(
        f"El último dato disponible corresponde a {periodo_largo(s['ultimo_periodo'], s['frecuencia'])}: "
        f"**{fmt(s['ultimo'], dec)} {u}**."
    )
    if s.get("previo") is not None:
        cual = "la semana anterior" if semanal else "el mes anterior"
        partes.append(f"Contra {cual} ({fmt(s['previo'], dec)}), {fmt_pct(s['ultimo'], s['previo'])}.")
    if s.get("hace_un_anio") is not None:
        partes.append(
            f"Contra el mismo período de un año antes ({fmt(s['hace_un_anio'], dec)}), "
            f"{fmt_pct(s['ultimo'], s['hace_un_anio'])}."
        )
    if s.get("prom_corto") is not None:
        frase = (f"El promedio de {ultimas} {s['ventana_corta']} {periodos} "
                 f"es de {fmt(s['prom_corto'], dec)} {u}")
        if s.get("prom_corto_anterior") is not None:
            frase += (f", {fmt_pct(s['prom_corto'], s['prom_corto_anterior'])} que en el mismo tramo "
                      f"del año anterior ({fmt(s['prom_corto_anterior'], dec)})")
        partes.append(frase + ".")
    if s.get("acum_anio") is not None:
        que = "El acumulado" if s.get("acumulado_es_suma") else "El promedio"
        frase = (f"{que} de {s['anio']} ({s['periodos_anio']} {periodos}) "
                 f"es de {fmt(s['acum_anio'], dec)} {u}")
        if s.get("acum_anio_anterior") is not None:
            frase += (f", {fmt_pct(s['acum_anio'], s['acum_anio_anterior'])} que el mismo tramo "
                      f"de {int(s['anio']) - 1} ({fmt(s['acum_anio_anterior'], dec)})")
        partes.append(frase + ".")
    if s.get("max_valor") is not None:
        partes.append(
            f"En {ultimas} {s['ventana_extremos']} {periodos} el máximo fue "
            f"{fmt(s['max_valor'], dec)} ({periodo_largo(s['max_periodo'], s['frecuencia'])}) "
            f"y el mínimo {fmt(s['min_valor'], dec)} ({periodo_largo(s['min_periodo'], s['frecuencia'])})."
        )
    return " ".join(partes)


# ---------------------------------------------------------------------------
# 2. Los bloques del post
# ---------------------------------------------------------------------------

def tabla(datos, decimales=2):
    """[(periodo, valor)] -> la tabla de texto que entienden los gráficos."""
    filas = []
    for periodo, valor in datos:
        v = round(valor, decimales)
        filas.append(f"{periodo} | {int(v) if float(v).is_integer() else v}")
    return "\n".join(filas)


def bloques_de_serie(clave, d, datos, stats, revisiones):
    """Los bloques de la sección de una serie: título, gráfico y párrafo."""
    recorte = datos[-int(d.get("periodos_grafico", 60)):]
    unidad_corta = d.get("unidad_corta", "")
    desde = periodo_largo(recorte[0][0], d["frecuencia"]) if recorte else ""
    hasta = periodo_largo(recorte[-1][0], d["frecuencia"]) if recorte else ""
    nota = ""
    if revisiones:
        detalle = "; ".join(
            f"{p}: {fmt(viejo, d.get('decimales', 0))} → {fmt(nuevo, d.get('decimales', 0))}"
            for p, viejo, nuevo in revisiones[:6]
        )
        nota = (f"En esta captura la EIA revisó {len(revisiones)} "
                f"{'valor' if len(revisiones) == 1 else 'valores'} ya publicados ({detalle}"
                f"{'; ...' if len(revisiones) > 6 else ''}).")
    return [
        ("heading", {"title": d["nombre"]}),
        ("chart", {
            "chart_type": "line",
            "title": d["corto"],
            "subtitle": f"{d.get('unidad', '')} — de {desde} a {hasta}",
            "table": tabla(recorte),
            "series_names": d["corto"],
            "options": {"y_title": unidad_corta},
            "color": d.get("color", "navy"),
            "colors": [d.get("color", "navy")],
            "source": d.get("fuente", "EIA"),
            "note": nota,
        }),
        ("paragraph", {"text": texto_serie(stats, d)}),
    ]


def bloques_publicaciones(publicaciones):
    """La sección de material de referencia: lo que la EIA escribió.

    Va citado, con la fecha y el link de cada cosa, y con un aviso de que está
    en inglés y es de ellos. Dos razones para que sea cita y no texto corrido:
    el análisis del Instituto lo escribe el equipo, y el lector tiene que
    poder ver de un vistazo qué es nuestro y qué no."""
    if not publicaciones:
        return []
    bloques = [
        ("heading", {"title": "Qué publicó la EIA"}),
        ("callout", {
            "color": "navy",
            "text": ("**Material de referencia, no texto del Instituto.** Lo que sigue son "
                     "citas de publicaciones de la EIA, en inglés y con el link a cada una, "
                     "para quien escriba el análisis. Si algo de esto va al post publicado, "
                     "va como cita con su fuente, o traducido y reescrito por el equipo."),
        }),
    ]
    # Un bloque por publicación, no uno con todas: así en el editor se borran
    # las que no sirven sin tocar el texto de las demás.
    for p in publicaciones:
        ficha = " · ".join(x for x in (p.get("fuente_nombre", "EIA"), p.get("fecha")) if x)
        bloques.append(("paragraph", {
            "text": f'**{p["titulo"]}** ({ficha}): "{p["resumen"]}" '
                    f'[Ver en la EIA]({p["link"]})',
        }))
    return bloques


def armar_bloques(resultados, hoy=None, con_fallas=(), publicaciones=()):
    """Todos los bloques del informe. `resultados` = lista de dicts con
    clave/definicion/datos/stats/revisiones (los arma semanal.py)."""
    hoy = hoy or datetime.now(timezone.utc) - timedelta(hours=3)
    bloques = [
        ("callout", {
            "color": "orange",
            "text": ("**Borrador automático — no publicado.** Lo armó el script "
                     "`datos/semanal.py` con los datos que la EIA tenía publicados al "
                     f"{fecha_larga(hoy)}. Los números y los gráficos ya están; falta la "
                     "lectura del equipo. Antes de publicar: revisar que los datos cierren, "
                     "escribir el análisis, y borrar este aviso."),
        }),
        ("paragraph", {
            "text": ("Seguimiento semanal de las series de la **U.S. Energy Information "
                     "Administration (EIA)** que el Instituto monitorea para el mercado "
                     "internacional de hidrocarburos. Cada serie se baja de la API pública de "
                     "la EIA, se guarda en la base histórica del Instituto y se compara contra "
                     "el período anterior, contra el mismo período del año pasado y contra el "
                     "acumulado del año. Son datos de **Estados Unidos**: para Argentina las "
                     "fuentes son la Secretaría de Energía, el ENARGAS y el INDEC."),
        }),
    ]
    for r in resultados:
        bloques += bloques_de_serie(r["clave"], r["definicion"], r["datos"],
                                   r["stats"], r["revisiones"])

    bloques += bloques_publicaciones(publicaciones)

    revisadas = [r for r in resultados if r["revisiones"]]
    bloques.append(("heading", {"title": "Cómo se armó este informe"}))
    detalle_fuentes = " ".join(
        f"*{r['definicion']['corto']}*: {r['definicion'].get('fuente', '')} "
        f"({r['stats']['periodos']} períodos guardados, desde {r['stats']['primer_periodo']})."
        for r in resultados
    )
    bloques.append(("paragraph", {
        "text": ("Los datos se bajan de la API v2 de la EIA (`api.eia.gov`) y quedan guardados "
                 "en la base histórica del Instituto, un archivo propio independiente de la "
                 "EIA: si mañana cambia una ruta o se cae el servicio, la serie capturada sigue "
                 "estando. En cada corrida se compara lo que llega con lo guardado, así que las "
                 "revisiones de datos ya publicados quedan registradas. " + detalle_fuentes),
    }))
    if revisadas:
        bloques.append(("callout", {
            "color": "maroon",
            "text": ("**Revisiones detectadas en esta captura.** " + " ".join(
                f"{r['definicion']['corto']}: {len(r['revisiones'])} "
                f"{'valor' if len(r['revisiones']) == 1 else 'valores'} corregidos."
                for r in revisadas) +
                " El detalle está en la nota al pie de cada gráfico. Es normal en series "
                "semanales: la EIA ajusta los datos preliminares. Vale la pena mirarlo antes "
                "de citar un número de las últimas semanas."),
        }))
    if con_fallas:
        bloques.append(("callout", {
            "color": "maroon",
            "text": ("**Series que no se pudieron actualizar en esta corrida.** " +
                     " ".join(f"{clave}: {motivo}" for clave, motivo in con_fallas) +
                     " El informe muestra lo último que había en la base histórica."),
        }))
    return bloques


# ---------------------------------------------------------------------------
# 3. Escribir el borrador en la base del blog
# ---------------------------------------------------------------------------

def armar_borrador(bloques, titulo, slug_base, eyebrow="", dek="", accent="navy", db_path=None):
    """Crea (o reemplaza, si ya existe el borrador de hoy) el post.

    Devuelve (post_id, slug, "creado"|"actualizado").
    Nunca toca un post ya publicado: si el slug de hoy quedó publicado, crea
    uno nuevo con slug numerado.
    """
    import app  # importa DB_PATH, init_db() y los helpers del editor

    ruta = db_path or app.DB_PATH
    db = sqlite3.connect(ruta)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    ahora = datetime.now(timezone.utc).isoformat()

    existente = db.execute(
        "SELECT id, slug, status, published_at FROM posts WHERE slug = ?", (slug_base,)
    ).fetchone()
    if existente and not existente["published_at"] and existente["status"] != "published":
        post_id, slug, accion = existente["id"], existente["slug"], "actualizado"
        db.execute(
            "UPDATE posts SET title=?, eyebrow=?, dek=?, accent=?, updated_at=? WHERE id=?",
            (titulo, eyebrow, dek, accent, ahora, post_id),
        )
        db.execute("DELETE FROM blocks WHERE post_id = ?", (post_id,))
    else:
        slug = app.unique_slug(db, slug_base)
        cur = db.execute(
            "INSERT INTO posts (slug, title, eyebrow, dek, status, accent, author, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'draft', ?, '', ?, ?)",
            (slug, titulo, eyebrow, dek, accent, ahora, ahora),
        )
        post_id, accion = cur.lastrowid, "creado"

    for posicion, (tipo, form) in enumerate(bloques):
        if tipo not in app.BLOCK_TYPES:
            raise ValueError(f"Tipo de bloque inválido: {tipo}")
        data = app.block_data_from_form(tipo, form)
        db.execute("INSERT INTO blocks (post_id, position, type, data) VALUES (?, ?, ?, ?)",
                   (post_id, posicion, tipo, json.dumps(data, ensure_ascii=False)))
    db.commit()
    db.close()
    return post_id, slug, accion
