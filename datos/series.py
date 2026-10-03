"""
Qué series de la EIA seguimos
=============================
Este archivo es el único lugar donde se define QUÉ datos se capturan. Para
sumar una serie nueva se agrega una entrada acá y nada más: la captura, la
base histórica y el informe la toman solas.

Cada entrada:

  grupo         con qué otras series se muestra junta en el panel
                ("Exportaciones — Estados Unidos"), que es lo que se elige al
                apretar el botón de traer datos
  nombre        título de la sección en el informe
  corto         nombre de la serie en los gráficos y en la base
  candidatos    [(ruta, código de serie)] a probar en orden. Se usa más de uno
                porque la EIA a veces publica la misma serie en dos rutas; se
                queda con el primero que devuelva datos.
  frecuencia    "weekly" | "monthly" | "annual"
  unidad        cómo se lee en el texto ("miles de barriles por día")
  unidad_corta  cómo se rotula el eje del gráfico ("mbd")
  agregacion    "promedio" si la serie es un caudal (barriles POR DÍA) o
                "suma" si es un volumen del período (pies cúbicos del mes).
                Define cómo se comparan los acumulados del año.
  decimales     decimales al escribir los números
  desde         primer período a capturar la primera vez
  periodos_grafico  cuántos períodos muestra el gráfico del informe
  color         clave de la paleta de static/charts.js
  fuente        línea "Fuente:" al pie del gráfico
  pagina        link a la página de la EIA, para que el lector verifique
  activa        False la deja definida pero fuera del informe semanal

Nota sobre los códigos de serie: son los que usa la propia EIA en sus
páginas (los que se ven en el "API Browser" y en las URLs del tipo
LeafHandler.ashx?...&s=W_EPLLPZ_EEX_NUS-Z00_MBBLD). Si alguno cambia o no
devuelve datos, el script lo dice y se busca el nuevo con:

    python datos/semanal.py --explorar natural-gas/move/expc --faceta series
"""

SERIES = {
    # ---- 1. Propano: lo que pidió Luciano para arrancar -------------------
    "propano_exp_usa": {
        "grupo": "Exportaciones — Estados Unidos",
        "nombre": "Exportaciones de propano y propileno de Estados Unidos",
        "corto": "Propano/propileno exportado (EE.UU.)",
        "candidatos": [("petroleum/move/wkly", "W_EPLLPZ_EEX_NUS-Z00_MBBLD")],
        "frecuencia": "weekly",
        "unidad": "miles de barriles por día",
        "unidad_corta": "mbd",
        "agregacion": "promedio",
        "decimales": 0,
        "desde": "2010-01-01",
        "periodos_grafico": 104,
        "color": "navy",
        "fuente": "EIA — Weekly U.S. Exports of Propane and Propylene (W_EPLLPZ_EEX_NUS-Z00_MBBLD)",
        "pagina": "https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=W_EPLLPZ_EEX_NUS-Z00_MBBLD&f=W",
        "activa": True,
    },

    # ---- 2. Gas natural: el total exportado por Estados Unidos -----------
    "gas_exp_usa": {
        "grupo": "Exportaciones — Estados Unidos",
        "nombre": "Exportaciones de gas natural de Estados Unidos",
        "corto": "Gas natural exportado (EE.UU.)",
        "candidatos": [
            ("natural-gas/move/expc", "N9130US2"),
            ("natural-gas/sum/lsum", "N9130US2"),
        ],
        "frecuencia": "monthly",
        "unidad": "millones de pies cúbicos",
        "unidad_corta": "MMpc",
        "agregacion": "suma",
        "decimales": 0,
        "desde": "2010-01",
        "periodos_grafico": 60,
        "color": "navy",
        "fuente": "EIA — Natural Gas Exports by Country (N9130US2)",
        "pagina": "https://www.eia.gov/opendata/browser/natural-gas/move/expc",
        "activa": True,
    },

    # ---- 3. GNL: la parte del gas que sale licuada por barco -------------
    "gnl_exp_usa": {
        "grupo": "Exportaciones — Estados Unidos",
        "nombre": "Exportaciones de gas natural licuado de Estados Unidos",
        "corto": "GNL exportado (EE.UU.)",
        "candidatos": [
            ("natural-gas/move/expc", "N9133US2"),
            ("natural-gas/sum/lsum", "N9133US2"),
        ],
        "frecuencia": "monthly",
        "unidad": "millones de pies cúbicos",
        "unidad_corta": "MMpc",
        "agregacion": "suma",
        "decimales": 0,
        "desde": "2010-01",
        "periodos_grafico": 60,
        "color": "blue",
        "fuente": "EIA — U.S. Natural Gas Exports by LNG (N9133US2)",
        "pagina": "https://www.eia.gov/opendata/browser/natural-gas/move/expc",
        "activa": True,
    },

    # ---- 4. Producción de crudo: el otro link que mandó Luciano ----------
    "crudo_prod_usa": {
        "grupo": "Producción — Estados Unidos",
        "nombre": "Producción de petróleo crudo de Estados Unidos",
        "corto": "Crudo producido (EE.UU.)",
        "candidatos": [
            ("petroleum/crd/crpdn", "MCRFPUS2"),
            ("petroleum/sum/sndw", "MCRFPUS2"),
        ],
        "frecuencia": "monthly",
        "unidad": "miles de barriles por día",
        "unidad_corta": "mbd",
        "agregacion": "promedio",
        "decimales": 0,
        "desde": "2010-01",
        "periodos_grafico": 60,
        "color": "orange",
        "fuente": "EIA — Crude Oil Production (MCRFPUS2)",
        "pagina": "https://www.eia.gov/opendata/browser/petroleum/crd/crpdn",
        "activa": True,
    },
}

# Orden en que aparecen en el informe.
ORDEN = ["propano_exp_usa", "gas_exp_usa", "gnl_exp_usa", "crudo_prod_usa"]


def activas(claves=None):
    """Las series que entran en el informe. `claves` (lista) limita a esas."""
    elegidas = claves or ORDEN
    salida = []
    for k in elegidas:
        d = SERIES.get(k)
        if not d:
            raise KeyError(f'No existe la serie "{k}". Las que hay: {", ".join(ORDEN)}')
        if claves or d.get("activa", True):
            salida.append((k, d))
    return salida
