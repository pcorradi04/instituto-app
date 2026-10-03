"""
La base histórica propia ("un espacio nuestro")
===============================================
Todo lo que se baja de la EIA queda guardado acá, en un SQLite aparte del
blog (`datos/datos.db` por defecto). Dos razones:

1. **Independencia**: si mañana la EIA cambia una ruta, se cae la API o
   deja de publicar una serie, el histórico ya capturado sigue siendo
   nuestro y los informes se pueden seguir armando.
2. **Auditoría**: la EIA *revisa* datos ya publicados (es normal en
   estadística oficial, sobre todo en las series semanales). Como se guarda
   el valor anterior y la fecha en que cambió, el script puede avisar
   "el dato de tal período cambió de X a Y", que es exactamente el tipo de
   control que el Instituto quiere poder mostrar.

Tres tablas:
  series         una fila por serie seguida (código, ruta, unidad, última captura)
  observaciones  una fila por período y serie (valor actual + cuántas veces cambió)
  revisiones     el registro de cada cambio de un valor ya publicado
  capturas       log de cada corrida (para saber si el automático dejó de correr)
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DATOS = os.environ.get("DATOS_DB_PATH") or os.path.join(BASE_DIR, "datos.db")


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conectar(ruta=None):
    ruta = ruta or DB_DATOS
    carpeta = os.path.dirname(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)
    db = sqlite3.connect(ruta)
    db.row_factory = sqlite3.Row
    db.executescript("""
    CREATE TABLE IF NOT EXISTS series (
        clave TEXT PRIMARY KEY,
        nombre TEXT NOT NULL DEFAULT '',
        ruta TEXT NOT NULL DEFAULT '',
        series_id TEXT NOT NULL DEFAULT '',
        frecuencia TEXT NOT NULL DEFAULT '',
        unidad TEXT NOT NULL DEFAULT '',
        ultima_captura TEXT
    );
    CREATE TABLE IF NOT EXISTS observaciones (
        clave TEXT NOT NULL,
        periodo TEXT NOT NULL,
        valor REAL NOT NULL,
        unidad TEXT NOT NULL DEFAULT '',
        primera_vez TEXT NOT NULL,       -- cuándo lo vimos por primera vez
        actualizado TEXT NOT NULL,       -- cuándo cambió por última vez
        cambios INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (clave, periodo)
    );
    CREATE TABLE IF NOT EXISTS revisiones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clave TEXT NOT NULL,
        periodo TEXT NOT NULL,
        valor_anterior REAL NOT NULL,
        valor_nuevo REAL NOT NULL,
        detectada TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS ix_revisiones_fecha ON revisiones(detectada);
    -- Una fila por vez que alguien aprieta "traer datos" en el panel (o que
    -- corre el automático): deja ver el avance mientras trabaja y qué pasó
    -- después. Vive en la base (no en memoria del proceso) para que la página
    -- lo pueda leer aunque el servidor tenga varios workers.
    CREATE TABLE IF NOT EXISTS tareas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        estado TEXT NOT NULL DEFAULT 'trabajando',   -- trabajando | listo | error
        series TEXT NOT NULL DEFAULT '',             -- claves separadas por coma
        quien TEXT NOT NULL DEFAULT '',              -- iniciales de quien lo pidió
        paso TEXT NOT NULL DEFAULT '',               -- "2 de 4: gas_exp_usa"
        mensaje TEXT NOT NULL DEFAULT '',
        post_id INTEGER,
        inicio TEXT NOT NULL,
        fin TEXT
    );
    CREATE TABLE IF NOT EXISTS capturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        clave TEXT NOT NULL,
        ts TEXT NOT NULL,
        filas INTEGER NOT NULL DEFAULT 0,
        nuevas INTEGER NOT NULL DEFAULT 0,
        revisadas INTEGER NOT NULL DEFAULT 0,
        error TEXT NOT NULL DEFAULT ''
    );
    """)
    db.commit()
    return db


def guardar(db, clave, definicion, series_id, ruta, observaciones):
    """Mete en la base lo que devolvió la API. No borra nada: los períodos
    que la EIA dejó de publicar quedan como estaban.

    Devuelve {"filas", "nuevas", "revisadas", "revisiones": [(periodo, viejo, nuevo)]}
    """
    ts = ahora()
    unidad_api = observaciones[0]["unit"] if observaciones else ""
    db.execute(
        "INSERT INTO series (clave, nombre, ruta, series_id, frecuencia, unidad, ultima_captura) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(clave) DO UPDATE SET nombre=excluded.nombre, ruta=excluded.ruta, "
        "series_id=excluded.series_id, frecuencia=excluded.frecuencia, "
        "unidad=excluded.unidad, ultima_captura=excluded.ultima_captura",
        (clave, definicion.get("nombre", ""), ruta, series_id,
         definicion.get("frecuencia", ""), unidad_api or definicion.get("unidad", ""), ts),
    )

    previos = {r["periodo"]: (r["valor"], r["cambios"])
               for r in db.execute("SELECT periodo, valor, cambios FROM observaciones WHERE clave = ?", (clave,))}
    nuevas, revisiones = 0, []
    for o in observaciones:
        periodo, valor = o["period"], float(o["value"])
        if periodo not in previos:
            db.execute(
                "INSERT INTO observaciones (clave, periodo, valor, unidad, primera_vez, actualizado, cambios) "
                "VALUES (?, ?, ?, ?, ?, ?, 0)",
                (clave, periodo, valor, o.get("unit", ""), ts, ts),
            )
            nuevas += 1
            continue
        viejo, cambios = previos[periodo]
        # Tolerancia relativa: la API a veces redondea distinto el mismo dato.
        if abs(valor - viejo) > max(abs(viejo), 1.0) * 1e-9:
            db.execute(
                "UPDATE observaciones SET valor = ?, unidad = ?, actualizado = ?, cambios = ? "
                "WHERE clave = ? AND periodo = ?",
                (valor, o.get("unit", ""), ts, cambios + 1, clave, periodo),
            )
            db.execute(
                "INSERT INTO revisiones (clave, periodo, valor_anterior, valor_nuevo, detectada) "
                "VALUES (?, ?, ?, ?, ?)",
                (clave, periodo, viejo, valor, ts),
            )
            revisiones.append((periodo, viejo, valor))

    db.execute(
        "INSERT INTO capturas (clave, ts, filas, nuevas, revisadas) VALUES (?, ?, ?, ?, ?)",
        (clave, ts, len(observaciones), nuevas, len(revisiones)),
    )
    db.commit()
    return {"filas": len(observaciones), "nuevas": nuevas,
            "revisadas": len(revisiones), "revisiones": revisiones}


def anotar_error(db, clave, mensaje):
    db.execute("INSERT INTO capturas (clave, ts, error) VALUES (?, ?, ?)",
               (clave, ahora(), str(mensaje)[:500]))
    db.commit()


def historia(db, clave, ultimos=None):
    """[(periodo, valor)] del más viejo al más nuevo. `ultimos` recorta la cola."""
    filas = db.execute(
        "SELECT periodo, valor FROM observaciones WHERE clave = ? ORDER BY periodo", (clave,)
    ).fetchall()
    datos = [(r["periodo"], r["valor"]) for r in filas]
    return datos[-ultimos:] if ultimos else datos


def revisiones_de(db, clave, desde_ts):
    """Las revisiones detectadas en esta corrida (o desde una fecha)."""
    filas = db.execute(
        "SELECT periodo, valor_anterior, valor_nuevo FROM revisiones "
        "WHERE clave = ? AND detectada >= ? ORDER BY periodo", (clave, desde_ts)
    ).fetchall()
    return [(r["periodo"], r["valor_anterior"], r["valor_nuevo"]) for r in filas]


def resumen(db):
    """Para el comando --estado: qué hay guardado de cada serie."""
    return db.execute("""
        SELECT s.clave, s.nombre, s.series_id, s.frecuencia, s.ultima_captura,
               COUNT(o.periodo) AS periodos, MIN(o.periodo) AS desde, MAX(o.periodo) AS hasta,
               (SELECT COUNT(*) FROM revisiones r WHERE r.clave = s.clave) AS revisiones
        FROM series s LEFT JOIN observaciones o ON o.clave = s.clave
        GROUP BY s.clave ORDER BY s.clave
    """).fetchall()


# ---------------------------------------------------------------------------
# Tareas: el botón "traer datos" del panel
# ---------------------------------------------------------------------------

def tarea_crear(db, claves, quien=""):
    cur = db.execute(
        "INSERT INTO tareas (estado, series, quien, paso, inicio) VALUES ('trabajando', ?, ?, ?, ?)",
        (",".join(claves), quien, f"0 de {len(claves)}", ahora()),
    )
    db.commit()
    return cur.lastrowid


def tarea_paso(db, tarea_id, paso):
    if not tarea_id:
        return
    db.execute("UPDATE tareas SET paso = ? WHERE id = ?", (str(paso)[:200], tarea_id))
    db.commit()


def tarea_fin(db, tarea_id, estado, mensaje="", post_id=None):
    if not tarea_id:
        return
    db.execute("UPDATE tareas SET estado = ?, mensaje = ?, post_id = ?, fin = ? WHERE id = ?",
               (estado, str(mensaje)[:1000], post_id, ahora(), tarea_id))
    db.commit()


def tarea_ultima(db):
    return db.execute("SELECT * FROM tareas ORDER BY id DESC LIMIT 1").fetchone()


def tarea_trabajando(db):
    """Para no largar dos corridas a la vez. Una tarea que quedó 'trabajando'
    hace más de 10 minutos se considera colgada (ej. se reinició el servidor)."""
    t = db.execute(
        "SELECT * FROM tareas WHERE estado = 'trabajando' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not t:
        return None
    viejo = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(timespec="seconds")
    if t["inicio"] < viejo:
        db.execute("UPDATE tareas SET estado = 'error', mensaje = ?, fin = ? WHERE id = ?",
                   ("La corrida quedó sin terminar (puede que se haya reiniciado el servidor).",
                    ahora(), t["id"]))
        db.commit()
        return None
    return t


def ultimo_periodo(db, clave):
    """El período más nuevo guardado de una serie, o None."""
    r = db.execute("SELECT MAX(periodo) AS p FROM observaciones WHERE clave = ?", (clave,)).fetchone()
    return r["p"] if r and r["p"] else None


def ultimas_revisiones(db, cuantas=12):
    return db.execute(
        "SELECT clave, periodo, valor_anterior, valor_nuevo, detectada FROM revisiones "
        "ORDER BY id DESC LIMIT ?", (cuantas,)
    ).fetchall()
