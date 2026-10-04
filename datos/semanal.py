"""
Traer los datos de la EIA y dejar el borrador en el blog
=======================================================
Se usa de dos formas, con el mismo código:

* **A mano, desde el panel**: `/admin/datos` tiene las series con casilleros y
  un botón "Traer datos y armar el borrador". La página llama a
  `correr_tarea()`, que trabaja en segundo plano y va dejando el avance en la
  base para que la página lo muestre.
* **Automático**: este archivo corrido como programa (Programador de tareas de
  Windows o cron). Hace lo mismo sin que nadie aprete nada.

Los tres pasos son siempre los mismos:

  1. bajar de la API de la EIA cada serie de `datos/series.py`;
  2. guardarlas en la base histórica propia (`datos/datos.db`), anotando los
     datos nuevos y las revisiones de datos viejos;
  3. escribir un post en **borrador** en el blog, con un gráfico y un párrafo
     por serie. No publica nada.

Uso normal como programa:

    venv\\Scripts\\python.exe datos\\semanal.py

Otras formas:

    --series propano_exp_usa,gas_exp_usa   solo esas series
    --solo-captura                         bajar y guardar, sin armar el post
    --solo-informe                         armar el post con lo ya guardado (sin API)
    --completo                             re-bajar la serie entera (por defecto
                                           se baja solo el último año, que es
                                           donde la EIA revisa)
    --sin-publicaciones                    sin la sección de citas de la EIA
    --demo                                 probar todo el circuito con datos
                                           inventados, sin clave de la EIA
    --estado                               qué hay en la base histórica
    --db RUTA                              base del blog (default: la de app.py)
    --datos RUTA                           base histórica (default: datos/datos.db)
    --explorar natural-gas/move/expc       ver qué tiene una ruta de la EIA
    --explorar RUTA --faceta series --contiene propane
                                           buscar el código de una serie

Qué hace falta la primera vez: una clave gratuita de la EIA
(https://www.eia.gov/opendata/register.php, llega por mail al instante) en
el archivo `.env` del proyecto, como `EIA_API_KEY=...`.
"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROYECTO = os.path.dirname(BASE_DIR)
if PROYECTO not in sys.path:
    sys.path.insert(0, PROYECTO)

# El .env del proyecto (donde está EIA_API_KEY), igual que hace app.py.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROYECTO, ".env"))
except ImportError:
    pass

from datos import almacen, eia_api, informe, publicaciones as pubs   # noqa: E402
from datos import series as registro                               # noqa: E402

LOG = os.path.join(BASE_DIR, "semanal.log")
LOG_MAX = 500_000      # medio mega: se recorta la mitad más vieja


def log(mensaje, silencioso=False):
    linea = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')}  {mensaje}"
    if not silencioso:
        print(mensaje, flush=True)
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > LOG_MAX:
            with open(LOG, encoding="utf-8", errors="replace") as f:
                lineas = f.readlines()
            with open(LOG, "w", encoding="utf-8") as f:
                f.writelines(lineas[len(lineas) // 2:])
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(linea + "\n")
    except OSError:
        pass       # que no se caiga la corrida por no poder escribir el log


# ---------------------------------------------------------------------------
# Captura
# ---------------------------------------------------------------------------

def retroceder_un_anio(periodo, frecuencia):
    """Desde dónde volver a pedir una serie que ya tenemos. La EIA revisa los
    datos recientes, no los de hace diez años: se re-piden los últimos 12
    meses y el resto queda como está (mucho menos tráfico y mucho más rápido,
    que importa cuando alguien está esperando el botón del panel)."""
    try:
        if frecuencia == "weekly":
            d = date.fromisoformat(periodo)
            return (d - timedelta(days=370)).isoformat()
        if frecuencia == "monthly":
            anio, mes = periodo.split("-")[:2]
            return f"{int(anio) - 1}-{mes}"
        return str(int(periodo[:4]) - 3)
    except (ValueError, IndexError):
        return None


def bajar(definicion, desde=None):
    """Prueba los (ruta, código) de la serie en orden y devuelve el primero
    que traiga datos, junto con la ruta y el código que funcionaron."""
    errores = []
    for ruta, series_id in definicion["candidatos"]:
        try:
            obs = eia_api.serie(ruta, series_id, definicion["frecuencia"],
                                desde=desde or definicion.get("desde"))
            return obs, ruta, series_id
        except eia_api.EIAError as e:
            errores.append(f"{ruta}/{series_id}: {e}")
            if "Falta la clave" in str(e):
                break
    raise eia_api.EIAError(" | ".join(errores))


def datos_demo(definicion):
    """Serie inventada, para ver el circuito completo sin clave de la EIA.
    Determinista: la misma corrida da siempre lo mismo."""
    import math
    hoy = datetime.now(timezone.utc).date()
    n = 160 if definicion["frecuencia"] == "weekly" else 72
    ciclo = 52 if definicion["frecuencia"] == "weekly" else 12
    obs = []
    for i in range(n):
        if definicion["frecuencia"] == "weekly":
            periodo = (hoy - timedelta(days=7 * (n - 1 - i) + 5)).isoformat()
        else:
            mes = hoy.month - (n - 1 - i)
            anio = hoy.year + (mes - 1) // 12
            periodo = f"{anio}-{(mes - 1) % 12 + 1:02d}"
        estacional = 120 * math.sin(i / (ciclo / (2 * math.pi)))
        obs.append({"period": periodo, "value": round(1000 + 9 * i + estacional + (i % 7) * 11, 1),
                    "unit": "DEMO"})
    return obs, "demo", "DEMO"


def capturar(db, claves=None, demo=False, silencioso=False, completo=False, tarea_id=None):
    """Baja y guarda cada serie. Devuelve (desde_ts, capturadas, fallas)."""
    desde_ts = almacen.ahora()
    elegidas = registro.activas(claves)
    capturadas, fallas = [], []
    for i, (clave, d) in enumerate(elegidas, 1):
        almacen.tarea_paso(db, tarea_id, f"{i} de {len(elegidas)}: {d['corto']}")
        desde = None
        if not completo and not demo:
            ultimo = almacen.ultimo_periodo(db, clave)
            if ultimo:
                desde = retroceder_un_anio(ultimo, d["frecuencia"])
        try:
            obs, ruta, series_id = datos_demo(d) if demo else bajar(d, desde)
        except eia_api.EIAError as e:
            almacen.anotar_error(db, clave, e)
            log(f"[ERROR] {clave}: {e}", silencioso)
            fallas.append((clave, str(e)))
            continue
        r = almacen.guardar(db, clave, d, series_id, ruta, obs)
        log(f"[ok] {clave}: {r['filas']} períodos pedidos ({r['nuevas']} nuevos, "
            f"{r['revisadas']} revisados) — último {obs[-1]['period']} = {obs[-1]['value']}",
            silencioso)
        capturadas.append(clave)
    almacen.tarea_paso(db, tarea_id, f"{len(elegidas)} de {len(elegidas)}: armando el borrador")
    return desde_ts, capturadas, fallas


# ---------------------------------------------------------------------------
# Informe
# ---------------------------------------------------------------------------

def preparar_resultados(db, claves=None, desde_ts="9999"):
    """Lo que necesita el informe: datos guardados + estadísticas + revisiones."""
    salida = []
    for clave, d in registro.activas(claves):
        datos = almacen.historia(db, clave)
        if not datos:
            continue
        salida.append({
            "clave": clave,
            "definicion": d,
            "datos": datos,
            "stats": informe.analizar(datos, d),
            "revisiones": almacen.revisiones_de(db, clave, desde_ts),
        })
    return salida


def traer_publicaciones(db, silencioso=False):
    """Lo que la EIA escribió (artículos y perspectivas). Nunca rompe el
    informe: si una fuente falla, queda anotada y se sigue.
    Devuelve (publicaciones, fallas)."""
    try:
        publicaciones, fallas = pubs.traer()
    except Exception as e:                      # red, XML roto, lo que sea
        log(f"[ERROR] publicaciones: {type(e).__name__}: {e}", silencioso)
        return [], [("publicaciones", f"{type(e).__name__}: {e}")]
    for clave, motivo in fallas:
        log(f"[ERROR] publicaciones/{clave}: {motivo}", silencioso)
    nuevas = pubs.guardar(db, publicaciones)
    log(f"[ok] publicaciones: {len(publicaciones)} ({len(nuevas)} nuevas desde la última corrida)",
        silencioso)
    return publicaciones, fallas


def armar_informe(resultados, fallas=(), db_blog=None, silencioso=False, publicaciones=(),
                  fallas_publicaciones=()):
    hoy = datetime.now(timezone.utc) - timedelta(hours=3)      # hora de Buenos Aires
    titulo = f"Seguimiento de datos EIA — {informe.fecha_larga(hoy)}"
    slug_base = f"datos-eia-{hoy.date().isoformat()}"
    # El copete: el titular de la serie principal, para no empezar en frío.
    s, d = resultados[0]["stats"], resultados[0]["definicion"]
    dek = (f"{d['corto']}: {informe.fmt(s['ultimo'], d.get('decimales', 0))} "
           f"{d.get('unidad_corta', '')} en {informe.periodo_largo(s['ultimo_periodo'], s['frecuencia'])}")
    if s.get("hace_un_anio") is not None:
        dek += f", {informe.fmt_pct(s['ultimo'], s['hace_un_anio'])} contra un año antes"
    dek += "."
    bloques = informe.armar_bloques(resultados, hoy=hoy, con_fallas=fallas,
                                    publicaciones=publicaciones,
                                    fallas_publicaciones=fallas_publicaciones)
    post_id, slug, accion = informe.armar_borrador(
        bloques, titulo=titulo, slug_base=slug_base,
        eyebrow="Seguimiento de datos; EIA; Estados Unidos",
        dek=dek, accent="navy", db_path=db_blog,
    )
    log(f"[ok] borrador {accion}: #{post_id} /{slug} — {len(bloques)} bloques", silencioso)
    return post_id, slug, accion


# ---------------------------------------------------------------------------
# El circuito completo (lo usan el panel y el automático)
# ---------------------------------------------------------------------------

# Centinela para "no me pasaron claves_informe": no sirve None, porque None ya
# significa "todas las series guardadas".
LAS_TRAIDAS = object()


def correr(claves=None, db_blog=None, datos_db=None, demo=False, completo=False,
           tarea_id=None, silencioso=True, db=None, claves_informe=LAS_TRAIDAS,
           con_publicaciones=True):
    """Captura + informe. Devuelve (post_id, slug, accion, fallas).
    Si no se pudo capturar NINGUNA serie, levanta eia_api.EIAError.

    `claves` = qué series se traen de la EIA; `claves_informe` = qué series
    entran en el borrador (por defecto, las mismas que se trajeron; None =
    todas las que tengan datos guardados). Se separan porque desde el panel se
    puede pedir "traeme solo las exportaciones" y querer igual un borrador con
    todo lo que ya tenemos guardado."""
    propia = db is None
    db = db or almacen.conectar(datos_db)
    try:
        desde_ts, capturadas, fallas = capturar(db, claves, demo=demo, silencioso=silencioso,
                                                completo=completo, tarea_id=tarea_id)
        if not capturadas:
            raise eia_api.EIAError(
                "No se pudo traer ninguna serie. " +
                (fallas[0][1] if fallas else "La EIA no respondió."))
        del_informe = claves if claves_informe is LAS_TRAIDAS else claves_informe
        resultados = preparar_resultados(db, del_informe, desde_ts)
        publicaciones, fallas_pub = [], []
        if con_publicaciones and not demo:
            almacen.tarea_paso(db, tarea_id, "leyendo lo que publicó la EIA")
            publicaciones, fallas_pub = traer_publicaciones(db, silencioso)
        if not resultados:
            raise eia_api.EIAError("No hay datos guardados para armar el informe.")
        post_id, slug, accion = armar_informe(resultados, fallas, db_blog=db_blog,
                                              silencioso=silencioso,
                                              publicaciones=publicaciones,
                                              fallas_publicaciones=fallas_pub)
        return post_id, slug, accion, fallas
    finally:
        if propia:
            db.close()


def correr_tarea(tarea_id, claves, db_blog=None, datos_db=None, completo=False,
                 claves_informe=LAS_TRAIDAS, con_publicaciones=True):
    """Lo que ejecuta el hilo que largó el botón del panel: igual que correr(),
    pero deja el resultado anotado en la tarea en vez de devolverlo (la página
    lo lee de la base, así funciona aunque el servidor tenga varios workers)."""
    db = almacen.conectar(datos_db)
    try:
        post_id, slug, accion, fallas = correr(
            claves, db_blog=db_blog, completo=completo, tarea_id=tarea_id, db=db,
            claves_informe=claves_informe, con_publicaciones=con_publicaciones)
        mensaje = f"Borrador {accion}: {slug}."
        if fallas:
            mensaje += (f" No se pudieron actualizar {len(fallas)} serie"
                        f"{'s' if len(fallas) > 1 else ''}: " +
                        ", ".join(c for c, _ in fallas) + ".")
        almacen.tarea_fin(db, tarea_id, "listo", mensaje, post_id)
    except Exception as e:                       # cualquier cosa: queda anotada
        log(f"[ERROR] tarea {tarea_id}: {type(e).__name__}: {e}", silencioso=True)
        almacen.tarea_fin(db, tarea_id, "error", f"{e}")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Comandos auxiliares
# ---------------------------------------------------------------------------

def mostrar_estado(db):
    filas = almacen.resumen(db)
    if not filas:
        print("La base histórica está vacía: todavía no se capturó nada.")
        return
    print(f"{'serie':22} {'código':26} {'frec':8} {'períodos':>8}  {'desde':11} {'hasta':11} rev.  última captura")
    for r in filas:
        print(f"{r['clave']:22} {r['series_id']:26} {r['frecuencia']:8} {r['periodos']:>8}  "
              f"{str(r['desde'] or ''):11} {str(r['hasta'] or ''):11} {r['revisiones']:>4}  "
              f"{(r['ultima_captura'] or '')[:19]}")


def explorar(ruta, faceta=None, contiene=""):
    if faceta:
        valores = eia_api.valores_faceta(ruta, faceta, contiene)
        print(f"{len(valores)} valores de la faceta '{faceta}' en {ruta}"
              f"{f' que contienen “{contiene}”' if contiene else ''}:")
        for v in valores[:200]:
            print(f"  {str(v.get('id', '')):30} {v.get('name', '')}")
        if len(valores) > 200:
            print(f"  ... y {len(valores) - 200} más (usá --contiene para filtrar)")
        return
    meta = eia_api.metadatos(ruta)
    print(f"Ruta: {ruta}  —  {meta.get('name', '')}")
    if meta.get("description"):
        print(f"  {meta['description']}")
    if meta.get("routes"):
        print("  Sub-rutas:")
        for r in meta["routes"]:
            print(f"    {r.get('id', ''):22} {r.get('name', '')}")
    if meta.get("frequency"):
        print("  Frecuencias: " + ", ".join(str(f.get("id", f)) for f in meta["frequency"]))
    if meta.get("data"):
        print("  Columnas de datos: " + ", ".join(meta["data"].keys()))
    if meta.get("facets"):
        print("  Facetas: " + ", ".join(str(f.get("id", f)) for f in meta["facets"]))
        print(f"  (para ver los códigos: --explorar {ruta} --faceta series)")


# ---------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(
        description="Captura las series de la EIA y deja un borrador en el blog.")
    p.add_argument("--series", help="solo estas series, separadas por coma")
    p.add_argument("--solo-captura", action="store_true", help="no armar el post")
    p.add_argument("--solo-informe", action="store_true", help="no llamar a la API")
    p.add_argument("--completo", action="store_true", help="re-bajar la serie entera, no solo el último año")
    p.add_argument("--sin-publicaciones", action="store_true",
                   help="no incluir lo que escribió la EIA (artículos y perspectivas)")
    p.add_argument("--demo", action="store_true", help="datos inventados, sin clave de la EIA")
    p.add_argument("--estado", action="store_true", help="qué hay en la base histórica")
    p.add_argument("--db", help="base del blog (default: la de app.py / DB_PATH)")
    p.add_argument("--datos", help="base histórica (default: datos/datos.db)")
    p.add_argument("--explorar", metavar="RUTA", help="ver una ruta de la API de la EIA")
    p.add_argument("--faceta", help="con --explorar: listar los valores de esa faceta")
    p.add_argument("--contiene", default="", help="con --faceta: filtrar por texto")
    p.add_argument("--silencioso", action="store_true", help="solo al log, sin imprimir")
    args = p.parse_args(argv)

    if args.explorar:
        try:
            explorar(args.explorar, args.faceta, args.contiene)
        except eia_api.EIAError as e:
            print(f"[ERROR] {e}")
            return 1
        return 0

    # Si falta la clave, decirlo una sola vez y de entrada (si no, el mismo
    # mensaje se repite por cada serie y no se entiende qué pasó).
    if not args.demo and not args.estado and not args.solo_informe:
        try:
            eia_api.api_key()
        except eia_api.EIAError as e:
            log(f"[ERROR] {e}", args.silencioso)
            return 1

    # El modo demo usa una base aparte: los datos inventados no tienen que
    # mezclarse nunca con la historia real capturada de la EIA.
    ruta_datos = args.datos or (os.path.join(BASE_DIR, "demo.db") if args.demo else None)
    db = almacen.conectar(ruta_datos)
    try:
        if args.estado:
            mostrar_estado(db)
            return 0

        claves = [c.strip() for c in args.series.split(",")] if args.series else None

        if args.solo_captura:
            _, capturadas, _ = capturar(db, claves, demo=args.demo, silencioso=args.silencioso,
                                        completo=args.completo)
            return 0 if capturadas else 1

        if args.solo_informe:
            resultados = preparar_resultados(db, claves)
            if not resultados:
                log("[ERROR] no hay datos guardados para armar el informe.", args.silencioso)
                return 1
            publicaciones, fallas_pub = [], []
            if not args.sin_publicaciones:
                publicaciones, fallas_pub = traer_publicaciones(db, args.silencioso)
            armar_informe(resultados, [], db_blog=args.db, silencioso=args.silencioso,
                          publicaciones=publicaciones, fallas_publicaciones=fallas_pub)
            return 0

        try:
            correr(claves, db_blog=args.db, demo=args.demo, completo=args.completo,
                   silencioso=args.silencioso, db=db,
                   con_publicaciones=not args.sin_publicaciones)
        except eia_api.EIAError as e:
            log(f"[ERROR] {e}", args.silencioso)
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:                      # que el log siempre quede escrito
        log(f"[ERROR] la corrida se cortó: {type(e).__name__}: {e}")
        raise
