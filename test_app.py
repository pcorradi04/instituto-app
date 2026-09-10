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
GENERAL = {"title": "Título editado", "eyebrow": "Prueba", "dek": "Copete", "accent": "navy"}
r = save({**GENERAL, "blocks": BLOCKS})
j = r.get_json() or {}
ok(r.status_code == 200 and j.get("ok") and j.get("slug") == "titulo-editado" and j.get("post_url") == "/post/titulo-editado",
   "guardar: responde ok; borrador nunca publicado -> la URL sigue al título")
slug = j.get("slug", slug)
ok(tuple(db_row("SELECT title, eyebrow, dek, accent FROM posts WHERE id=?", pid)) == ("Título editado", "Prueba", "Copete", "navy"),
   "datos generales guardados")
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
ok('"table": "Ene | 1 | 2.5\\nFeb | 3 | \\nMar |  | 4"' in ehtml and '"series_names": "A, B"' in ehtml,
   "editor: el gráfico vuelve como tabla de texto (sin .0) y series como texto")
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
save({**GENERAL, "title": "Título cambiado después de publicar", "blocks": BLOCKS})
ok(db_row("SELECT slug FROM posts WHERE id=?", pid)["slug"] == "titulo-editado", "ya publicado: el slug se congela aunque cambie el título")
ok("Título cambiado" in text(anon.get("/?q=cambiado")), "búsqueda por título")
ok("No encontramos" in text(anon.get("/?q=zzzz")), "búsqueda sin resultados")
ok('style="--accent:#1F4E5F"' in text(anon.get("/")), "la portada pinta cada post con su acento")
r = c.post(f"/admin/posts/{pid}/publish", data={"next": "https://evil.com"})
ok(r.headers["Location"].endswith("/admin/"), "despublicar con next externo -> dashboard")
p2 = db_row("SELECT status, published_at FROM posts WHERE id=?", pid)
ok(p2["status"] == "draft" and p2["published_at"], "despublicado conserva la fecha original")

# --- slug duplicado, borrar, 404s, logout --------------------------------
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
