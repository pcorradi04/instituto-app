"""
Carga un post de ejemplo (con datos reales del Reporte de Comercio Exterior)
para que la plataforma no arranque vacía. Correr una sola vez:

    python seed.py
"""
import json
import sqlite3
from datetime import datetime, timezone

from app import DB_PATH, init_db, slugify

init_db()
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row

now = datetime.now(timezone.utc).isoformat()
slug = slugify("Petróleo y gas natural, contados por tres fuentes distintas")

existing = db.execute("SELECT id FROM posts WHERE slug = ?", (slug,)).fetchone()
if existing:
    print("El post de ejemplo ya existe (id=%s). No se creó de nuevo." % existing["id"])
else:
    cur = db.execute(
        """INSERT INTO posts (slug, title, eyebrow, dek, status, accent, author, created_at, updated_at, published_at)
           VALUES (?, ?, ?, ?, 'published', 'blue', 'Instituto de Energía', ?, ?, ?)""",
        (
            slug,
            "Petróleo y gas natural, contados por tres fuentes distintas",
            "Comercio Exterior",
            "Cruzamos la base de la Secretaría de Energía contra Aduana/INDEC, ENARGAS, CAMMESA, el pronóstico climático del SMN y la dinámica internacional del petróleo — para saber qué tan sólido es cada número antes de proyectarlo.",
            now, now, now,
        ),
    )
    post_id = cur.lastrowid

    def add_block(pos, type_, data):
        db.execute(
            "INSERT INTO blocks (post_id, position, type, data) VALUES (?, ?, ?, ?)",
            (post_id, pos, type_, json.dumps(data, ensure_ascii=False)),
        )

    add_block(0, "heading", {"tag": "Fuente única — Secretaría de Energía", "title": "Lo único que da la serie completa 2020–2026"})
    add_block(1, "paragraph", {"text": "Ninguna otra fuente pública ofrece esta profundidad histórica mensual, con detalle por empresa y cuenca, en un solo archivo. Es la columna vertebral del reporte: todo lo que sigue se contrasta contra esto."})
    add_block(2, "chart", {
        "chart_type": "line", "title": "Exportación de petróleo crudo y gas natural — USD millones/mes",
        "subtitle": "Fuente: Secretaría de Energía, TD Comercio Exterior (pivot cache extraído).",
        "source": "Secretaría de Energía", "color": "orange",
        "series_names": ["Petróleo crudo", "Gas natural"],
        "labels": ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06"],
        "series": [[463.1, 386.6, 720.7, 741.3, 959.1, 401.3], [22.96, 24.61, 34.19, 19.22, 30.41, 19.81]],
    })
    add_block(3, "heading", {"tag": "Validación cruzada — INDEC / ARCA", "title": "Lo que agrega Aduana: un control independiente"})
    add_block(4, "paragraph", {"text": "Bajamos los informes técnicos ICA de INDEC (mayo y junio de 2026) para comparar, mes a mes, contra la misma variable en la base de Energía. La coincidencia es alta en **importación de gas** y baja en **exportación**."})
    add_block(5, "chart", {
        "chart_type": "bar_comparison", "title": "Exportación de petróleo crudo — Energía vs. INDEC/Aduana",
        "subtitle": "USD millones. NCM 27090010 vs. suma de cuencas exportadas (Energía).",
        "source": "Secretaría de Energía; INDEC", "color": "orange",
        "series_names": ["Energía (SESCO)", "INDEC / Aduana"],
        "labels": ["Mayo 2026", "Junio 2026"],
        "series": [[959.1, 401.3], [1172, 918]],
    })
    add_block(6, "callout", {"color": "maroon", "text": "**Por qué exportación diverge y no importación:** INDEC aclara en su nota metodológica que las exportaciones de petróleo están sujetas al régimen de \"precios revisables\", que permite modificar el valor declarado hasta 180 días después del embarque."})

    db.commit()
    print("Post de ejemplo creado con id=%s (slug=%s)." % (post_id, slug))

db.close()
