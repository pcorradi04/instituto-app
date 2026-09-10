"""
Test automático de la plataforma — recorre el flujo completo del panel
(login, crear post, los cinco tipos de bloque, editar, reordenar, publicar,
buscar, borrar) sobre una base de datos TEMPORAL. No toca instance/instituto.db.

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

# --- crear y editar post -------------------------------------------------
r = c.post("/admin/posts", data={"title": "Título de prueba: Ñandú & Cía"})
pid = int(re.search(r"/admin/posts/(\d+)/edit", r.headers["Location"]).group(1))
db = appmod.sqlite3.connect(os.environ["DB_PATH"])
db.row_factory = appmod.sqlite3.Row
slug = db_row("SELECT slug FROM posts WHERE id=?", pid)["slug"]
ok(slug == "titulo-de-prueba-nandu-cia", "post creado, slug con ñ y tildes: " + slug)
ok(anon.get("/post/" + slug).status_code == 404, "borrador invisible sin login")
r = c.get("/post/" + slug)
ok(r.status_code == 200 and "BORRADOR" in text(r), "borrador visible logueado")
r = c.post(f"/admin/posts/{pid}", data={"title": "Título editado", "eyebrow": "Prueba", "dek": "Copete", "accent": "navy"},
           follow_redirects=True)
ok("Post actualizado" in text(r), "datos generales guardados")
slug = db_row("SELECT slug FROM posts WHERE id=?", pid)["slug"]
ok(slug == "titulo-editado", "borrador nunca publicado: la URL sigue al título -> " + slug)
c.post(f"/admin/posts/{pid}", data={"title": "Título editado", "accent": "fucsia"})
ok(db_row("SELECT accent FROM posts WHERE id=?", pid)["accent"] == "blue", "acento fuera de paleta -> blue")
ok(db_row("SELECT slug FROM posts WHERE id=?", pid)["slug"] == "titulo-editado",
   "mismo título -> slug estable (no se agrega -2 a sí mismo)")


# --- bloques -------------------------------------------------------------
def add(type_, **fields):
    # Se mandan también campos "ruido" de los otros sub-formularios, como
    # pasaría si el JS que los deshabilita fallara: el server debe ignorarlos.
    data = {"type": type_, "heading_title": "RUIDO", "chart_title": "RUIDO", "image_url": "RUIDO",
            "paragraph_text": "RUIDO", "callout_text": "RUIDO"}
    data.update(fields)
    r = c.post(f"/admin/posts/{pid}/blocks", data=data, follow_redirects=True)
    assert r.status_code == 200


add("heading", heading_tag="Sección uno", heading_title="Primer título")
add("paragraph", paragraph_text="Texto con **negrita** y *itálica*.\n\nSegundo párrafo <script>alert(1)</script>")
add("callout", callout_color="navy", callout_text="Destacado")
add("chart", chart_chart_type="line", chart_title="Gráfico", chart_subtitle="sub", chart_source="Fuente X",
    chart_color="orange", chart_series_names="A, B", chart_table="Ene | 1 | 2.5\nFeb | 3 |\nMar | x | 4")
add("image", image_url="https://example.com/a.png", image_caption="Epígrafe")
add("heading", heading_tag="Sección dos", heading_title="Segundo título")
blocks = appmod.get_post_blocks(db, pid)
ok([b["type"] for b in blocks] == ["heading", "paragraph", "callout", "chart", "image", "heading"], "6 bloques en orden")
ok(blocks[0]["data"]["title"] == "Primer título", "prefijo heading_ aislado del ruido de otros sub-formularios")
ok(blocks[3]["data"]["title"] == "Gráfico" and blocks[3]["data"]["labels"] == ["Ene", "Feb", "Mar"]
   and blocks[3]["data"]["series"] == [[1.0, 3.0, None], [2.5, None, 4.0]],
   "gráfico parseado, huecos y no-números -> null: " + json.dumps(blocks[3]["data"]["series"]))
ok(blocks[4]["data"]["url"] == "https://example.com/a.png", "prefijo image_ aislado")
r = c.post(f"/admin/posts/{pid}/blocks", data={"type": "evil"}, follow_redirects=True)
ok("inválido" in text(r), "tipo de bloque inválido rechazado")

html = text(c.get("/post/" + slug))
ok('<span class="num">I</span>' in html and '<span class="num">II</span>' in html, "numeración romana I, II")
ok("<b>negrita</b>" in html and "<i>itálica</i>" in html, "negrita/itálica renderizadas")
ok("<script>alert(1)</script>" not in html and "&lt;script&gt;" in html, "HTML escrito por el usuario queda escapado (XSS)")
ok('id="chart-' in html and "series_names" in html and '"A"' in html, "definición del gráfico pasada a Chart.js")
ok('class="callout navy"' in html, "callout navy")

bid = blocks[1]["id"]
r = c.post(f"/admin/posts/{pid}/blocks/{bid}", data={"text": "Texto nuevo"}, follow_redirects=True)
ok("Bloque actualizado" in text(r), "bloque editado")
ok(appmod.get_post_blocks(db, pid)[1]["data"]["text"] == "Texto nuevo", "edición persistida")
b0 = blocks[0]["id"]
c.post(f"/admin/posts/{pid}/blocks/{b0}/move/down")
ok([b["type"] for b in appmod.get_post_blocks(db, pid)][:2] == ["paragraph", "heading"], "mover abajo")
c.post(f"/admin/posts/{pid}/blocks/{b0}/move/up")
ok([b["type"] for b in appmod.get_post_blocks(db, pid)][:2] == ["heading", "paragraph"], "mover arriba")
c.post(f"/admin/posts/{pid}/blocks/{b0}/move/up")
ok(appmod.get_post_blocks(db, pid)[0]["type"] == "heading", "mover arriba en el tope: sin cambios")
c.post(f"/admin/posts/{pid}/blocks/{blocks[4]['id']}/delete")
ok(len(appmod.get_post_blocks(db, pid)) == 5, "bloque borrado")
ehtml = text(c.get(f"/admin/posts/{pid}/edit"))
ok("Ene | 1 | 2.5\nFeb | 3 | \nMar |  | 4" in ehtml, "tabla del gráfico reconstruida para reeditar (sin .0)")

# --- imágenes subidas ----------------------------------------------------
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
n_before = len(appmod.get_post_blocks(db, pid))
r = c.post(f"/admin/posts/{pid}/blocks",
           data={"type": "image", "image_caption": "Foto", "image_url": "",
                 "image_file": (io.BytesIO(PNG), "Foto de Prueba.PNG")},
           content_type="multipart/form-data", follow_redirects=True)
img_block = appmod.get_post_blocks(db, pid)[-1]
img_url = img_block["data"]["url"]
ok(img_block["type"] == "image" and img_url.startswith("/uploads/") and img_url.endswith("-foto_de_prueba.png"),
   "imagen subida -> bloque con URL local: " + img_url)
r = anon.get(img_url)
ok(r.status_code == 200 and r.mimetype == "image/png" and r.data == PNG, "la imagen subida se sirve públicamente como image/png")
ok(os.path.isfile(os.path.join(appmod.UPLOAD_DIR, os.path.basename(img_url))), "archivo guardado en UPLOAD_DIR (al lado de la base)")
r = c.post(f"/admin/posts/{pid}/blocks",
           data={"type": "image", "image_file": (io.BytesIO(b"MZ esto no es una imagen"), "virus.png")},
           content_type="multipart/form-data", follow_redirects=True)
ok("no parece una imagen" in text(r) and len(appmod.get_post_blocks(db, pid)) == n_before + 1,
   "archivo que no es imagen: rechazado aunque se llame .png")
r = c.post(f"/admin/posts/{pid}/blocks", data={"type": "image", "image_url": "", "image_caption": "sin nada"}, follow_redirects=True)
ok("subí un archivo o pegá una URL" in text(r) and len(appmod.get_post_blocks(db, pid)) == n_before + 1,
   "imagen sin archivo ni URL: rechazada")
r = c.post(f"/admin/posts/{pid}/blocks/{img_block['id']}",
           data={"caption": "Foto nueva", "url": img_url, "file": (io.BytesIO(JPG), "otra.jpeg")},
           content_type="multipart/form-data", follow_redirects=True)
b_new = appmod.get_post_blocks(db, pid)[-1]
ok(b_new["data"]["url"].endswith("-otra.jpg") and b_new["data"]["caption"] == "Foto nueva",
   "editar bloque con archivo nuevo reemplaza la URL (extensión según contenido real)")
big = b"\x89PNG\r\n\x1a\n" + b"\x00" * (11 * 1024 * 1024)
r = c.post(f"/admin/posts/{pid}/blocks",
           data={"type": "image", "image_file": (io.BytesIO(big), "grande.png")},
           content_type="multipart/form-data", follow_redirects=True)
ok("demasiado grande" in text(r) and len(appmod.get_post_blocks(db, pid)) == n_before + 1,
   "imagen de 11 MB: rechazada con mensaje claro")
ok(anon.get("/uploads/../app.py").status_code == 404, "no se puede salir de la carpeta de uploads")
ehtml = text(c.get(f"/admin/posts/{pid}/edit"))
ok('name="image_file"' in ehtml and 'name="file"' in ehtml and ehtml.count('enctype="multipart/form-data"') >= 2
   and f'<img src="{b_new["data"]["url"]}"' in ehtml, "editor: campos de subida, formularios multipart y vista previa de la imagen")

# --- publicar, buscar, borrar --------------------------------------------
r = c.post(f"/admin/posts/{pid}/publish", follow_redirects=True)
ok("Post publicado" in text(r), "publicado")
r = anon.get("/post/" + slug)
ok(r.status_code == 200 and "BORRADOR" not in text(r), "visible públicamente")
c.post(f"/admin/posts/{pid}", data={"title": "Título cambiado después de publicar", "accent": "navy"})
ok(db_row("SELECT slug FROM posts WHERE id=?", pid)["slug"] == "titulo-editado",
   "ya publicado: el slug se congela aunque cambie el título")
ok("Título cambiado" in text(anon.get("/?q=cambiado")), "búsqueda por título")
ok("No encontramos" in text(anon.get("/?q=zzzz")), "búsqueda sin resultados")
c.post(f"/admin/posts/{pid}/publish")
p2 = db_row("SELECT status, published_at FROM posts WHERE id=?", pid)
ok(p2["status"] == "draft" and p2["published_at"], "despublicado conserva la fecha original")
r = c.post("/admin/posts", data={"title": "Título editado"})
pid2 = int(re.search(r"/(\d+)/edit", r.headers["Location"]).group(1))
ok(db_row("SELECT slug FROM posts WHERE id=?", pid2)["slug"] == "titulo-editado-2", "slug duplicado -> sufijo -2")
c.post(f"/admin/posts/{pid}/delete")
ok(db_row("SELECT count(*) c FROM blocks WHERE post_id=?", pid)["c"] == 0, "borrar post borra sus bloques")
ok(db_row("SELECT count(*) c FROM posts WHERE id=?", pid)["c"] == 0, "post borrado")
ok(c.get("/admin/posts/9999/edit").status_code == 404, "404 post inexistente")
ok(anon.get("/post/no-existe").status_code == 404, "404 slug inexistente")
c.get("/admin/logout")
ok(c.get("/admin/").status_code == 302, "logout efectivo")

db.close()
print("\nRESULTADO:", "TODO OK" if fails == 0 else f"{fails} FALLAS")
sys.exit(1 if fails else 0)
