"""
Instituto de Energía — plataforma de posts
============================================
App propia (sin WordPress) para publicar reportes/posts con una estructura
y un lenguaje visual fijos, pero contenido libre. Pensada para correr con
lo mínimo posible: Flask + SQLite (nada de bases de datos externas).

Cómo correrla local:
    pip install -r requirements.txt
    python app.py
    -> abre http://127.0.0.1:5000
    -> admin en http://127.0.0.1:5000/admin  (clave: ADMIN_PASSWORD en .env, o "energia2026" por defecto)

Ver README.md para instrucciones de deploy a un hosting real.
"""

import os
import re
import json
import sqlite3
import unicodedata
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask, request, session, redirect, url_for, render_template,
    g, flash, abort, send_from_directory
)
from markupsafe import escape
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Si existe un archivo .env al lado de app.py, carga sus variables
# (ADMIN_PASSWORD, SECRET_KEY, ...). Es opcional: si python-dotenv no está
# instalado, simplemente se usan las variables de entorno del sistema.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass
# Si querés que la base viva en otro lado (ej. un disco persistente del
# hosting), definí DB_PATH como variable de entorno.
DB_PATH = os.environ.get("DB_PATH") or os.path.join(BASE_DIR, "instance", "instituto.db")

# Carpeta donde se guardan las imágenes subidas desde el panel. Por defecto
# al lado de la base (instance/uploads/), así un backup de instance/ se lleva
# todo el contenido del sitio junto.
UPLOAD_DIR = os.environ.get("UPLOAD_DIR") or os.path.join(os.path.dirname(DB_PATH), "uploads")
MAX_UPLOAD_MB = 10

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "clave-de-desarrollo-cambiar-en-produccion")
# La cookie de sesión no viaja en formularios enviados desde OTRO sitio:
# protege los botones del panel (borrar, publicar...) contra CSRF sin
# necesidad de tokens en cada formulario.
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
# En producción (con HTTPS) poné SECURE_COOKIES=1 en el .env: la cookie de
# sesión solo viaja cifrada. Apagado por defecto para que funcione en local.
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SECURE_COOKIES", "0") == "1"
# Tope de tamaño para cualquier request; en la práctica, el máximo de una
# imagen subida. Si se pasa, Flask corta con un error 413 que se maneja abajo.
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

# Clave del panel de administración. En producción, definila como variable
# de entorno ADMIN_PASSWORD en vez de dejarla acá.
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get("ADMIN_PASSWORD", "energia2026"))

ACCENTS = {
    "blue":   {"label": "Azul (institucional)", "hex": "#0000CC"},
    "orange": {"label": "Naranja (petróleo)",    "hex": "#C1622E"},
    "navy":   {"label": "Navy (gas)",            "hex": "#1F4E5F"},
    "maroon": {"label": "Granate (alerta)",      "hex": "#A63D2F"},
}
CHART_TYPES = {
    "bar_comparison": "Barras comparativas (hasta 2 series)",
    "line":           "Línea temporal (hasta 3 series)",
    "stacked_area":   "Áreas apiladas",
}
BLOCK_TYPES = ["heading", "paragraph", "callout", "chart", "image"]


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        eyebrow TEXT DEFAULT '',
        dek TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'draft',
        accent TEXT NOT NULL DEFAULT 'blue',
        author TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        published_at TEXT
    );
    CREATE TABLE IF NOT EXISTS blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
        position INTEGER NOT NULL,
        type TEXT NOT NULL,
        data TEXT NOT NULL
    );
    """)
    db.commit()
    db.close()


# Crear las tablas al importar el módulo (no solo con `python app.py`): así
# también existen cuando la app arranca con gunicorn en producción.
init_db()


# ---------------------------------------------------------------------------
# Autenticación (panel admin — una sola clave compartida, simple a propósito)
# ---------------------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        pw = request.form.get("password", "")
        if check_password_hash(ADMIN_PASSWORD_HASH, pw):
            session["is_admin"] = True
            nxt = request.args.get("next", "")
            # Solo rutas internas del sitio (un link armado a mano no puede
            # mandarte a otro dominio después de loguearte).
            if not nxt.startswith("/") or nxt.startswith("//"):
                nxt = url_for("admin_dashboard")
            return redirect(nxt)
        flash("Clave incorrecta.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Helpers de contenido
# ---------------------------------------------------------------------------

def slugify(text):
    """Convierte un título en su URL: "Diseño y año" -> "diseno-y-ano"."""
    # NFKD separa cada letra acentuada en letra + acento; se descarta el acento.
    # Cubre tildes, diéresis y la ñ (que antes se perdía: "Ñandú" -> "andu").
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "post"


def unique_slug(db, base, exclude_id=None):
    """Slug único entre todos los posts. exclude_id: ignorar el propio post
    cuando se re-genera su slug (si no, se agregaría -2 a sí mismo)."""
    slug = slugify(base)
    candidate = slug
    n = 2
    while db.execute(
        "SELECT 1 FROM posts WHERE slug = ? AND id IS NOT ?", (candidate, exclude_id)
    ).fetchone():
        candidate = f"{slug}-{n}"
        n += 1
    return candidate


def render_richtext(text):
    """Markdown minimo y seguro: **negrita**, *italica*, párrafos por linea en blanco."""
    text = str(escape(text or ""))
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paras)


def parse_table(raw):
    """Convierte lineas 'Etiqueta | val1 | val2' en labels + columnas de valores."""
    rows = []
    for line in (raw or "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        rows.append(parts)
    if not rows:
        return [], []
    labels = [r[0] for r in rows]
    n_series = max(len(r) for r in rows) - 1
    series = []
    for i in range(n_series):
        vals = []
        for r in rows:
            try:
                vals.append(float(r[i + 1]) if i + 1 < len(r) and r[i + 1] != "" else None)
            except ValueError:
                vals.append(None)
        series.append(vals)
    return labels, series


def fmt_num(v):
    """Al reeditar un gráfico, mostrar 1172.0 como 1172 (pero 959.1 queda igual)."""
    return str(int(v)) if float(v).is_integer() else str(v)


def get_post_blocks(db, post_id):
    rows = db.execute(
        "SELECT * FROM blocks WHERE post_id = ? ORDER BY position ASC", (post_id,)
    ).fetchall()
    blocks = []
    for r in rows:
        b = dict(r)
        b["data"] = json.loads(b["data"])
        blocks.append(b)
    return blocks


def next_position(db, post_id):
    row = db.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 AS p FROM blocks WHERE post_id = ?", (post_id,)
    ).fetchone()
    return row["p"]


# ---------------------------------------------------------------------------
# Imágenes subidas desde el panel
# ---------------------------------------------------------------------------

def detect_image_type(head):
    """Reconoce el formato por los primeros bytes del archivo (su "firma"),
    no por la extensión que dice tener: un .exe renombrado a .png no pasa."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def save_upload(fs):
    """Guarda un archivo subido (FileStorage de Werkzeug) en UPLOAD_DIR y
    devuelve su URL pública (/uploads/...). Lanza ValueError con un mensaje
    para el usuario si el archivo no sirve."""
    head = fs.stream.read(16)
    fs.stream.seek(0)
    ext = detect_image_type(head)
    if not ext:
        raise ValueError("El archivo no parece una imagen. Se aceptan PNG, JPG, GIF y WebP.")
    base = secure_filename(os.path.splitext(fs.filename or "")[0]).lower()[:40] or "imagen"
    # Fecha + sufijo aleatorio: dos archivos con el mismo nombre no se pisan,
    # y la extensión sale del contenido real, no del nombre original.
    name = f"{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3)}-{base}.{ext}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    fs.save(os.path.join(UPLOAD_DIR, name))
    return url_for("uploaded_file", filename=name)


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    # send_from_directory rechaza rutas que intenten salir de UPLOAD_DIR.
    return send_from_directory(UPLOAD_DIR, filename)


@app.errorhandler(413)
def upload_too_large(e):
    flash(f"La imagen es demasiado grande: el máximo es {MAX_UPLOAD_MB} MB.", "error")
    ref = request.referrer or ""
    return redirect(ref if ref.startswith(request.host_url) else url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# Sitio público
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    db = get_db()
    q = request.args.get("q", "").strip()
    if q:
        like = f"%{q}%"
        posts = db.execute(
            """SELECT * FROM posts WHERE status = 'published'
               AND (title LIKE ? OR dek LIKE ? OR eyebrow LIKE ?)
               ORDER BY published_at DESC""",
            (like, like, like),
        ).fetchall()
    else:
        posts = db.execute(
            "SELECT * FROM posts WHERE status = 'published' ORDER BY published_at DESC"
        ).fetchall()
    return render_template("index.html", posts=posts, q=q)


@app.route("/post/<slug>")
def show_post(slug):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE slug = ?", (slug,)).fetchone()
    if not post or (post["status"] != "published" and not session.get("is_admin")):
        abort(404)
    blocks = get_post_blocks(db, post["id"])

    # Numerar automaticamente los bloques 'heading' con numeros romanos
    romans = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
              "XI", "XII", "XIII", "XIV", "XV"]
    heading_i = 0
    chart_defs = []  # para pasarle a Chart.js en el template
    for b in blocks:
        if b["type"] == "heading":
            b["roman"] = romans[heading_i] if heading_i < len(romans) else str(heading_i + 1)
            heading_i += 1
        elif b["type"] == "paragraph":
            b["html"] = render_richtext(b["data"].get("text", ""))
        elif b["type"] == "callout":
            b["html"] = render_richtext(b["data"].get("text", ""))
        elif b["type"] == "chart":
            chart_defs.append({"id": f"chart-{b['id']}", **b["data"]})

    return render_template(
        "post.html", post=post, blocks=blocks, chart_defs=chart_defs,
        accents=ACCENTS, accents_hex={k: v["hex"] for k, v in ACCENTS.items()},
    )


# ---------------------------------------------------------------------------
# Admin — dashboard
# ---------------------------------------------------------------------------

@app.route("/admin/")
@login_required
def admin_dashboard():
    db = get_db()
    posts = db.execute("SELECT * FROM posts ORDER BY updated_at DESC").fetchall()
    return render_template("admin_dashboard.html", posts=posts)


@app.route("/admin/posts", methods=["POST"])
@login_required
def admin_create_post():
    db = get_db()
    title = request.form.get("title", "Nuevo post").strip() or "Nuevo post"
    now = datetime.now(timezone.utc).isoformat()
    slug = unique_slug(db, title)
    cur = db.execute(
        """INSERT INTO posts (slug, title, eyebrow, dek, status, accent, author, created_at, updated_at)
           VALUES (?, ?, '', '', 'draft', 'blue', '', ?, ?)""",
        (slug, title, now, now),
    )
    db.commit()
    return redirect(url_for("admin_edit_post", post_id=cur.lastrowid))


@app.route("/admin/posts/<int:post_id>/edit")
@login_required
def admin_edit_post(post_id):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        abort(404)
    blocks = get_post_blocks(db, post_id)
    for b in blocks:
        if b["type"] == "chart":
            # reconstruir el texto tabla para reeditar
            rows = []
            labels = b["data"].get("labels", [])
            series = b["data"].get("series", [])
            for i, lab in enumerate(labels):
                vals = [fmt_num(s[i]) if i < len(s) and s[i] is not None else "" for s in series]
                rows.append(" | ".join([lab] + vals))
            b["table_text"] = "\n".join(rows)
    return render_template(
        "admin_edit.html", post=post, blocks=blocks,
        accents=ACCENTS, chart_types=CHART_TYPES, block_types=BLOCK_TYPES,
    )


@app.route("/admin/posts/<int:post_id>", methods=["POST"])
@login_required
def admin_update_post(post_id):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        abort(404)
    title = request.form.get("title", "").strip() or post["title"]
    eyebrow = request.form.get("eyebrow", "").strip()
    dek = request.form.get("dek", "").strip()
    accent = request.form.get("accent", "blue")
    if accent not in ACCENTS:
        accent = "blue"
    now = datetime.now(timezone.utc).isoformat()
    # Mientras el post nunca se publicó, la URL (slug) sigue al título: así un
    # post creado como "Nuevo post" no queda en /post/nuevo-post para siempre.
    # Una vez publicado, el slug se congela para no romper links ya compartidos.
    slug = post["slug"]
    if not post["published_at"]:
        slug = unique_slug(db, title, exclude_id=post_id)
    db.execute(
        "UPDATE posts SET title=?, slug=?, eyebrow=?, dek=?, accent=?, updated_at=? WHERE id=?",
        (title, slug, eyebrow, dek, accent, now, post_id),
    )
    db.commit()
    flash("Post actualizado.", "ok")
    return redirect(url_for("admin_edit_post", post_id=post_id))


@app.route("/admin/posts/<int:post_id>/publish", methods=["POST"])
@login_required
def admin_toggle_publish(post_id):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        abort(404)
    now = datetime.now(timezone.utc).isoformat()
    if post["status"] == "published":
        db.execute("UPDATE posts SET status='draft', updated_at=? WHERE id=?", (now, post_id))
        flash("Post pasado a borrador.", "ok")
    else:
        published_at = post["published_at"] or now
        db.execute(
            "UPDATE posts SET status='published', updated_at=?, published_at=? WHERE id=?",
            (now, published_at, post_id),
        )
        flash("Post publicado.", "ok")
    db.commit()
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/posts/<int:post_id>/delete", methods=["POST"])
@login_required
def admin_delete_post(post_id):
    db = get_db()
    # ON DELETE CASCADE ya borra los bloques, pero lo hacemos explícito por
    # si alguna vez se toca la base desde afuera con foreign_keys apagado.
    db.execute("DELETE FROM blocks WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    db.commit()
    flash("Post eliminado.", "ok")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# Admin — bloques de contenido
# ---------------------------------------------------------------------------

def strip_prefix(form, prefix):
    """Para el formulario de 'agregar bloque', que prefija cada campo con
    el tipo (chart_title, heading_title, ...) para que nunca puedan
    pisarse entre si aunque el JS que oculta/deshabilita falle."""
    plen = len(prefix) + 1
    out = {}
    for k in form.keys():
        if k.startswith(prefix + "_"):
            out[k[plen:]] = form.get(k)
    return out


def block_data_from_form(block_type, form):
    if block_type == "heading":
        return {"tag": form.get("tag", "").strip(), "title": form.get("title", "").strip()}
    if block_type == "paragraph":
        return {"text": form.get("text", "").strip()}
    if block_type == "callout":
        color = form.get("color", "orange")
        if color not in ACCENTS:
            color = "orange"
        return {"color": color, "text": form.get("text", "").strip()}
    if block_type == "image":
        return {"url": form.get("url", "").strip(), "caption": form.get("caption", "").strip()}
    if block_type == "chart":
        labels, series = parse_table(form.get("table", ""))
        series_names = [s.strip() for s in form.get("series_names", "").split(",") if s.strip()]
        chart_type = form.get("chart_type", "bar_comparison")
        if chart_type not in CHART_TYPES:
            chart_type = "bar_comparison"
        color = form.get("color", "orange")
        if color not in ACCENTS:
            color = "orange"
        return {
            "chart_type": chart_type,
            "title": form.get("title", "").strip(),
            "subtitle": form.get("subtitle", "").strip(),
            "source": form.get("source", "").strip(),
            "color": color,
            "labels": labels,
            "series": series,
            "series_names": series_names,
        }
    return {}


@app.route("/admin/posts/<int:post_id>/blocks", methods=["POST"])
@login_required
def admin_add_block(post_id):
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        abort(404)
    block_type = request.form.get("type")
    if block_type not in BLOCK_TYPES:
        flash("Tipo de bloque inválido.", "error")
        return redirect(url_for("admin_edit_post", post_id=post_id))
    data = block_data_from_form(block_type, strip_prefix(request.form, block_type))
    if block_type == "image":
        f = request.files.get("image_file")
        if f and f.filename:
            try:
                data["url"] = save_upload(f)
            except ValueError as e:
                flash(str(e), "error")
                return redirect(url_for("admin_edit_post", post_id=post_id) + "#blocks")
        if not data["url"]:
            flash("Para agregar una imagen, subí un archivo o pegá una URL.", "error")
            return redirect(url_for("admin_edit_post", post_id=post_id) + "#blocks")
    pos = next_position(db, post_id)
    db.execute(
        "INSERT INTO blocks (post_id, position, type, data) VALUES (?, ?, ?, ?)",
        (post_id, pos, block_type, json.dumps(data, ensure_ascii=False)),
    )
    db.execute("UPDATE posts SET updated_at=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), post_id))
    db.commit()
    flash("Bloque agregado.", "ok")
    return redirect(url_for("admin_edit_post", post_id=post_id) + "#blocks")


@app.route("/admin/posts/<int:post_id>/blocks/<int:block_id>", methods=["POST"])
@login_required
def admin_update_block(post_id, block_id):
    db = get_db()
    block = db.execute("SELECT * FROM blocks WHERE id = ? AND post_id = ?", (block_id, post_id)).fetchone()
    if not block:
        abort(404)
    data = block_data_from_form(block["type"], request.form)
    if block["type"] == "image":
        f = request.files.get("file")
        if f and f.filename:
            try:
                data["url"] = save_upload(f)
            except ValueError as e:
                flash(str(e), "error")
                return redirect(url_for("admin_edit_post", post_id=post_id) + "#blocks")
    db.execute("UPDATE blocks SET data = ? WHERE id = ?", (json.dumps(data, ensure_ascii=False), block_id))
    db.execute("UPDATE posts SET updated_at=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), post_id))
    db.commit()
    flash("Bloque actualizado.", "ok")
    return redirect(url_for("admin_edit_post", post_id=post_id) + "#blocks")


@app.route("/admin/posts/<int:post_id>/blocks/<int:block_id>/delete", methods=["POST"])
@login_required
def admin_delete_block(post_id, block_id):
    db = get_db()
    db.execute("DELETE FROM blocks WHERE id = ? AND post_id = ?", (block_id, post_id))
    db.commit()
    return redirect(url_for("admin_edit_post", post_id=post_id) + "#blocks")


@app.route("/admin/posts/<int:post_id>/blocks/<int:block_id>/move/<direction>", methods=["POST"])
@login_required
def admin_move_block(post_id, block_id, direction):
    db = get_db()
    blocks = db.execute(
        "SELECT id, position FROM blocks WHERE post_id = ? ORDER BY position ASC", (post_id,)
    ).fetchall()
    ids = [b["id"] for b in blocks]
    if block_id not in ids:
        abort(404)
    idx = ids.index(block_id)
    swap_idx = idx - 1 if direction == "up" else idx + 1
    if 0 <= swap_idx < len(ids):
        a_id, b_id = ids[idx], ids[swap_idx]
        pos_a = blocks[idx]["position"]
        pos_b = blocks[swap_idx]["position"]
        db.execute("UPDATE blocks SET position = ? WHERE id = ?", (pos_b, a_id))
        db.execute("UPDATE blocks SET position = ? WHERE id = ?", (pos_a, b_id))
        db.commit()
    return redirect(url_for("admin_edit_post", post_id=post_id) + "#blocks")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    # Solo desarrollo local. El debugger de Flask permite ejecutar código, así
    # que por defecto escucha solo en esta máquina (HOST=0.0.0.0 para abrirlo).
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=port, debug=True)
