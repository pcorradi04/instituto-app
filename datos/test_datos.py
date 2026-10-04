"""
Chequeos del automático de datos
================================
Corre sin internet y sin clave de la EIA: la llamada a la API se reemplaza
por series inventadas. Prueba lo que de verdad puede romperse: el formato de
los números, las cuentas del análisis, la detección de revisiones y que el
borrador quede bien armado en una base del blog temporal.

    venv\\Scripts\\python.exe datos\\test_datos.py
"""

import json
import os
import sqlite3
import sys
import tempfile
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROYECTO = os.path.dirname(BASE_DIR)
sys.path.insert(0, PROYECTO)

# La base del blog tiene que ser temporal ANTES de importar app.py (que al
# importarse crea las tablas en DB_PATH).
TMP = tempfile.mkdtemp(prefix="test-datos-")
os.environ["DB_PATH"] = os.path.join(TMP, "blog.db")
os.environ["DATOS_DB_PATH"] = os.path.join(TMP, "panel.db")   # la que usa el panel
os.environ["EIA_API_KEY"] = "clave-de-prueba"

from datos import almacen, eia_api, informe, semanal   # noqa: E402
from datos import publicaciones as pubs                # noqa: E402
from datos import series as registro                   # noqa: E402

ok = fallos = 0


def check(condicion, descripcion):
    global ok, fallos
    if condicion:
        ok += 1
    else:
        fallos += 1
        print(f"  FALLA: {descripcion}")


# ---------------------------------------------------------------------------
# Formato de números y períodos
# ---------------------------------------------------------------------------
print("Formato")
check(informe.fmt(1234.5, 1) == "1.234,5", "1234.5 -> 1.234,5")
check(informe.fmt(1234567) == "1.234.567", "miles con punto")
check(informe.fmt(959.1, 1) == "959,1", "decimal con coma")
check(informe.fmt(None) == "s/d", "None -> s/d")
check(informe.fmt_pct(110, 100) == "+10,0 %", "suba")
check(informe.fmt_pct(90, 100) == "-10,0 %", "baja")
check(informe.fmt_pct(100, 100) == "sin cambios", "igual")
check(informe.fmt_pct(100, 0) == "s/d", "división por cero")
check(informe.fmt_pct(None, 100) == "s/d", "sin dato")
check(informe.periodo_largo("2026-09-26", "weekly") == "la semana terminada el 26 de septiembre de 2026",
      "período semanal en palabras")
check(informe.periodo_largo("2026-07", "monthly") == "julio de 2026", "período mensual en palabras")
check(informe.periodo_largo("2026", "annual") == "2026", "período anual")
check(informe.periodo_largo("rarísimo", "monthly") == "rarísimo", "período con formato raro no explota")

# ---------------------------------------------------------------------------
# Análisis
# ---------------------------------------------------------------------------
print("Análisis")
mensual = {"frecuencia": "monthly", "agregacion": "suma", "decimales": 0}
# 36 meses de 2024-01 a 2026-12, valor = 100 + i
datos = []
for i in range(36):
    anio, mes = 2024 + i // 12, i % 12 + 1
    datos.append((f"{anio}-{mes:02d}", 100.0 + i))
s = informe.analizar(datos, mensual)
check(s["ultimo"] == 135 and s["ultimo_periodo"] == "2026-12", "último dato")
check(s["previo"] == 134, "dato previo")
check(s["hace_un_anio"] == 123, "mismo mes del año anterior (12 atrás)")
check(abs(s["prom_corto"] - 134.0) < 1e-9, "promedio de los últimos 3 meses")
check(abs(s["prom_corto_anterior"] - 122.0) < 1e-9, "promedio del mismo tramo del año anterior")
check(s["acum_anio"] == sum(range(124, 136)), "acumulado del año (suma)")
check(s["acum_anio_anterior"] == sum(range(112, 124)), "acumulado del año anterior")
check(s["max_valor"] == 135 and s["min_valor"] == 112, "extremos de los últimos 24 meses")
check(s["periodos"] == 36 and s["primer_periodo"] == "2024-01", "tamaño de la serie")

# Un caudal se promedia, no se suma.
caudal = informe.analizar(datos, {"frecuencia": "monthly", "agregacion": "promedio"})
check(abs(caudal["acum_anio"] - sum(range(124, 136)) / 12) < 1e-9, "acumulado de un caudal = promedio")

# Serie corta: no inventa comparaciones.
corta = informe.analizar([("2026-01", 10.0)], mensual)
check(corta["previo"] is None and corta["hace_un_anio"] is None, "serie de un dato: sin comparaciones")
check(corta["acum_anio_anterior"] is None, "serie de un dato: sin año anterior")
texto = informe.texto_serie(corta, dict(mensual, unidad="MMpc", corto="X", nombre="X"))
check("enero de 2026" in texto and "s/d" not in texto, "el texto se adapta a la serie corta")

# Año anterior incompleto: no compara peras con manzanas.
parcial = informe.analizar([("2025-01", 5.0), ("2025-02", 5.0), ("2026-01", 7.0), ("2026-02", 8.0)], mensual)
check(parcial["acum_anio"] == 15.0 and parcial["acum_anio_anterior"] == 10.0, "mismo número de meses de cada año")

# ---------------------------------------------------------------------------
# Base histórica: altas y revisiones
# ---------------------------------------------------------------------------
print("Base histórica")
db = almacen.conectar(os.path.join(TMP, "datos.db"))
d = registro.SERIES["gas_exp_usa"]
obs1 = [{"period": "2026-05", "value": 100.0, "unit": "MMCF"},
        {"period": "2026-06", "value": 200.0, "unit": "MMCF"}]
r1 = almacen.guardar(db, "gas_exp_usa", d, "N9130US2", "natural-gas/move/expc", obs1)
check((r1["nuevas"], r1["revisadas"]) == (2, 0), "primera captura: dos períodos nuevos")

ts_antes = almacen.ahora()
obs2 = obs1 + [{"period": "2026-07", "value": 300.0, "unit": "MMCF"}]
obs2[1] = {"period": "2026-06", "value": 205.0, "unit": "MMCF"}      # revisión
r2 = almacen.guardar(db, "gas_exp_usa", d, "N9130US2", "natural-gas/move/expc", obs2)
check((r2["nuevas"], r2["revisadas"]) == (1, 1), "segunda captura: un nuevo y una revisión")
check(r2["revisiones"] == [("2026-06", 200.0, 205.0)], "la revisión queda con el valor viejo y el nuevo")
check(almacen.historia(db, "gas_exp_usa") == [("2026-05", 100.0), ("2026-06", 205.0), ("2026-07", 300.0)],
      "la historia queda ordenada y con el valor corregido")
check(len(almacen.revisiones_de(db, "gas_exp_usa", ts_antes)) == 1, "revisiones de esta corrida")
check(almacen.revisiones_de(db, "gas_exp_usa", "9999") == [], "ninguna revisión futura")

r3 = almacen.guardar(db, "gas_exp_usa", d, "N9130US2", "natural-gas/move/expc", obs2)
check((r3["nuevas"], r3["revisadas"]) == (0, 0), "capturar lo mismo dos veces no duplica ni revisa")
check(almacen.historia(db, "gas_exp_usa", ultimos=2) == [("2026-06", 205.0), ("2026-07", 300.0)],
      "últimos N períodos")
almacen.anotar_error(db, "propano_exp_usa", "la API no respondió")
check(db.execute("SELECT COUNT(*) FROM capturas WHERE error != ''").fetchone()[0] == 1,
      "los errores quedan en el log de capturas")
check([r["clave"] for r in almacen.resumen(db)] == ["gas_exp_usa"], "resumen de la base")
db.close()

# ---------------------------------------------------------------------------
# Tabla de datos del gráfico
# ---------------------------------------------------------------------------
print("Gráficos")
import app   # noqa: E402  (ya con DB_PATH temporal)

tabla = informe.tabla([("2026-01", 1172.0), ("2026-02", 959.14)])
check(tabla == "2026-01 | 1172\n2026-02 | 959.14", "la tabla no deja 1172.0")
labels, series_, rows = app.parse_table(tabla, "line")
check(labels == ["2026-01", "2026-02"] and series_ == [[1172.0, 959.14]],
      "app.py parsea la tabla que genera el automático")

# ---------------------------------------------------------------------------
# El borrador entero, con datos inventados
# ---------------------------------------------------------------------------
print("Borrador")
datos_db = os.path.join(TMP, "datos2.db")
code = semanal.main(["--demo", "--datos", datos_db, "--silencioso"])
check(code == 0, "la corrida completa en modo demo termina bien")

blog = sqlite3.connect(os.environ["DB_PATH"])
blog.row_factory = sqlite3.Row
posts = blog.execute("SELECT * FROM posts ORDER BY id").fetchall()
borradores = [p for p in posts if p["status"] == "draft"]
check(len(borradores) == 1, "quedó exactamente un borrador")
post = borradores[0]
check(post["status"] == "draft" and post["published_at"] is None, "el post queda sin publicar")
check(post["slug"].startswith("datos-eia-20"), f"slug con fecha ({post['slug']})")
check("EIA" in post["title"], "el título nombra la fuente")
check("Seguimiento de datos" in post["eyebrow"], "etiquetas cargadas")
check(len(post["dek"]) > 20, "copete con el titular del dato")

bloques = blog.execute("SELECT type, data FROM blocks WHERE post_id = ? ORDER BY position",
                       (post["id"],)).fetchall()
tipos = [b["type"] for b in bloques]
check(all(t in app.BLOCK_TYPES for t in tipos), "todos los tipos de bloque son válidos")
check(tipos[0] == "callout", "arranca con el aviso de borrador")
check(tipos.count("chart") == len(registro.ORDEN), "un gráfico por serie")
check(tipos.count("heading") == len(registro.ORDEN) + 1, "un título por serie más el de método")

graficos = [json.loads(b["data"]) for b in bloques if b["type"] == "chart"]
check(all(g["chart_type"] == "line" for g in graficos), "los gráficos son de líneas")
check(all(len(g["labels"]) > 20 for g in graficos), "cada gráfico tiene la serie cargada")
check(all(len(g["series"]) == 1 and all(v is not None for v in g["series"][0]) for g in graficos),
      "una sola serie, sin huecos")
check(all(g["source"] for g in graficos), "cada gráfico dice su fuente")
check(all(g["colors"] and g["colors"][0] for g in graficos), "cada gráfico tiene color")
primero = json.loads([b["data"] for b in bloques if b["type"] == "callout"][0])
check("Borrador automático" in primero["text"], "el aviso dice que es borrador")

# Correr de nuevo el mismo día reemplaza el borrador, no acumula posts.
code2 = semanal.main(["--demo", "--datos", datos_db, "--silencioso"])
check(code2 == 0, "segunda corrida del mismo día termina bien")
check(blog.execute("SELECT COUNT(*) FROM posts WHERE status = 'draft'").fetchone()[0] == 1,
      "no se duplica el borrador del día")
check(blog.execute("SELECT COUNT(*) FROM blocks WHERE post_id = ?", (post["id"],)).fetchone()[0] == len(bloques),
      "los bloques se reemplazan, no se suman")

# Si el borrador ya se publicó, el automático no lo pisa: crea otro.
blog.execute("UPDATE posts SET status = 'published', published_at = '2026-10-03T12:00:00' WHERE id = ?",
             (post["id"],))
blog.commit()
semanal.main(["--demo", "--datos", datos_db, "--silencioso"])
check(blog.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == len(posts) + 1,
      "con el del día ya publicado, crea un post nuevo")
check(blog.execute("SELECT status FROM posts WHERE id = ?", (post["id"],)).fetchone()[0] == "published",
      "el post publicado queda intacto")
blog.close()

# Series elegidas a mano.
solo = tempfile.mktemp(suffix=".db", dir=TMP)
check(semanal.main(["--demo", "--datos", solo, "--solo-captura", "--series", "propano_exp_usa",
                    "--silencioso"]) == 0, "captura de una sola serie")
db2 = almacen.conectar(solo)
check([r["clave"] for r in almacen.resumen(db2)] == ["propano_exp_usa"], "solo se capturó la serie pedida")
db2.close()

# ---------------------------------------------------------------------------
# Errores de la API
# ---------------------------------------------------------------------------
print("Errores")
guardado = os.environ.pop("EIA_API_KEY")
try:
    eia_api.api_key()
    check(False, "sin clave tiene que avisar")
except eia_api.EIAError as e:
    check("register.php" in str(e), "el error sin clave dice dónde sacarla")
os.environ["EIA_API_KEY"] = guardado
check(eia_api._tapar("https://api.eia.gov/v2?api_key=secreta", "secreta").endswith("***"),
      "la clave nunca aparece en un mensaje de error")
try:
    registro.activas(["no-existe"])
    check(False, "serie inexistente tiene que avisar")
except KeyError as e:
    check("no-existe" in str(e), "el error nombra la serie que no existe")

# Una serie que falla no impide el informe con las demás.
def bajar_roto(definicion, desde=None):
    if definicion["corto"].startswith("Propano"):
        raise eia_api.EIAError("503 de la EIA")
    return semanal.datos_demo(definicion)

original = semanal.bajar
semanal.bajar = bajar_roto
try:
    db3 = tempfile.mktemp(suffix=".db", dir=TMP)
    check(semanal.main(["--datos", db3, "--silencioso"]) == 0, "con una serie caída el informe se arma igual")
    blog = sqlite3.connect(os.environ["DB_PATH"])
    ultimo = blog.execute("SELECT id FROM posts ORDER BY id DESC LIMIT 1").fetchone()[0]
    avisos = [json.loads(r[0]) for r in blog.execute(
        "SELECT data FROM blocks WHERE post_id = ? AND type = 'callout'", (ultimo,))]
    check(any("no se pudieron actualizar" in a["text"] for a in avisos),
          "el borrador avisa qué serie no se pudo actualizar")
    blog.close()
finally:
    semanal.bajar = original

# ---------------------------------------------------------------------------
# El botón del panel (/admin/datos)
# ---------------------------------------------------------------------------
print("Panel")
app.app.config["TESTING"] = True
cli = app.app.test_client()

r = cli.get("/admin/datos")
check(r.status_code == 302 and "/admin/login" in r.headers.get("Location", ""),
      "sin sesión, la pantalla de datos redirige al login")

blog = sqlite3.connect(os.environ["DB_PATH"])
blog.row_factory = sqlite3.Row
usuario = blog.execute("SELECT id, initials, role FROM users LIMIT 1").fetchone()
with cli.session_transaction() as ses:
    ses["user_id"] = usuario["id"]; ses["user_initials"] = usuario["initials"]
    ses["role"] = usuario["role"]; ses["is_admin"] = True

html = cli.get("/admin/datos").get_data(as_text=True)
check("Traer datos y armar el borrador" in html, "la pantalla tiene el botón")
for clave, d in registro.activas():
    check(d["nombre"] in html, f"la pantalla lista {clave}")
check(html.count('name="series"') == len(registro.ORDEN), "un casillero por serie")
check("Falta la clave de la EIA" not in html, "con clave puesta no muestra el aviso")

r = cli.post("/admin/datos/traer", data={}, follow_redirects=True)
check("Elegí al menos una serie" in r.get_data(as_text=True), "sin series marcadas avisa")
dbp = almacen.conectar(os.environ["DATOS_DB_PATH"])
check(almacen.tarea_ultima(dbp) is None, "sin series marcadas no crea tarea")

guardada = os.environ.pop("EIA_API_KEY")
r = cli.post("/admin/datos/traer", data={"series": ["gas_exp_usa"]}, follow_redirects=True)
check("Falta la clave de la EIA" in r.get_data(as_text=True), "sin clave no larga la búsqueda")
check(almacen.tarea_ultima(dbp) is None, "sin clave no crea tarea")
os.environ["EIA_API_KEY"] = guardada


def esperar_tarea(db, segundos=15):
    for _ in range(segundos * 4):
        t = almacen.tarea_ultima(db)
        if t and t["estado"] != "trabajando":
            return t
        time.sleep(0.25)
    return almacen.tarea_ultima(db)


# El botón de verdad, con la bajada de la EIA reemplazada por datos inventados.
antes = semanal.bajar
semanal.bajar = lambda definicion, desde=None: semanal.datos_demo(definicion)
try:
    r = cli.post("/admin/datos/traer", data={"series": ["gas_exp_usa", "crudo_prod_usa"]},
                 follow_redirects=True)
    check("Trayendo 2 series" in r.get_data(as_text=True), "avisa que está trayendo")
    tarea = esperar_tarea(dbp)
    check(tarea is not None and tarea["estado"] == "listo",
          "la tarea termina bien (quedó en %s: %s)" % (
              tarea["estado"] if tarea else None, tarea["mensaje"] if tarea else ""))
    check(tarea["quien"] == usuario["initials"], "queda registrado quién la pidió")
    check(tarea["post_id"] is not None, "la tarea guarda el post que creó")
    check(sorted(tarea["series"].split(",")) == ["crudo_prod_usa", "gas_exp_usa"],
          "la tarea guarda qué series se pidieron")
    tipos = [f[0] for f in blog.execute(
        "SELECT type FROM blocks WHERE post_id = ? ORDER BY position", (tarea["post_id"],))]
    check(tipos.count("chart") == 2, "el borrador lleva solo las series marcadas")
    html = cli.get("/admin/datos").get_data(as_text=True)
    check("Abrir el borrador" in html, "la pantalla ofrece abrir el borrador")
    check("Última búsqueda" in html, "la pantalla muestra el resultado")

    # Con la casilla "todas" se trae UNA serie pero el borrador incluye todas
    # las que ya tengan historia guardada (acá, las dos de la corrida anterior).
    cli.post("/admin/datos/traer", data={"series": ["gas_exp_usa"], "todas": "1"},
             follow_redirects=True)
    t2 = esperar_tarea(dbp)
    check(t2["estado"] == "listo" and t2["series"] == "gas_exp_usa",
          "con 'todas' se trae igual solo la serie marcada")
    titulos = [json.loads(f[0])["title"] for f in blog.execute(
        "SELECT data FROM blocks WHERE post_id = ? AND type = 'chart' ORDER BY position",
        (t2["post_id"],))]
    check(len(titulos) == 2 and registro.SERIES["crudo_prod_usa"]["corto"] in titulos,
          "con 'todas' el borrador suma las series guardadas que no se trajeron ahora")
    check(registro.SERIES["propano_exp_usa"]["corto"] not in titulos,
          "una serie sin datos guardados no aparece en el borrador")
finally:
    semanal.bajar = antes
dbp.close()
blog.close()

# ---------------------------------------------------------------------------
# Captura incremental: desde dónde se vuelve a pedir una serie ya guardada
# ---------------------------------------------------------------------------
print("Incremental")
check(semanal.retroceder_un_anio("2026-09-25", "weekly") == "2025-09-20",
      "semanal: un año y pico atrás")
check(semanal.retroceder_un_anio("2026-07", "monthly") == "2025-07",
      "mensual: el mismo mes del año anterior")
check(semanal.retroceder_un_anio("2026", "annual") == "2023", "anual: tres años atrás")
check(semanal.retroceder_un_anio("rarísimo", "monthly") is None,
      "período raro: se pide la serie entera")

# ---------------------------------------------------------------------------
# Lo que la EIA escribe (artículos y perspectivas)
# ---------------------------------------------------------------------------
print("Publicaciones")

RSS = b"""<?xml version="1.0" encoding="ISO-8859-1" ?>
<rss version="2.0"><channel><title>Today in Energy</title>
<item><title>U.S. exports of propane reached records</title>
<link>https://www.eia.gov/todayinenergy/detail.php?id=68244</link>
<pubDate>Thu, 01 Oct 2026  09:00:00 EST</pubDate>
<description>U.S. propane exports increased to 2 million barrels per day.</description></item>
<item><title>Solar capacity grew in 2026</title>
<link>https://www.eia.gov/todayinenergy/detail.php?id=68100</link>
<pubDate>Wed, 30 Sep 2026  09:00:00 EST</pubDate>
<description>Utility-scale solar additions set a record.</description></item>
<item><title>Sin link</title><link>no-es-una-direccion</link>
<pubDate>Tue, 29 Sep 2026 09:00:00 EST</pubDate><description>x</description></item>
</channel></rss>"""

STEO = """<html><body>
<p>Release Date: September 9, 2026 | Forecast Completed: September 3, 2026</p>
<h1>Forecast overview</h1>
<ul><li><strong>Global oil prices. </strong>Global oil prices rose to an average of $91 per barrel
in August, $7/b higher than in July, in response to falling global inventories that we estimate
have decreased by 400 million barrels so far this year.</li></ul>
<ul><li><strong>Natural gas storage. </strong>U.S. natural gas inventories are on track to be above
the five-year average at the start of winter, totaling 3,969 billion cubic feet on October 31,
2026, which is 5% above the five-year average for that date.</li></ul>
<ul><li>Punto sin tema en negrita que no debería entrar porque no se sabe de qué habla.</li></ul>
</body></html>""".encode("utf-8")

bajados = []


def _bajar_falso(url):
    bajados.append(url)
    return RSS if url.endswith(".xml") else STEO


_bajar_real = pubs._bajar
pubs._bajar = _bajar_falso
try:
    arts = pubs.bajar_rss(pubs.FUENTES["tie"])
    check(len(arts) == 2, "del feed salen los artículos con link válido (y se descarta el roto)")
    check(arts[0]["titulo"].startswith("U.S. exports of propane"),
          "lo de hidrocarburos queda primero")
    check(arts[0]["fecha"] == "2026-10-01", "fecha del RSS a AAAA-MM-DD")
    check(arts[0]["link"].startswith("https://www.eia.gov/todayinenergy/"), "link del artículo")

    steo = pubs.bajar_steo(pubs.FUENTES["steo"])
    check(len(steo) == 2, "del STEO salen los puntos con tema en negrita")
    check(steo[0]["titulo"] == "Global oil prices", "el tema del punto es el título")
    check(steo[0]["resumen"].count("Global oil prices") == 1,
          "la cita no repite el título dos veces")
    check(steo[0]["fecha"] == "2026-09-09", 'fecha "September 9, 2026" a AAAA-MM-DD')

    todas, fallas = pubs.traer()
    check(not fallas and len(todas) == 4, "traer() junta las dos fuentes")
    check(all(x["fuente_nombre"] for x in todas), "cada publicación sabe de dónde salió")

    dbpub = almacen.conectar(os.path.join(TMP, "pubs.db"))
    check(len(pubs.guardar(dbpub, todas)) == 4, "la primera vez son todas nuevas")
    check(len(pubs.guardar(dbpub, todas)) == 0, "la segunda vez ninguna es nueva")
    dbpub.close()

    bloques = informe.bloques_publicaciones(todas)
    check(bloques[0][0] == "heading" and bloques[1][0] == "callout",
          "la sección arranca con título y aviso")
    check("no texto del Instituto" in bloques[1][1]["text"], "el aviso dice que son citas ajenas")
    check(sum(1 for t, _ in bloques if t == "paragraph") == 4,
          "un bloque por publicación (se borran de a una en el editor)")
    texto = bloques[2][1]["text"]
    check(texto.count('"') == 2 and "[Ver en la EIA](https://" in texto,
          "cada cita va entre comillas y con su link")
    check(informe.bloques_publicaciones([]) == [], "sin publicaciones no hay sección")
finally:
    pubs._bajar = _bajar_real

# Una fuente caída no rompe nada.
pubs._bajar = lambda url: (_ for _ in ()).throw(pubs.PublicacionesError("se cayó"))
try:
    vacias, fallas = pubs.traer()
    check(vacias == [] and len(fallas) == 2, "si fallan las fuentes, traer() avisa y no explota")
finally:
    pubs._bajar = _bajar_real

bloques = informe.armar_bloques(
    [{"clave": "gas_exp_usa", "definicion": registro.SERIES["gas_exp_usa"],
      "datos": datos, "stats": informe.analizar(datos, registro.SERIES["gas_exp_usa"]),
      "revisiones": []}],
    publicaciones=[], fallas_publicaciones=[("tie", "no se pudo salir a internet")])
avisos = [d["text"] for t, d in bloques if t == "callout"]
check(any("No se pudo leer lo que publicó la EIA" in a for a in avisos),
      "si no se pudieron traer las citas, el borrador lo dice")
check(any("no se pudo salir a internet" in a for a in avisos), "y dice por qué")
bloques_ok = informe.armar_bloques(
    [{"clave": "gas_exp_usa", "definicion": registro.SERIES["gas_exp_usa"],
      "datos": datos, "stats": informe.analizar(datos, registro.SERIES["gas_exp_usa"]),
      "revisiones": []}], publicaciones=[], fallas_publicaciones=[])
check(not any("No se pudo leer" in d["text"] for t, d in bloques_ok if t == "callout"),
      "sin fallas no aparece el aviso")

check(pubs.recortar("a" * 400, 100).endswith("…"), "las citas largas se recortan y se marca")
check(pubs.recortar("corta") == "corta", "las citas cortas quedan enteras")
check(pubs._fecha("cualquier cosa") == "cualquier cosa", "una fecha rara no se inventa")

print(f"\n{ok} chequeos OK, {fallos} fallas")
sys.exit(1 if fallos else 0)
