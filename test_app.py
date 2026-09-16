"""
Test automático de la plataforma — recorre el flujo completo del panel
(login, crear post, guardar desde el editor visual con los cinco tipos de
bloque, reordenar, subir imágenes, publicar, buscar, borrar) sobre una base
de datos TEMPORAL. No toca instance/instituto.db.

Correr después de cualquier cambio en app.py o en los templates:

    python test_app.py

Si todo está bien termina con "RESULTADO: TODO OK". Si algo falla, cada
línea FAIL dice qué se esperaba.
"""
import io
import json
import os
import re
import sys
import tempfile

# La base temporal se define ANTES de importar app, porque app.py lee
# DB_PATH al importarse.
TMP_DIR = tempfile.mkdtemp(prefix="instituto-test-")
os.environ["DB_PATH"] = os.path.join(TMP_DIR, "test.db")
os.environ["ADMIN_PASSWORD"] = "clave-de-test"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as appmod  # noqa: E402

app = appmod.app
app.config["TESTING"] = True
PW = "clave-de-test"

# Los mails de aviso no se mandan: se capturan acá para revisarlos.
SENT = []
appmod.send_email_async = lambda subject, body: SENT.append((subject, body))

c = app.test_client()       # sesión de administrador
anon = app.test_client()    # visitante sin login
fails = 0


def ok(cond, msg):
    global fails
    print(("OK   " if cond else "FAIL ") + msg)
    if not cond:
        fails += 1


def text(r):
    return r.get_data(as_text=True)


def db_row(sql, *params):
    return db.execute(sql, params).fetchone()


def save(payload, client=None):
    return (client or c).post(f"/admin/posts/{pid}/save", data=json.dumps(payload),
                              content_type="application/json")


def blocks():
    return appmod.get_post_blocks(db, pid)


# --- login y seguridad básica --------------------------------------------
r = c.get("/")
ok(r.status_code == 200 and "Todavía no hay posts" in text(r), "portada vacía")
r = c.get("/admin/")
ok(r.status_code == 302 and "/admin/login" in r.headers["Location"], "admin sin login redirige a login")
r = c.post("/admin/login", data={"password": "nope"}, follow_redirects=True)
ok("Clave incorrecta" in text(r), "clave incorrecta rechazada")
r = c.post("/admin/login?next=https://evil.com", data={"password": PW})
ok(r.status_code == 302 and r.headers["Location"].endswith("/admin/"), "next externo ignorado")
c.get("/admin/logout")
r = c.post("/admin/login?next=//evil.com", data={"password": PW})
ok(r.headers["Location"].endswith("/admin/"), "next con doble barra ignorado")
c.get("/admin/logout")
r = c.post("/admin/login?next=/admin/", data={"password": PW})
ok(r.headers["Location"].endswith("/admin/"), "next interno respetado")
ok("SameSite=Lax" in r.headers.get("Set-Cookie", "") and "HttpOnly" in r.headers.get("Set-Cookie", ""),
   "cookie de sesión SameSite=Lax + HttpOnly")

# --- crear post y abrir el editor ----------------------------------------
r = c.post("/admin/posts", data={"title": "Título de prueba: Ñandú & Cía"})
pid = int(re.search(r"/admin/posts/(\d+)/edit", r.headers["Location"]).group(1))
db = appmod.sqlite3.connect(os.environ["DB_PATH"])
db.row_factory = appmod.sqlite3.Row
slug = db_row("SELECT slug FROM posts WHERE id=?", pid)["slug"]
ok(slug == "titulo-de-prueba-nandu-cia", "post creado, slug con ñ y tildes: " + slug)
ok(anon.get("/post/" + slug).status_code == 404, "borrador invisible sin login")
r = c.get("/post/" + slug)
ok(r.status_code == 200 and "BORRADOR" in text(r), "borrador visible logueado")
ehtml = text(c.get(f"/admin/posts/{pid}/edit"))
ok('id="blocks"' in ehtml and "charts.js" in ehtml and "const INITIAL" in ehtml and "Editando: Título de prueba" in ehtml,
   "editor visual: página con el post inicial, charts.js y el estado en JSON")
ok(anon.get(f"/admin/posts/{pid}/edit").status_code == 302, "editor requiere login")

# --- guardar desde el editor: datos generales + los 5 tipos de bloque ----
BLOCKS = [
    {"type": "heading", "data": {"tag": "Sección uno", "title": "Primer título"}},
    {"type": "paragraph", "data": {"text": "Texto con **negrita** y *itálica*.\n\nSegundo párrafo <script>alert(1)</script>"}},
    {"type": "callout", "data": {"color": "navy", "text": "Destacado"}},
    {"type": "chart", "data": {"chart_type": "line", "title": "Gráfico", "subtitle": "sub", "source": "Fuente X",
                               "color": "orange", "series_names": "A, B", "table": "Ene | 1 | 2.5\nFeb | 3 |\nMar | x | 4"}},
    {"type": "image", "data": {"url": "https://example.com/a.png", "caption": "Epígrafe"}},
    {"type": "heading", "data": {"tag": "Sección dos", "title": "Segundo título"}},
]
GENERAL = {"title": "Título editado", "eyebrow": "Prueba", "dek": "Copete", "author": "Autor de prueba", "accent": "navy"}
r = save({**GENERAL, "blocks": BLOCKS})
j = r.get_json() or {}
ok(r.status_code == 200 and j.get("ok") and j.get("slug") == "titulo-editado" and j.get("post_url") == "/post/titulo-editado",
   "guardar: responde ok; borrador nunca publicado -> la URL sigue al título")
slug = j.get("slug", slug)
ok(tuple(db_row("SELECT title, eyebrow, dek, author, accent FROM posts WHERE id=?", pid)) == ("Título editado", "Prueba", "Copete", "Autor de prueba", "navy"),
   "datos generales guardados (incluido el autor)")
bl = blocks()
ok([b["type"] for b in bl] == ["heading", "paragraph", "callout", "chart", "image", "heading"], "6 bloques en orden")
ok(bl[3]["data"]["labels"] == ["Ene", "Feb", "Mar"] and bl[3]["data"]["series"] == [[1.0, 3.0, None], [2.5, None, 4.0]]
   and bl[3]["data"]["series_names"] == ["A", "B"],
   "gráfico parseado desde texto: huecos y no-números -> null, series con nombre")
r = save({**GENERAL, "accent": "fucsia", "blocks": BLOCKS})
ok(db_row("SELECT accent, slug FROM posts WHERE id=?", pid)["accent"] == "blue", "acento fuera de paleta -> blue")
ok(db_row("SELECT slug FROM posts WHERE id=?", pid)["slug"] == "titulo-editado", "mismo título -> slug estable (no se agrega -2 a sí mismo)")
save({**GENERAL, "blocks": BLOCKS})

# --- payloads inválidos --------------------------------------------------
ok(c.post(f"/admin/posts/{pid}/save", data="esto no es json", content_type="text/plain").status_code == 400, "guardar sin JSON -> 400")
ok(save({"title": "x", "blocks": "nope"}).status_code == 400, "blocks que no es lista -> 400")
r = save({"title": "x", "blocks": [{"type": "evil", "data": {}}]})
ok(r.status_code == 400 and len(blocks()) == 6 and db_row("SELECT title FROM posts WHERE id=?", pid)["title"] == "Título editado",
   "tipo de bloque inválido -> 400 y no se guarda nada")
ok(save({"title": "x", "blocks": []}, client=anon).status_code == 302, "guardar sin login -> redirige a login")
ok(c.post("/admin/posts/9999/save", data="{}", content_type="application/json").status_code == 404, "guardar post inexistente -> 404")

# --- tabla de texto: separadores, decimales con coma, encabezado ---------
pt = appmod.parse_table
ok(pt("Mayo 2026;959,1;1.172\nJunio 2026;401,3;918")[:2] == (["Mayo 2026", "Junio 2026"], [[959.1, 401.3], [1172.0, 918.0]]),
   "tabla con punto y coma y números a la argentina (959,1 y 1.172)")
ok(pt('"Vista, Oil & Gas",569\nYPF,574.1')[2] == [["Vista, Oil & Gas", "569"], ["YPF", "574.1"]], "CSV con coma y celdas entre comillas")
ok(pt("Período\tEnergía\tINDEC\n2026-01\t1\t2")[:2] == (["2026-01"], [[1.0], [2.0]]), "pegado desde Excel (tabulación): la fila de encabezado se descarta")
ok(pt("Origen | Destino | valor\nGas | Chile | 340.8", "sankey")[2] == [["Gas", "Chile", "340.8"]],
   "sankey: encabezado de tres columnas descartado; la columna de texto del medio no confunde")
ok(pt("2026-05 | 959.1\n2026-07 | | 536.2")[0] == ["2026-05", "2026-07"], "una fila con celdas vacías no es encabezado (fan chart)")
ok(pt("a | 1,172.5 | 2")[1] == [[1172.5], [2.0]] and pt("a | 1.172,5")[2] == [["a", "1172.5"]], "miles a la inglesa (1,172.5) y a la argentina (1.172,5)")
ok(pt("") == ([], [], []) and pt("Etiqueta | Valor") == ([], [], []), "tabla vacía o solo encabezado: sin datos")

# --- tipos de gráfico: filas crudas, opciones, tipo desconocido -----------
BLOCKS2 = [
    {"type": "chart", "data": {"chart_type": "scatter", "table": "Crudo | 959.1 | 1172\nGas | 30.4 | 52",
                               "series_names": "Energía, INDEC", "options": {"diagonal": "si", "Clave Rara!": "x", "y_title": None, "unit": ""}}},
    {"type": "chart", "data": {"chart_type": "sankey", "table": "Gas 2025 | Chile | 340.8\nGas 2025 | Uruguay | 5.1"}},
    {"type": "chart", "data": {"chart_type": "inexistente", "table": "a | 1"}},
    {"type": "chart", "data": {"chart_type": "line", "title": "Vacío", "table": ""}},
    {"type": "image", "data": {"url": "", "caption": "sin imagen"}},
    {"type": "figure", "data": {"title": "Uso de IA", "subtitle": "% de encuestados", "note": "¹En 2017 la definición era distinta.", "source": "McKinsey",
                                "panels": [
                                    {"title": "Al menos 1 función", "chart_type": "line", "series_names": "Organizaciones", "table": "2018 | 47\n2019 | 58\n2020 | 50", "options": {"height": "260"}},
                                    {"title": "Fase de uso", "chart_type": "stacked_bar_100", "series_names": "Escalando, Piloto, Experimentando", "table": "2025 | 38 | 30 | 32\n2026 | 44 | 34 | 22"},
                                    {"chart_type": "line", "table": ""},
                                    {"chart_type": "line", "table": "de más | 1"}]}},
    {"type": "figure", "data": {"title": "Figura vacía", "panels": [{"chart_type": "line", "table": ""}]}},
    {"type": "chart", "data": {"chart_type": "bar_comparison", "title": "Con nota", "note": "Nota al pie del gráfico simple.", "table": "a | 1"}},
    {"type": "chart", "data": {"chart_type": "line", "title": "Colores", "color": "pastel_orange",
                               "colors": ["pastel_orange", "navy", "Mal!", "gold", "#1A2B3c", "#12345", "#GGGGGG"],
                               "table": "a | 1 | 2 | 3 | 4 | 5 | 6 | 7"}},
    {"type": "paragraph", "data": {"text": "Ver [el informe](https://indec.gob.ar/x?a=1&b=2) y www.enargas.gob.ar. Nada de javascript:alert(1) ni <a href=x>."}},
]
r = save({**GENERAL, "blocks": BLOCKS2})
bl = blocks()
ok(bl[8]["data"]["color"] == "pastel_orange" and bl[8]["data"]["colors"] == ["pastel_orange", "navy", "", "gold", "#1a2b3c", "", ""],
   "color por serie: claves de la paleta o #RRGGBB libre (en minúsculas); lo inválido queda vacío (color por defecto)")
r = save({**GENERAL, "blocks": [{"type": "chart", "data": {"chart_type": "bar_comparison", "color": "#ABCDEF", "table": "a | 1",
                                                            "colors": ["#%06x" % i for i in range(30)]}}]})
ok(blocks()[0]["data"]["color"] == "#abcdef" and len(blocks()[0]["data"]["colors"]) == 24,
   "color principal libre en #RRGGBB; la lista de colores se corta en 24")
r = save({**GENERAL, "blocks": BLOCKS2})
bl = blocks()
ok(bl[0]["data"]["colors"] == [] and bl[0]["data"]["color"] == "orange", "gráfico sin colores elegidos: lista vacía y principal por defecto")
fig = bl[5]["data"]
ok(bl[5]["type"] == "figure" and len(fig["panels"]) == 3 and fig["panels"][0]["labels"] == ["2018", "2019", "2020"]
   and fig["panels"][1]["series_names"] == ["Escalando", "Piloto", "Experimentando"] and fig["panels"][0]["options"] == {"height": "260"}
   and fig["note"].startswith("¹En 2017"), "figura: hasta 3 paneles, cada uno parseado como un gráfico completo, con nota al pie común")
ok(r.status_code == 200 and bl[0]["data"]["rows"] == [["Crudo", "959.1", "1172"], ["Gas", "30.4", "52"]],
   "scatter: se guardan las filas crudas (texto) además de labels/series")
ok(bl[0]["data"]["options"] == {"diagonal": "si"}, "opciones del gráfico: se guardan las válidas, se descartan claves raras y valores vacíos")
ok(bl[1]["data"]["rows"][0] == ["Gas 2025", "Chile", "340.8"] and bl[1]["data"]["series"][0] == [None, None],
   "sankey: una columna de texto en el medio no rompe el parseo")
ok(bl[2]["data"]["chart_type"] == "bar_comparison", "tipo de gráfico desconocido -> barras agrupadas")
html = text(c.get("/post/" + slug))
ok('"chart_type": "scatter"' in html and '"rows": [["Crudo", "959.1", "1172"]' in html and '"diagonal": "si"' in html,
   "el post recibe tipo, filas y opciones para charts.js")
ok(html.count('class="chart-wrap"') == 7 and "sin datos: no se muestra a los lectores" in html
   and 'src=""' not in html, "gráfico sin datos e imagen sin URL: no dejan cuadros vacíos (el admin ve un aviso)")
fid = bl[5]["id"]
ok('class="figure-grid cols-2"' in html and f'id="chart-{fid}-0"' in html and f'id="chart-{fid}-1"' in html and f'id="chart-{fid}-2"' not in html
   and "Al menos 1 función" in html and "¹En 2017 la definición" in html and '"id": "chart-' + str(fid) + '-1"' in html,
   "figura en el post: dos paneles lado a lado (el vacío no cuenta), títulos por panel, nota al pie y definiciones para charts.js")
ok("Figura vacía" not in html.split('id="comentarios"')[0].split("chart-card")[-1] and html.count("Figura sin datos") == 1,
   "figura sin ningún panel con datos: no se muestra (el admin ve el aviso)")
ok('class="chart-note">Nota al pie del gráfico simple.' in html, "nota al pie en un gráfico simple")
ok('"colors": ["pastel_orange", "navy", "", "gold", "#1a2b3c", "", ""]' in html, "el post recibe los colores por serie para charts.js")
ok(html.count('<a data-net=') == 3 and html.count("<svg") >= 4 and 'aria-label="Compartir en LinkedIn"' in html
   and '<span class="lbl">Copiar link</span>' in html, "compartir: logo de X, LinkedIn y WhatsApp más el botón de copiar con ícono")
js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "charts.js"), encoding="utf-8").read()
ok(all(g in js for g in ["group('Institucional'", "group('Vivos'", "group('Pastel'", "group('Tierra'", "group('Oscuros'", "group('Grises'"])
   and js.count("', '#") >= 60 and "window.chartColorSlots" in js and "onSeriesClick" in js and "data-si=" in js,
   "charts.js: paleta de 60+ colores en 6 grupos, colores por serie/bloque y clic sobre la serie (onSeriesClick, data-si)")
ok('<a href="https://indec.gob.ar/x?a=1&amp;b=2" target="_blank" rel="noopener">el informe</a>' in html
   and '<a href="http://www.enargas.gob.ar" target="_blank" rel="noopener">www.enargas.gob.ar</a>.' in html
   and 'href="javascript' not in html and '<a href=x>' not in html and "&lt;a href=x&gt;" in html,
   "links en párrafos: [texto](url) y URLs sueltas se vuelven clicables; javascript: y HTML crudo no")
ok(html.count('class="chart-wrap"') == 7, "7 cajas de gráfico con datos en el post")
ehtml = text(c.get(f"/admin/posts/{pid}/edit"))
ok('"panels": [' in ehtml and '"table": "2025 | 38 | 30 | 32\\n2026 | 44 | 34 | 22"' in ehtml and '"note": "\\u00b9En 2017' in ehtml,
   "editor: la figura vuelve con sus paneles como tablas de texto")
ok('data-mode="copy"' in html and 'data-mode="download"' in html and 'data-filename="grafico"' in html,
   "cada tarjeta de gráfico tiene botones de copiar y descargar PNG")
ok('class="hero"' not in html and 'class="post-head"' in html and html.count('class="chart-logo"') == 6,
   "post: sin la banda beige (encabezado dentro del cuerpo) y logo gris arriba a la derecha de cada gráfico")
ok('class="hero"' in text(anon.get("/")), "la portada conserva la banda beige")
ok('class="post-head"' in text(c.get(f"/admin/posts/{pid}/edit")) and 'class="hero"' not in text(c.get(f"/admin/posts/{pid}/edit")),
   "el editor refleja el mismo encabezado que el post")
ehtml = text(c.get(f"/admin/posts/{pid}/edit"))
ok('"table": "Gas 2025 | Chile | 340.8\\nGas 2025 | Uruguay | 5.1"' in ehtml, "editor: la tabla del Sankey vuelve con su columna de texto")
save({**GENERAL, "blocks": BLOCKS})

# --- render público del post ---------------------------------------------
html = text(c.get("/post/" + slug))
ok('<span class="num">I</span>' in html and '<span class="num">II</span>' in html, "numeración romana I, II")
ok("<b>negrita</b>" in html and "<i>itálica</i>" in html, "negrita/itálica renderizadas")
ok("<script>alert(1)</script>" not in html and "&lt;script&gt;" in html, "HTML escrito por el usuario queda escapado (XSS)")
ok('id="chart-' in html and "series_names" in html and '"A"' in html and "charts.js" in html, "definición del gráfico pasada a charts.js")
ok('class="callout navy"' in html, "callout navy")
ok('style="--accent:#1F4E5F"' in html, "el color de acento del post llega al CSS (--accent)")

# --- el editor devuelve lo guardado en forma editable --------------------
ehtml = text(c.get(f"/admin/posts/{pid}/edit"))
ok('"table": "Ene | 1 | 2.5\\nFeb | 3\\nMar | x | 4"' in ehtml and '"series_names": "A, B"' in ehtml,
   "editor: el gráfico vuelve como tabla de texto (las celdas vacías del final se omiten), y series como texto")
ok('style="--accent:#1F4E5F"' in ehtml, "editor: arranca con el acento del post")

# --- reordenar y borrar bloques = mandar otra lista -----------------------
rev = list(reversed(BLOCKS))
save({**GENERAL, "blocks": rev})
ok([b["type"] for b in blocks()] == [b["type"] for b in rev] and blocks()[0]["data"]["title"] == "Segundo título",
   "reordenar: el orden guardado es el que manda el editor")
save({**GENERAL, "blocks": BLOCKS[:-1]})
ok(len(blocks()) == 5, "borrar un bloque: guardar sin él lo elimina")
save({**GENERAL, "blocks": BLOCKS})

# --- imágenes subidas ----------------------------------------------------
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
r = c.post("/admin/upload", data={"file": (io.BytesIO(PNG), "Foto de Prueba.PNG")}, content_type="multipart/form-data")
img_url = (r.get_json() or {}).get("url", "")
ok(r.status_code == 200 and img_url.startswith("/uploads/") and img_url.endswith("-foto_de_prueba.png"),
   "subir imagen -> URL local: " + img_url)
r = anon.get(img_url)
ok(r.status_code == 200 and r.mimetype == "image/png" and r.data == PNG, "la imagen subida se sirve públicamente como image/png")
ok(os.path.isfile(os.path.join(appmod.UPLOAD_DIR, os.path.basename(img_url))), "archivo guardado en UPLOAD_DIR (al lado de la base)")
r = c.post("/admin/upload", data={"file": (io.BytesIO(b"MZ esto no es una imagen"), "virus.png")}, content_type="multipart/form-data")
ok(r.status_code == 400 and "no parece una imagen" in (r.get_json() or {}).get("error", ""),
   "archivo que no es imagen: rechazado aunque se llame .png")
r = c.post("/admin/upload", data={}, content_type="multipart/form-data")
ok(r.status_code == 400 and "ningún archivo" in (r.get_json() or {}).get("error", ""), "subir sin archivo -> error claro")
big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (11 * 1024 * 1024)
r = c.post("/admin/upload", data={"file": (io.BytesIO(big), "grande.png")}, content_type="multipart/form-data")
ok(r.status_code == 413 and "demasiado grande" in (r.get_json() or {}).get("error", ""), "imagen de 11 MB: 413 con mensaje en JSON")
ok(anon.post("/admin/upload", data={"file": (io.BytesIO(PNG), "x.png")}, content_type="multipart/form-data").status_code == 302,
   "subir sin login -> redirige a login")
ok(anon.get("/uploads/../app.py").status_code == 404, "no se puede salir de la carpeta de uploads")
save({**GENERAL, "blocks": BLOCKS + [{"type": "image", "data": {"url": img_url, "caption": "Foto"}}]})
html = text(c.get("/post/" + slug))
ok(f'<img src="{img_url}"' in html, "la imagen subida aparece en el post")

# --- publicar, buscar, despublicar ---------------------------------------
r = c.post(f"/admin/posts/{pid}/publish", data={"next": f"/admin/posts/{pid}/edit"})
ok(r.status_code == 302 and r.headers["Location"].endswith(f"/admin/posts/{pid}/edit"), "publicar desde el editor vuelve al editor")
r = anon.get("/post/" + slug)
ok(r.status_code == 200 and "BORRADOR" not in text(r), "visible públicamente")
ok(db_row("SELECT post_number FROM posts WHERE id=?", pid)["post_number"] == 1
   and '<div class="section-marker post-marker"><span class="num">1</span><span class="tag">Prueba</span></div>' in text(r),
   "primera publicación: recibe el N.º 1, mostrado en caja como los numerales de sección, con la etiqueta")
ok('class="section-marker card-marker"><span class="num">1</span>' in text(anon.get("/")), "la portada muestra el número de cada post en caja")
save({**GENERAL, "author": "", "blocks": BLOCKS})
ok('class="byline">Publicado el ' in text(anon.get("/post/" + slug)), "sin autor: 'Publicado el fecha', sin repetir el nombre del Instituto")
save({**GENERAL, "blocks": BLOCKS})
ok(anon.get("/favicon.ico").status_code == 302 and 'rel="icon"' in text(anon.get("/")), "favicon: ícono de la pestaña")
save({**GENERAL, "title": "Título cambiado después de publicar", "blocks": BLOCKS})
ok(db_row("SELECT slug FROM posts WHERE id=?", pid)["slug"] == "titulo-editado", "ya publicado: el slug se congela aunque cambie el título")
ok("Título cambiado" in text(anon.get("/?q=cambiado")), "búsqueda por título")
ok("No encontramos" in text(anon.get("/?q=zzzz")), "búsqueda sin resultados")
ok('style="--accent:#1F4E5F"' in text(anon.get("/")), "la portada pinta cada post con su acento")
# --- comentarios (modo por defecto: se publican al instante) --------------
from urllib.parse import urlparse  # noqa: E402
curl = "/post/" + slug + "/comentar"
html = text(anon.get("/post/" + slug))
ok('id="comentarios"' in html and 'name="website"' in html and "Compartir:" in html and "Por Autor de prueba" in html
   and " de 2026" in html and "se publican al instante" in html,
   "post publicado: sección de comentarios, campo trampa, compartir, firma de autor, fecha en español y aviso de moderación posterior")
r = anon.post(curl, data={"name": "Ana", "body": "Muy buen análisis, ¿tienen los datos por cuenca?", "website": ""}, follow_redirects=True)
ok("ya está publicado" in text(r), "comentario enviado: mensaje de gracias")
ok(db_row("SELECT status FROM comments WHERE name='Ana'")["status"] == "approved", "queda publicado al instante (moderación posterior)")
ok("Muy buen análisis" in text(app.test_client().get("/post/" + slug)), "se ve para el público sin pasar por el panel")
ok(len(SENT) == 1 and "Nuevo comentario de Ana" in SENT[0][0] and "Borrar:" in SENT[0][1] and "Aprobar:" not in SENT[0][1],
   "aviso por mail: nuevo comentario con link para borrar (sin 'aprobar': ya está publicado)")
anon.post(curl, data={"name": "Bot", "body": "compra esto ahora mismo", "website": "http://spam"})
ok(db_row("SELECT COUNT(*) AS c FROM comments WHERE name='Bot'")["c"] == 0, "campo trampa lleno: se descarta en silencio")
r = anon.post(curl, data={"name": "A", "body": "hola"}, follow_redirects=True)
ok("muy corto" in text(r) and db_row("SELECT COUNT(*) AS c FROM comments")["c"] == 1, "nombre o comentario muy cortos: rechazado con aviso")
ok(anon.post("/post/no-existe/comentar", data={"name": "Ana", "body": "hola hola"}).status_code == 404, "comentar en post inexistente -> 404")
ok("1 comentario" in text(anon.get("/")), "la portada muestra la cantidad de comentarios del post")
lhtml = text(c.get("/admin/comentarios"))
ok("Ana" in lhtml and "Título cambiado" in lhtml and "Borrar" in lhtml, "lista de comentarios en el panel, con el post al que pertenecen")
ok(anon.get("/admin/comentarios").status_code == 302, "lista de comentarios requiere login")
ok("pendiente" not in text(c.get("/admin/")), "dashboard: sin aviso de pendientes en moderación posterior")
r = anon.post(curl, data={"name": "Ana", "body": "Miren esto: https://www.argentina.gob.ar/energia, vale la pena."}, follow_redirects=True)
ok("Como tiene links" in text(r) and db_row("SELECT status FROM comments WHERE body LIKE 'Miren esto%'")["status"] == "pending",
   "comentario con link: queda para autorizar (anti-spam) y avisa por qué")
linkc = db_row("SELECT id FROM comments WHERE body LIKE 'Miren esto%'")["id"]
ok("1 comentario pendiente" in text(c.get("/admin/")), "el pendiente por link aparece en el dashboard")
c.post(f"/admin/comentarios/{linkc}/aprobar", data={"next": "/admin/comentarios"})
ok('<a href="https://www.argentina.gob.ar/energia" target="_blank" rel="nofollow noopener">https://www.argentina.gob.ar/energia</a>,' in text(app.test_client().get("/post/" + slug)),
   "aprobado: el link del comentario es clicable, con rel=nofollow y la coma afuera")
cid = db_row("SELECT id FROM comments WHERE name='Ana' AND body LIKE 'Muy buen%'")["id"]
r = c.post(curl, data={"body": "Sí, los publicamos la semana que viene.", "parent_id": str(cid)}, follow_redirects=True)
staff = db_row("SELECT * FROM comments WHERE is_staff=1")
ok(staff is not None and staff["status"] == "approved" and staff["parent_id"] == cid and staff["name"] == appmod.STAFF_NAME,
   "respuesta del equipo (logueado): firmada 'Instituto de Energía' y colgada del comentario")
phtml = text(app.test_client().get("/post/" + slug))
ok("Equipo del Instituto" not in phtml and 'class="comment reply staff"' in phtml and ".comment.staff" not in text(anon.get("/static/style.css"))
   and phtml.index("Muy buen análisis") < phtml.index("la semana que viene"),
   "la respuesta se ve debajo del original, como un comentario más (sin cajita ni distintivo)")
ok("cerrá la sesión" in text(c.get("/post/" + slug)), "logueado: el formulario avisa que firma como el Instituto y ofrece cerrar la sesión")
ok(len([m for m in SENT if "la semana que viene" in m[1]]) == 0, "las respuestas del equipo no generan aviso")
anon.post(curl, data={"name": "Ana", "body": "Gracias, quedo atenta.", "parent_id": str(staff["id"])})
ok(db_row("SELECT parent_id FROM comments WHERE body LIKE 'Gracias, quedo%'")["parent_id"] == cid,
   "responder a una respuesta cuelga del comentario original (un solo nivel)")
for i in range(13):   # ya van 3 de Ana desde esta IP (uno con link); el límite es 15 cada 10 minutos
    anon.post(curl, data={"name": "Ana", "body": f"comentario número {i} de prueba"})
r = anon.post(curl, data={"name": "Ana", "body": "este ya es demasiado"}, follow_redirects=True)
ok("Esperá unos minutos" in text(r) and db_row("SELECT COUNT(*) AS c FROM comments WHERE body LIKE 'este ya es%'")["c"] == 0,
   "más de 15 comentarios en 10 minutos desde la misma IP: rechazado")
ok(db_row("SELECT COUNT(*) AS c FROM comments WHERE ip = '127.0.0.1' AND is_staff = 0")["c"] == 15, "los 15 anteriores sí entraron")
mail = [m for m in SENT if "comentario número 5 de" in m[1]][0]
delete_path = urlparse(re.search(r"Borrar:\s+(\S+)", mail[1]).group(1)).path
r = app.test_client().get(delete_path)
ok(r.status_code == 200 and "Comentario borrado" in text(r) and db_row("SELECT COUNT(*) AS c FROM comments WHERE body LIKE '%número 5 de%'")["c"] == 0,
   "link del mail: borra sin estar logueado")
ok(app.test_client().get(delete_path).status_code == 404, "link ya usado sobre un comentario borrado: 'ya no existe'")
ok(anon.get("/moderar/token-falso.abc").status_code == 404, "token inventado: 404")
# --- modo de moderación previa (COMMENTS_MODERATION=pre) -------------------
appmod.COMMENTS_MODERATION = "pre"
db.execute("DELETE FROM comments WHERE is_staff = 0 AND body LIKE 'comentario número%'")
db.commit()
r = anon.post(curl, data={"name": "Luz", "body": "Comentario en modo previo."}, follow_redirects=True)
ok("cuando lo revise" in text(r) and db_row("SELECT status FROM comments WHERE name='Luz'")["status"] == "pending", "modo previo: queda pendiente y avisa")
ok("Comentario en modo previo" not in text(app.test_client().get("/post/" + slug)), "modo previo: no se ve para el público")
ahtml = text(c.get("/post/" + slug))
ok("Comentario en modo previo" in ahtml and "Pendiente de aprobación" in ahtml and "Aprobar" in ahtml,
   "modo previo: el admin lo ve marcado en el post, con botón Aprobar")
ok("1 comentario pendiente" in text(c.get("/admin/")) and "Comentarios (1)" in text(c.get("/admin/")), "modo previo: aviso de pendientes en el dashboard")
mail = [m for m in SENT if "modo previo" in m[1]][0]
ok("para aprobar" in mail[0] and "Aprobar:" in mail[1], "modo previo: el mail trae el link de aprobar")
approve_path = urlparse(re.search(r"Aprobar:\s+(\S+)", mail[1]).group(1)).path
r = app.test_client().get(approve_path)
ok(r.status_code == 200 and "Comentario aprobado" in text(r) and db_row("SELECT status FROM comments WHERE name='Luz'")["status"] == "approved",
   "link del mail: aprueba sin estar logueado")
luz = db_row("SELECT id FROM comments WHERE name='Luz'")["id"]
r = c.post(f"/admin/comentarios/{luz}/aprobar", data={"next": f"/post/{slug}#c{luz}"})
ok(r.status_code == 302 and r.headers["Location"].endswith(f"/post/{slug}#c{luz}"), "aprobar desde el post vuelve al post")
appmod.COMMENTS_MODERATION = "post"
c.post(f"/admin/comentarios/{cid}/borrar", data={"next": "/admin/comentarios"})
ok(db_row("SELECT COUNT(*) AS c FROM comments WHERE id=? OR parent_id=?", cid, cid)["c"] == 0, "borrar un comentario borra también sus respuestas")

r = c.post(f"/admin/posts/{pid}/publish", data={"next": "https://evil.com"})
ok(r.headers["Location"].endswith("/admin/"), "despublicar con next externo -> dashboard")
ok(anon.post(curl, data={"name": "Ana", "body": "hola hola hola"}).status_code == 404, "no se puede comentar un post despublicado")
p2 = db_row("SELECT status, published_at, post_number FROM posts WHERE id=?", pid)
ok(p2["status"] == "draft" and p2["published_at"] and p2["post_number"] == 1, "despublicado conserva la fecha original y el número")

# --- slug duplicado, borrar, 404s, logout --------------------------------
r = c.post("/admin/posts", data={"title": "Título editado"})
pid2 = int(re.search(r"/(\d+)/edit", r.headers["Location"]).group(1))
ok(db_row("SELECT slug FROM posts WHERE id=?", pid2)["slug"] == "titulo-editado-2", "slug duplicado -> sufijo -2")
c.post(f"/admin/posts/{pid2}/publish")
ok(db_row("SELECT post_number FROM posts WHERE id=?", pid2)["post_number"] == 2, "el segundo post publicado recibe el N.º 2")
c.post(f"/admin/posts/{pid}/delete")
ok(db_row("SELECT count(*) c FROM blocks WHERE post_id=?", pid)["c"] == 0, "borrar post borra sus bloques")
ok(db_row("SELECT count(*) c FROM comments WHERE post_id=?", pid)["c"] == 0, "borrar post borra sus comentarios")
ok(db_row("SELECT count(*) c FROM posts WHERE id=?", pid)["c"] == 0, "post borrado")
ok(c.get("/admin/posts/9999/edit").status_code == 404, "404 post inexistente")
ok(anon.get("/post/no-existe").status_code == 404, "404 slug inexistente")
c.get("/admin/logout")
ok(c.get("/admin/").status_code == 302, "logout efectivo")

db.close()
print("\nRESULTADO:", "TODO OK" if fails == 0 else f"{fails} FALLAS")
sys.exit(1 if fails else 0)
