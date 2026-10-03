"""
Lo que la EIA *escribe*, no lo que mide
=======================================
Además de las series de números, la EIA publica textos: artículos cortos y
un informe mensual de perspectivas. Este módulo los trae para que el borrador
los incluya como **material de referencia** para quien escribe — citado, con
fecha y con el link, nunca como texto del Instituto.

Dos fuentes, elegidas después de revisar cuáles siguen vivas (3 oct 2026):

* **Today in Energy** — artículos cortos, casi diarios, con un resumen de dos
  líneas. Tiene RSS, que es un formato pensado para que lo lea un programa:
  no hay que adivinar nada de la página. Al día.
* **Short-Term Energy Outlook (STEO)** — el informe mensual de perspectivas.
  No tiene RSS; se leen los párrafos de "highlights" de su portada. Al día
  (se publica alrededor del 6 de cada mes).

Dos que NO se usan, y conviene que quede escrito para no volver a intentarlo
sin mirar: el **Natural Gas Weekly Update** está congelado desde enero de 2026
y **This Week in Petroleum**, desde octubre de 2025. Las páginas siguen
online, así que un script que las lea devolvería texto viejo con cara de
nuevo — exactamente el problema de "información desactualizada en el
dashboard" que marcó Luciano. Si alguna vez vuelven a publicarse, agregarlas
acá es una entrada más en FUENTES.

Nota de derechos: la EIA es una agencia del gobierno de Estados Unidos y sus
textos son de dominio público, así que citarlos no tiene problema legal. La
razón de citarlos cortos, con comillas y con link es editorial: el análisis
del Instituto lo escribe el equipo, y el lector tiene que poder ver de un
vistazo qué es cita y qué es nuestro.
"""

import html
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

AGENTE = "instituto-energia-austral/1.0 (blog.ieaustral.com)"
TIMEOUT = 30

FUENTES = {
    "tie": {
        "nombre": "Today in Energy",
        "descripcion": "Artículos cortos de la EIA sobre datos y tendencias (casi diarios).",
        "url": "https://www.eia.gov/rss/todayinenergy.xml",
        "pagina": "https://www.eia.gov/todayinenergy/",
        "tipo": "rss",
        "maximo": 6,
    },
    "steo": {
        "nombre": "Short-Term Energy Outlook",
        "descripcion": "El informe mensual de perspectivas de la EIA (precios, producción, inventarios).",
        "url": "https://www.eia.gov/outlooks/steo/",
        "pagina": "https://www.eia.gov/outlooks/steo/",
        "tipo": "steo",
        "maximo": 4,
    },
}
ORDEN = ["tie", "steo"]

# Para ordenar primero lo que le interesa al Instituto. No descarta nada: solo
# pone arriba lo que habla de hidrocarburos.
PALABRAS = ("oil", "crude", "petroleum", "gas", "lng", "propane", "gasoline",
            "diesel", "distillate", "refinery", "export", "import", "opec", "shale")


class PublicacionesError(RuntimeError):
    pass


def _bajar(url):
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
            return r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        raise PublicacionesError(f"No se pudo leer {url}: {e}") from None


def _texto_plano(fragmento):
    """HTML -> texto legible, sin etiquetas ni espacios de más."""
    sin_scripts = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", fragmento)
    texto = html.unescape(re.sub(r"<[^>]+>", " ", sin_scripts))
    return re.sub(r"\s+", " ", texto).strip()


def recortar(texto, largo=320):
    """Corta en palabra entera y marca el corte, para que la cita no mienta
    sobre dónde termina."""
    texto = texto.strip()
    if len(texto) <= largo:
        return texto
    corte = texto[:largo].rsplit(" ", 1)[0].rstrip(" ,;:.")
    return corte + "…"


MESES_EN = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def _fecha(crudo):
    """A AAAA-MM-DD, desde los dos formatos en que la EIA escribe fechas:
    "Fri, 02 Oct 2026 09:00:00 EST" (RSS) y "September 9, 2026" (STEO).
    Si no se entiende ninguno, se devuelve el texto como vino: mejor eso que
    inventar una fecha."""
    crudo = str(crudo or "").strip()
    try:
        return parsedate_to_datetime(crudo).date().isoformat()
    except (TypeError, ValueError):
        pass
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})", crudo)     # 9 Sep 2026
    if m:
        mes = MESES_EN.get(m.group(2).lower())
        if mes:
            return f"{m.group(3)}-{mes:02d}-{int(m.group(1)):02d}"
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", crudo)   # September 9, 2026
    if m:
        mes = MESES_EN.get(m.group(1).lower())
        if mes:
            return f"{m.group(3)}-{mes:02d}-{int(m.group(2)):02d}"
    return crudo[:40]


def bajar_rss(fuente):
    """Los últimos artículos de un feed RSS."""
    try:
        raiz = ET.fromstring(_bajar(fuente["url"]))
    except ET.ParseError as e:
        raise PublicacionesError(f"El feed de {fuente['nombre']} no se pudo leer: {e}") from None
    salida = []
    for item in raiz.iter("item"):
        titulo = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not titulo or not link.startswith("http"):
            continue
        salida.append({
            "titulo": _texto_plano(titulo),
            "link": link,
            "fecha": _fecha(item.findtext("pubDate")),
            "resumen": recortar(_texto_plano(item.findtext("description") or "")),
        })
    if not salida:
        raise PublicacionesError(f"El feed de {fuente['nombre']} vino vacío.")
    # Primero lo que habla de hidrocarburos, después el resto, sin perder el
    # orden cronológico dentro de cada grupo.
    def relevante(p):
        t = (p["titulo"] + " " + p["resumen"]).lower()
        return 0 if any(w in t for w in PALABRAS) else 1
    return sorted(salida, key=relevante)[:fuente.get("maximo", 6)]


def bajar_steo(fuente):
    """Los "highlights" de la portada del Short-Term Energy Outlook, con su
    fecha de publicación (que es el dato clave: dice si está al día).

    En la página son una lista debajo del encabezado "Forecast overview", y
    cada punto arranca con su tema en negrita:
        <ul><li><strong>Global oil prices. </strong>Global oil prices rose...
    Se busca por ese encabezado y no por posición, así un cambio de diseño
    deja la sección afuera (con aviso) en vez de meter texto equivocado."""
    pagina = _bajar(fuente["url"]).decode("utf-8", "replace")
    m = re.search(r"Release Date:\s*([A-Za-z]+ \d{1,2},? \d{4})", _texto_plano(pagina[:40000]))
    fecha = _fecha(m.group(1)) if m else ""
    sin_scripts = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", pagina)
    encabezado = re.search(r"(?is)<h[1-3][^>]*>[^<]*(forecast overview|highlights)[^<]*</h[1-3]>",
                           sin_scripts)
    cuerpo = sin_scripts[encabezado.end():] if encabezado else ""
    salida = []
    for bruto in re.findall(r"(?is)<li[^>]*>(.*?)</li>", cuerpo):
        negrita = re.search(r"(?is)<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>", bruto)
        if not negrita:
            continue
        tema = _texto_plano(negrita.group(1)).strip(" .:")
        # El cuerpo sin el tema adelante: si no, la cita queda "Global oil
        # prices. Global oil prices rose...".
        texto = _texto_plano(bruto[negrita.end():])
        if len(texto) < 120 or not tema:
            continue
        salida.append({
            "titulo": tema[:70],
            "link": fuente["pagina"],
            "fecha": fecha,
            "resumen": recortar(texto, 420),
        })
        if len(salida) >= fuente.get("maximo", 4):
            break
    if not salida:
        raise PublicacionesError(
            "No se encontraron los highlights del STEO: puede que haya cambiado la página "
            f"({fuente['pagina']}).")
    return salida


def traer(claves=None):
    """Baja las fuentes pedidas. Devuelve (publicaciones, fallas); una fuente
    caída nunca rompe el informe, solo queda anotada."""
    publicaciones, fallas = [], []
    for clave in (claves or ORDEN):
        fuente = FUENTES.get(clave)
        if not fuente:
            fallas.append((clave, "fuente desconocida"))
            continue
        try:
            items = bajar_rss(fuente) if fuente["tipo"] == "rss" else bajar_steo(fuente)
        except PublicacionesError as e:
            fallas.append((clave, str(e)))
            continue
        for item in items:
            item["fuente"] = clave
            item["fuente_nombre"] = fuente["nombre"]
            publicaciones.append(item)
    return publicaciones, fallas


# ---------------------------------------------------------------------------
# Guardado (para no repetir en dos informes seguidos lo mismo)
# ---------------------------------------------------------------------------

def clave_de(p):
    """Qué hace única a una publicación. No sirve el link: los cuatro puntos
    del STEO salen de la misma página y se pisarían entre sí."""
    return f"{p.get('fuente', '')}|{p.get('fecha', '')}|{p.get('titulo', '')}"[:300]


def init(db):
    # Migración: la primera versión usaba el link como clave. Esta tabla es
    # solo una memoria de lo ya visto (se vuelve a llenar en la corrida
    # siguiente), así que se rehace y listo.
    cols = {r[1] for r in db.execute("PRAGMA table_info(publicaciones)")}
    if cols and "clave" not in cols:
        db.execute("DROP TABLE publicaciones")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS publicaciones (
        clave TEXT PRIMARY KEY,
        fuente TEXT NOT NULL,
        titulo TEXT NOT NULL,
        fecha TEXT NOT NULL DEFAULT '',
        resumen TEXT NOT NULL DEFAULT '',
        link TEXT NOT NULL DEFAULT '',
        capturada TEXT NOT NULL
    );
    """)
    db.commit()


def guardar(db, publicaciones):
    """Guarda las que no estaban y devuelve esas (las nuevas desde la última
    corrida), para poder decir en el log cuánto hay de nuevo."""
    init(db)
    ahora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    nuevas = []
    for p in publicaciones:
        clave = clave_de(p)
        ya = db.execute("SELECT 1 FROM publicaciones WHERE clave = ?", (clave,)).fetchone()
        if not ya:
            nuevas.append(p)
        db.execute(
            "INSERT INTO publicaciones (clave, fuente, titulo, fecha, resumen, link, capturada) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(clave) DO UPDATE SET "
            "titulo=excluded.titulo, fecha=excluded.fecha, resumen=excluded.resumen, "
            "link=excluded.link",
            (clave, p["fuente"], p["titulo"], p["fecha"], p["resumen"], p["link"], ahora),
        )
    db.commit()
    return nuevas
