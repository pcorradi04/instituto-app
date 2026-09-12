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
import smtplib
import threading
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from functools import wraps

from flask import (
    Flask, request, session, redirect, url_for, render_template,
    g, flash, abort, send_from_directory
)
from itsdangerous import URLSafeSerializer, BadSignature
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
# Tipos de gráfico disponibles. La definición de cada uno (qué columnas lleva
# la tabla, qué opciones tiene, cómo se dibuja) vive en static/charts.js, que
# comparten el post y el editor. Acá solo se valida que el tipo exista: para
# agregar un tipo nuevo hay que sumarlo en los dos lados.
CHART_TYPES = [
    "bar_comparison", "bar_horizontal", "diverging_bar", "dumbbell", "scatter",
    "line", "bar_line", "stacked_area", "bump", "heatmap", "waterfall", "fan_chart",
    "stacked_bar", "stacked_bar_100", "treemap", "sankey", "shaded_list",
    "boxplot", "bullet", "gauge",
]
BLOCK_TYPES = ["heading", "paragraph", "callout", "chart", "image"]

# Comentarios de lectores. Se publican después de que alguien del equipo los
# aprueba desde el panel (decisión del Instituto: empezar moderado y aflojar
# después). Las respuestas del equipo llevan esta firma y salen al instante.
STAFF_NAME = "Instituto de Energía"
COMMENT_LIMIT_PER_10MIN = 3   # comentarios por dirección IP cada 10 minutos

# Aviso por mail cuando llega un comentario (opcional). Con Gmail: crear una
# "contraseña de aplicación" en la cuenta de Google y poner en el .env:
#   SMTP_USER=cuenta@gmail.com   SMTP_PASSWORD=la-contraseña-de-aplicación
#   NOTIFY_EMAIL=quien-recibe@...   (si falta, se manda a SMTP_USER)
# Si SMTP_USER o SMTP_PASSWORD faltan, no se manda nada y todo funciona igual.
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", "") or SMTP_USER
# Dirección pública del sitio, para armar los links de los mails
# (ej. https://institutoenergia.pythonanywhere.com). Si falta, se deduce.
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")


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
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
        parent_id INTEGER REFERENCES comments(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        email TEXT DEFAULT '',
        body TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        is_staff INTEGER NOT NULL DEFAULT 0,
        ip TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    """)
    # Migraciones chicas: columnas agregadas después de la primera versión.
    cols = {r[1] for r in db.execute("PRAGMA table_info(posts)")}
    if "post_number" not in cols:
        try:
            db.execute("ALTER TABLE posts ADD COLUMN post_number INTEGER")
        except sqlite3.OperationalError:
            pass  # otro proceso la agregó al mismo tiempo (recargador / varios workers)
    # Número correlativo, único y cronológico para cada post publicado: se
    # asigna la primera vez que se publica y no cambia más. Acá se numeran
    # los que ya estaban publicados sin número (ej. el post del seed).
    n = db.execute("SELECT COALESCE(MAX(post_number), 0) FROM posts").fetchone()[0]
    for row in db.execute(
        "SELECT id FROM posts WHERE published_at IS NOT NULL AND post_number IS NULL ORDER BY published_at"
    ).fetchall():
        n += 1
        db.execute("UPDATE posts SET post_number = ? WHERE id = ?", (n, row[0]))
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


app.jinja_env.filters["slug"] = slugify


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


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_es(iso, hora=False):
    """'2026-09-10T22:15:00+00:00' -> '10 de septiembre de 2026' (hora de
    Argentina, UTC-3 fijo: el país no cambia de horario)."""
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso[:10]
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone(timedelta(hours=-3)))
    s = f"{dt.day} de {MESES[dt.month - 1]} de {dt.year}"
    return s + (f", {dt:%H:%M}" if hora else "")


app.jinja_env.filters["fecha_es"] = fecha_es


def client_ip():
    """IP del visitante. Detrás del proxy del hosting viene en X-Forwarded-For."""
    return (request.access_route[0] if request.access_route else request.remote_addr) or ""


def get_comments(db, post_id, include_pending=False):
    """Comentarios de un post como árbol de un solo nivel, en orden
    cronológico: [{...comentario, "replies": [...]}, ...]. Los pendientes
    solo se incluyen para el admin (que los ve marcados en el post)."""
    if include_pending:
        rows = db.execute("SELECT * FROM comments WHERE post_id = ? ORDER BY created_at ASC", (post_id,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM comments WHERE post_id = ? AND status = 'approved' ORDER BY created_at ASC",
                          (post_id,)).fetchall()
    roots, by_id = [], {}
    for r in rows:
        c = dict(r)
        c["replies"] = []
        c["html"] = render_richtext(c["body"])
        by_id[c["id"]] = c
    for c in by_id.values():
        if c["parent_id"]:
            parent = by_id.get(c["parent_id"])
            if parent:
                parent["replies"].append(c)
            # Respuesta a un comentario todavía no aprobado: no se muestra.
        else:
            roots.append(c)
    return roots


def comment_counts(db):
    """{post_id: cantidad de comentarios aprobados}, para la portada."""
    return {r["post_id"]: r["c"] for r in db.execute(
        "SELECT post_id, COUNT(*) AS c FROM comments WHERE status = 'approved' GROUP BY post_id")}


def safe_next(default):
    """Ruta interna a la que volver después de una acción del panel."""
    nxt = request.form.get("next", "")
    if not nxt.startswith("/") or nxt.startswith("//"):
        return default
    return nxt


# ---------------------------------------------------------------------------
# Avisos por mail (comentarios nuevos) con links para aprobar o borrar
# ---------------------------------------------------------------------------

def send_email(subject, body):
    """Manda un mail de texto plano por SMTP. Devuelve True si salió."""
    if not (SMTP_USER and SMTP_PASSWORD and NOTIFY_EMAIL):
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = NOTIFY_EMAIL
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception as e:  # un mail caído no tiene que romper el sitio
        app.logger.warning("No se pudo mandar el mail de aviso: %s", e)
        return False


def send_email_async(subject, body):
    """El mail sale en segundo plano, para no demorar la respuesta al lector."""
    if not (SMTP_USER and SMTP_PASSWORD and NOTIFY_EMAIL):
        return
    threading.Thread(target=send_email, args=(subject, body), daemon=True).start()


def moderation_token(cid, action):
    """Token firmado con la SECRET_KEY: identifica el comentario y la acción.
    Es la credencial del link del mail, por eso no hace falta login."""
    return URLSafeSerializer(app.secret_key, salt="moderacion-comentarios").dumps({"c": cid, "a": action})


def site_url():
    base = SITE_URL or request.url_root.rstrip("/")
    if app.config["SESSION_COOKIE_SECURE"] and base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    return base


def notify_new_comment(post, cid, name, email, body):
    base = site_url()
    text = (
        f'Nuevo comentario en "{post["title"]}"\n\n'
        f"De: {name}" + (f" <{email}>" if email else "") + "\n\n"
        f"{body}\n\n"
        f"Aprobar:  {base}{url_for('moderate_comment', token=moderation_token(cid, 'approve'))}\n"
        f"Borrar:   {base}{url_for('moderate_comment', token=moderation_token(cid, 'delete'))}\n"
        f"Ver post: {base}{url_for('show_post', slug=post['slug'])}#c{cid}\n"
    )
    send_email_async(f"[Blog Instituto de Energía] Comentario de {name} para aprobar", text)


def parse_table(raw):
    """Convierte líneas 'Etiqueta | val1 | val2' en:
    - labels: la primera columna de cada fila,
    - series: las demás columnas como números (vacío o no numérico -> None),
    - rows: las filas crudas, como texto (para los gráficos que llevan texto
      en más de una columna, ej. Sankey: origen | destino | valor).
    Misma regla que parseChartTable() en static/charts.js."""
    rows = []
    for line in (raw or "").strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("|")]
        rows.append(parts)
    if not rows:
        return [], [], []
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
    return labels, series, rows


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


@app.route("/favicon.ico")
def favicon():
    # Los navegadores piden /favicon.ico por costumbre; el ícono real es un PNG.
    return redirect(url_for("static", filename="img/favicon.png"))


@app.errorhandler(413)
def upload_too_large(e):
    msg = f"La imagen es demasiado grande: el máximo es {MAX_UPLOAD_MB} MB."
    if request.path == url_for("admin_upload"):
        # El editor sube por AJAX y espera JSON.
        return {"error": msg}, 413
    flash(msg, "error")
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
    return render_template("index.html", posts=posts, q=q, comment_counts=comment_counts(db),
                           accents_hex={k: v["hex"] for k, v in ACCENTS.items()})


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

    accent = post["accent"] if post["accent"] in ACCENTS else "blue"
    is_admin = bool(session.get("is_admin"))
    comments = get_comments(db, post["id"], include_pending=is_admin)
    n_comments = db.execute(
        "SELECT COUNT(*) AS c FROM comments WHERE post_id = ? AND status = 'approved'", (post["id"],)
    ).fetchone()["c"]
    return render_template(
        "post.html", post=post, blocks=blocks, chart_defs=chart_defs,
        accent_hex=ACCENTS[accent]["hex"],
        accents_hex={k: v["hex"] for k, v in ACCENTS.items()},
        comments=comments, n_comments=n_comments, staff_name=STAFF_NAME,
        commenter_name=session.get("commenter_name", ""),
    )


@app.route("/post/<slug>/comentar", methods=["POST"])
def post_comment(slug):
    """Un lector deja un comentario (queda pendiente) o el equipo, logueado,
    responde (sale al instante con firma institucional)."""
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE slug = ? AND status = 'published'", (slug,)).fetchone()
    if not post:
        abort(404)
    back = url_for("show_post", slug=slug) + "#comentarios"
    # Campo trampa: el formulario lo lleva oculto. Una persona no lo ve; un
    # robot lo llena. Si viene con algo, se descarta en silencio.
    if request.form.get("website", "").strip():
        return redirect(back)
    is_admin = bool(session.get("is_admin"))
    name = STAFF_NAME if is_admin else request.form.get("name", "").strip()[:60]
    email = "" if is_admin else request.form.get("email", "").strip()[:120]
    body = request.form.get("body", "").strip()[:3000]
    if len(name) < 2 or len(body) < 5:
        flash("Falta el nombre o el comentario es muy corto.", "comment-error")
        return redirect(back)
    ip = client_ip()
    if not is_admin:
        since = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        n = db.execute("SELECT COUNT(*) AS c FROM comments WHERE ip = ? AND is_staff = 0 AND created_at > ?",
                       (ip, since)).fetchone()["c"]
        if n >= COMMENT_LIMIT_PER_10MIN:
            flash("Mandaste varios comentarios seguidos. Esperá unos minutos y probá de nuevo.", "comment-error")
            return redirect(back)
    # Un solo nivel de respuestas: responder a una respuesta cuelga del
    # comentario original, así el hilo no se vuelve un árbol ilegible.
    parent = None
    parent_id = request.form.get("parent_id", "").strip()
    if parent_id.isdigit():
        parent = db.execute("SELECT * FROM comments WHERE id = ? AND post_id = ?", (int(parent_id), post["id"])).fetchone()
        if parent and parent["parent_id"]:
            parent = db.execute("SELECT * FROM comments WHERE id = ?", (parent["parent_id"],)).fetchone()
    now = datetime.now(timezone.utc).isoformat()
    cur = db.execute(
        """INSERT INTO comments (post_id, parent_id, name, email, body, status, is_staff, ip, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (post["id"], parent["id"] if parent else None, name, email, body,
         "approved" if is_admin else "pending", 1 if is_admin else 0, ip, now),
    )
    db.commit()
    if is_admin:
        flash("Respuesta publicada.", "comment-ok")
    else:
        session["commenter_name"] = name
        flash("¡Gracias! Tu comentario se va a publicar cuando lo revise el equipo del Instituto.", "comment-ok")
        notify_new_comment(post, cur.lastrowid, name, email, body)
    return redirect(back)


@app.route("/moderar/<token>")
def moderate_comment(token):
    """Aprobar o borrar un comentario desde el link del mail de aviso."""
    try:
        data = URLSafeSerializer(app.secret_key, salt="moderacion-comentarios").loads(token)
    except BadSignature:
        abort(404)
    db = get_db()
    c = db.execute(
        """SELECT c.*, p.slug AS post_slug, p.title AS post_title
           FROM comments c JOIN posts p ON p.id = c.post_id WHERE c.id = ?""", (data.get("c"),)
    ).fetchone()
    if not c:
        return render_template("admin_moderate.html", result="missing", comment=None), 404
    if data.get("a") == "approve":
        db.execute("UPDATE comments SET status = 'approved' WHERE id = ?", (c["id"],))
        result = "approved"
    elif data.get("a") == "delete":
        db.execute("DELETE FROM comments WHERE parent_id = ?", (c["id"],))
        db.execute("DELETE FROM comments WHERE id = ?", (c["id"],))
        result = "deleted"
    else:
        abort(404)
    db.commit()
    return render_template("admin_moderate.html", result=result, comment=c)


# ---------------------------------------------------------------------------
# Admin — dashboard
# ---------------------------------------------------------------------------

@app.route("/admin/")
@login_required
def admin_dashboard():
    db = get_db()
    posts = db.execute("SELECT * FROM posts ORDER BY updated_at DESC").fetchall()
    pending = db.execute("SELECT COUNT(*) AS c FROM comments WHERE status = 'pending'").fetchone()["c"]
    return render_template("admin_dashboard.html", posts=posts, pending=pending)


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
    # El editor visual trabaja con una copia "editable" de cada bloque: igual
    # a lo guardado, salvo el gráfico, que vuelve a ser texto (la tabla y los
    # nombres de las series) para poder corregirlo a mano.
    editable = []
    for b in blocks:
        data = dict(b["data"])
        if b["type"] == "chart":
            # Si el gráfico se guardó con las filas crudas, se devuelven tal
            # cual (conservan columnas de texto, ej. Sankey). Los gráficos
            # viejos, sin "rows", se reconstruyen desde labels + series.
            if data.get("rows"):
                rows = [" | ".join(r) for r in data["rows"]]
            else:
                rows = []
                for i, lab in enumerate(data.get("labels", [])):
                    vals = [fmt_num(s[i]) if i < len(s) and s[i] is not None else ""
                            for s in data.get("series", [])]
                    rows.append(" | ".join([lab] + vals))
            data = {
                "chart_type": data.get("chart_type", "bar_comparison"),
                "title": data.get("title", ""), "subtitle": data.get("subtitle", ""),
                "source": data.get("source", ""), "color": data.get("color", "orange"),
                "series_names": ", ".join(data.get("series_names", [])),
                "table": "\n".join(rows),
                "options": data.get("options") or {},
            }
        editable.append({"type": b["type"], "data": data})
    accent = post["accent"] if post["accent"] in ACCENTS else "blue"
    editor = {
        "id": post["id"], "title": post["title"], "eyebrow": post["eyebrow"] or "",
        "dek": post["dek"] or "", "author": post["author"] or "", "accent": accent, "blocks": editable,
    }
    return render_template(
        "admin_edit.html", post=post, editor=editor, accent_hex=ACCENTS[accent]["hex"],
        accents=ACCENTS,
    )


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
        if post["post_number"] is None:
            # Número correlativo, único y cronológico: se asigna la primera
            # vez que el post se publica y ya no cambia.
            next_n = db.execute("SELECT COALESCE(MAX(post_number), 0) + 1 FROM posts").fetchone()[0]
            db.execute("UPDATE posts SET post_number = ? WHERE id = ?", (next_n, post_id))
        flash("Post publicado.", "ok")
    db.commit()
    # El editor manda next=<su propia URL> para volver ahí; el dashboard no
    # manda nada. Solo rutas internas.
    nxt = request.form.get("next", "")
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = url_for("admin_dashboard")
    return redirect(nxt)


@app.route("/admin/posts/<int:post_id>/delete", methods=["POST"])
@login_required
def admin_delete_post(post_id):
    db = get_db()
    # ON DELETE CASCADE ya borra los bloques, pero lo hacemos explícito por
    # si alguna vez se toca la base desde afuera con foreign_keys apagado.
    db.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM blocks WHERE post_id = ?", (post_id,))
    db.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    db.commit()
    flash("Post eliminado.", "ok")
    return redirect(url_for("admin_dashboard"))


# ---------------------------------------------------------------------------
# Admin — guardar el post desde el editor visual
# ---------------------------------------------------------------------------

def block_data_from_form(block_type, form):
    """Limpia y valida los datos de un bloque tal como llegan del editor
    (un dict de strings) y devuelve lo que se guarda en la base. Para el
    gráfico, convierte la tabla de texto en labels + series numéricas."""
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
        labels, series, rows = parse_table(form.get("table", ""))
        series_names = [s.strip() for s in form.get("series_names", "").split(",") if s.strip()]
        chart_type = form.get("chart_type", "bar_comparison")
        if chart_type not in CHART_TYPES:
            chart_type = "bar_comparison"
        color = form.get("color", "orange")
        if color not in ACCENTS:
            color = "orange"
        # Opciones propias de cada tipo (título de eje, unidad, etc.): un dict
        # chico de texto. Se aceptan solo claves con pinta de identificador y
        # se descartan las vacías.
        raw_opts = form.get("options") or {}
        options = {}
        if isinstance(raw_opts, dict):
            for k, v in raw_opts.items():
                if re.fullmatch(r"[a-z][a-z0-9_]{0,30}", str(k)) and str(v or "").strip():
                    options[str(k)] = str(v).strip()[:200]
        return {
            "chart_type": chart_type,
            "title": form.get("title", "").strip(),
            "subtitle": form.get("subtitle", "").strip(),
            "source": form.get("source", "").strip(),
            "color": color,
            "labels": labels,
            "series": series,
            "rows": rows,
            "series_names": series_names,
            "options": options,
        }
    return {}


@app.route("/admin/posts/<int:post_id>/save", methods=["POST"])
@login_required
def admin_save_post(post_id):
    """Guarda el post entero desde el editor visual: datos generales y TODOS
    los bloques, en el orden en que vienen. Recibe JSON y responde JSON.
    Reemplazar todos los bloques de una vez (en vez de editarlos de a uno)
    es lo que permite que mover/borrar/agregar en el editor sea instantáneo
    y que "Guardar" sea un solo paso."""
    db = get_db()
    post = db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post:
        abort(404)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("blocks"), list):
        return {"ok": False, "error": "Datos inválidos."}, 400

    title = str(payload.get("title") or "").strip() or post["title"]
    eyebrow = str(payload.get("eyebrow") or "").strip()
    dek = str(payload.get("dek") or "").strip()
    author = str(payload.get("author") or "").strip()[:120]
    accent = payload.get("accent") if payload.get("accent") in ACCENTS else "blue"

    blocks = []
    for raw in payload["blocks"]:
        if not isinstance(raw, dict) or raw.get("type") not in BLOCK_TYPES:
            return {"ok": False, "error": "Tipo de bloque inválido."}, 400
        raw_data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        # block_data_from_form espera strings (null -> ""); "options" del
        # gráfico es un dict de strings.
        data = {}
        for k, v in raw_data.items():
            if isinstance(v, dict):
                data[k] = {str(kk): ("" if vv is None else str(vv)) for kk, vv in v.items()}
            else:
                data[k] = "" if v is None else str(v)
        blocks.append((raw["type"], block_data_from_form(raw["type"], data)))

    now = datetime.now(timezone.utc).isoformat()
    # Mientras el post nunca se publicó, la URL (slug) sigue al título: así un
    # post creado como "Nuevo post" no queda en /post/nuevo-post para siempre.
    # Una vez publicado, el slug se congela para no romper links ya compartidos.
    slug = post["slug"]
    if not post["published_at"]:
        slug = unique_slug(db, title, exclude_id=post_id)
    db.execute(
        "UPDATE posts SET title=?, slug=?, eyebrow=?, dek=?, author=?, accent=?, updated_at=? WHERE id=?",
        (title, slug, eyebrow, dek, author, accent, now, post_id),
    )
    db.execute("DELETE FROM blocks WHERE post_id = ?", (post_id,))
    for pos, (btype, data) in enumerate(blocks):
        db.execute(
            "INSERT INTO blocks (post_id, position, type, data) VALUES (?, ?, ?, ?)",
            (post_id, pos, btype, json.dumps(data, ensure_ascii=False)),
        )
    db.commit()
    return {"ok": True, "slug": slug, "post_url": url_for("show_post", slug=slug)}


@app.route("/admin/upload", methods=["POST"])
@login_required
def admin_upload():
    """Sube una imagen desde el editor (AJAX). Responde {"url": ...} o
    {"error": ...}; el bloque de imagen guarda esa URL al guardar el post."""
    f = request.files.get("file")
    if not f or not f.filename:
        return {"error": "No llegó ningún archivo."}, 400
    try:
        return {"url": save_upload(f)}
    except ValueError as e:
        return {"error": str(e)}, 400


# ---------------------------------------------------------------------------
# Admin — moderación de comentarios
# ---------------------------------------------------------------------------

@app.route("/admin/comentarios")
@login_required
def admin_comments():
    db = get_db()
    rows = db.execute(
        """SELECT c.*, p.title AS post_title, p.slug AS post_slug
           FROM comments c JOIN posts p ON p.id = c.post_id
           ORDER BY CASE c.status WHEN 'pending' THEN 0 ELSE 1 END, c.created_at DESC
           LIMIT 200"""
    ).fetchall()
    pending = sum(1 for r in rows if r["status"] == "pending")
    return render_template("admin_comments.html", comments=rows, pending=pending)


@app.route("/admin/comentarios/<int:cid>/aprobar", methods=["POST"])
@login_required
def admin_comment_approve(cid):
    db = get_db()
    db.execute("UPDATE comments SET status = 'approved' WHERE id = ?", (cid,))
    db.commit()
    flash("Comentario aprobado.", "ok")
    return redirect(safe_next(url_for("admin_comments")))


@app.route("/admin/comentarios/<int:cid>/borrar", methods=["POST"])
@login_required
def admin_comment_delete(cid):
    db = get_db()
    # ON DELETE CASCADE ya borra las respuestas; explícito por las dudas.
    db.execute("DELETE FROM comments WHERE parent_id = ?", (cid,))
    db.execute("DELETE FROM comments WHERE id = ?", (cid,))
    db.commit()
    flash("Comentario borrado.", "ok")
    return redirect(safe_next(url_for("admin_comments")))


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    # Solo desarrollo local. El debugger de Flask permite ejecutar código, así
    # que por defecto escucha solo en esta máquina (HOST=0.0.0.0 para abrirlo).
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=port, debug=True)
