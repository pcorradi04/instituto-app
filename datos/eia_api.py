"""
Cliente mínimo de la API v2 de la EIA (U.S. Energy Information Administration)
=============================================================================
Solo biblioteca estándar: `urllib` + `json`. No agrega dependencias al
proyecto (importante: el servidor del blog corre con el mismo venv).

Qué es la API de la EIA, en dos líneas: la EIA publica miles de series de
tiempo (producción, exportaciones, precios, stocks...) organizadas en
"rutas" (`petroleum/move/wkly`, `natural-gas/move/expc`, ...). Cada serie
dentro de una ruta se identifica con un código histórico, el mismo que
aparece en las páginas del sitio: por ejemplo
`W_EPLLPZ_EEX_NUS-Z00_MBBLD` = exportaciones semanales de propano/propileno
de Estados Unidos, en miles de barriles por día. La API devuelve JSON y
pide una clave gratuita (una línea en el .env: `EIA_API_KEY=...`).

Se usa así:

    from datos import eia_api
    obs = eia_api.serie("petroleum/move/wkly", "W_EPLLPZ_EEX_NUS-Z00_MBBLD",
                        "weekly", desde="2015-01-01")
    # -> [{"period": "2015-01-02", "value": 601.0, "unit": "MBBL/D"}, ...]

Para explorar qué hay en una ruta (sirve para agregar series nuevas):

    python datos/semanal.py --explorar natural-gas/move/expc
    python datos/semanal.py --explorar natural-gas/move/expc --faceta series
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.eia.gov/v2"
PAGINA = 5000          # máximo de filas que devuelve la API por pedido
TIMEOUT = 60


class EIAError(RuntimeError):
    """Cualquier problema hablando con la API: clave, red, ruta inexistente."""


def api_key():
    """La clave del .env. Se saca gratis en https://www.eia.gov/opendata/register.php"""
    clave = (os.environ.get("EIA_API_KEY") or "").strip()
    if not clave:
        raise EIAError(
            "Falta la clave de la EIA. Pedila gratis en "
            "https://www.eia.gov/opendata/register.php (llega por mail en el momento) "
            'y agregá la línea "EIA_API_KEY=tu-clave" al archivo .env del proyecto.'
        )
    return clave


def _tapar(texto, clave):
    """Nunca escribir la clave en un mensaje de error ni en un log."""
    return texto.replace(clave, "***") if clave else texto


def _get(ruta, params, intentos=3):
    """Un pedido a la API. Devuelve el objeto "response" del JSON."""
    clave = api_key()
    query = urllib.parse.urlencode([("api_key", clave)] + list(params))
    url = f"{BASE}/{ruta.strip('/')}/?{query}"
    publico = _tapar(url, clave)
    pedido = urllib.request.Request(url, headers={
        # La EIA bloquea pedidos sin User-Agent identificable.
        "User-Agent": "instituto-energia-austral/1.0 (blog.ieaustral.com)",
        "Accept": "application/json",
    })
    for intento in range(1, intentos + 1):
        try:
            with urllib.request.urlopen(pedido, timeout=TIMEOUT) as r:
                cuerpo = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            detalle = _tapar(e.read().decode("utf-8", "replace")[:400], clave)
            # 429 = demasiados pedidos; 5xx = problema del lado de la EIA.
            # Los dos se reintentan; 400/403 (ruta mal escrita, clave inválida) no.
            if e.code in (429, 500, 502, 503, 504) and intento < intentos:
                time.sleep(3 * intento)
                continue
            raise EIAError(f"La EIA respondió {e.code} a {publico}\n{detalle}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if intento < intentos:
                time.sleep(3 * intento)
                continue
            raise EIAError(f"No se pudo conectar con la EIA ({e}). ¿Hay internet?") from None
        try:
            payload = json.loads(cuerpo)
        except json.JSONDecodeError:
            raise EIAError(f"La EIA devolvió algo que no es JSON en {publico}: {cuerpo[:200]}") from None
        if isinstance(payload.get("error"), dict):
            err = payload["error"]
            raise EIAError(f"La EIA rechazó el pedido ({err.get('code', '?')}): {err.get('message', '')}")
        if "error" in payload and payload["error"]:
            raise EIAError(f"La EIA rechazó el pedido: {_tapar(str(payload['error'])[:300], clave)}")
        return payload.get("response") or {}
    raise EIAError(f"No se pudo leer {publico}")  # inalcanzable, por prolijidad


def serie(ruta, series_id, frecuencia, desde=None, hasta=None, maximo=20000):
    """Una serie de tiempo completa, del período más viejo al más nuevo.

    ruta       ej. "petroleum/move/wkly"
    series_id  el código histórico, ej. "W_EPLLPZ_EEX_NUS-Z00_MBBLD"
    frecuencia "weekly" / "monthly" / "annual" (la que admita la ruta)
    desde/hasta  "AAAA-MM-DD" o "AAAA-MM" según la frecuencia (opcionales)

    Devuelve [{"period", "value", "unit"}], sin los períodos sin dato.
    """
    base = [
        ("frequency", frecuencia),
        ("data[0]", "value"),
        ("facets[series][]", series_id),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "asc"),
        ("length", str(PAGINA)),
    ]
    if desde:
        base.append(("start", desde))
    if hasta:
        base.append(("end", hasta))

    filas, offset = [], 0
    while True:
        resp = _get(f"{ruta}/data", base + [("offset", str(offset))])
        lote = resp.get("data") or []
        filas.extend(lote)
        total = int(resp.get("total") or len(filas))
        offset += len(lote)
        if not lote or offset >= min(total, maximo):
            break

    obs = []
    for f in filas:
        periodo = str(f.get("period") or "").strip()
        valor = f.get("value")
        if not periodo or valor in (None, "", "NA", "--"):
            continue
        try:
            obs.append({"period": periodo, "value": float(valor),
                        "unit": str(f.get("units") or f.get("unit") or "").strip()})
        except (TypeError, ValueError):
            continue
    obs.sort(key=lambda o: o["period"])
    if not obs:
        raise EIAError(
            f'La EIA no devolvió datos para la serie "{series_id}" en la ruta "{ruta}" '
            f'con frecuencia "{frecuencia}". Revisá el código con: '
            f"python datos/semanal.py --explorar {ruta} --faceta series"
        )
    return obs


# ---------------------------------------------------------------------------
# Exploración (para agregar series nuevas sin adivinar)
# ---------------------------------------------------------------------------

def metadatos(ruta):
    """Qué tiene una ruta: sub-rutas, frecuencias, columnas de datos y facetas."""
    return _get(ruta, [])


def valores_faceta(ruta, faceta, contiene=""):
    """Los valores posibles de una faceta (ej. todos los códigos de serie de
    una ruta). `contiene` filtra por texto en el código o en el nombre."""
    resp = _get(f"{ruta}/facet/{faceta}", [])
    valores = resp.get("facets") or []
    if contiene:
        c = contiene.lower()
        valores = [v for v in valores
                   if c in str(v.get("id", "")).lower() or c in str(v.get("name", "")).lower()]
    return valores
