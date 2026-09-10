# Instituto de Energía — plataforma de posts

App propia (no WordPress) para publicar reportes/posts del Instituto con una
**estructura y un lenguaje visual fijos**, pero contenido libre: cada persona
que carga un post elige título, texto y gráficos, pero no puede romper el
formato — los colores salen de una paleta cerrada, los bloques de contenido
son de tipos predefinidos (título de sección, párrafo, callout, gráfico,
imagen), y el CSS es el mismo para todos los posts.

Está armada con **Flask + SQLite** — nada de bases de datos externas ni
build steps. Corre en cualquier hosting que soporte Python.

## 1. Correrla en tu máquina

Necesitás Python 3.10 o más nuevo. En Windows se instala con
`winget install Python.Python.3.12` (o desde python.org). Ojo: si Windows
dice "Python no se encontró" y te abre la Microsoft Store, es el atajo falso
de Windows — usá `py` en vez de `python`, como abajo.

**Windows (PowerShell o CMD):**

```bash
cd instituto-app
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python seed.py                  # crea la base y carga un post de ejemplo (una sola vez)
python app.py                   # arranca el servidor
```

**Mac / Linux:**

```bash
cd instituto-app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python seed.py
python app.py
```

Abrí:
- Sitio público: http://127.0.0.1:5000
- Panel de administración: http://127.0.0.1:5000/admin/login
  - Clave por defecto: `energia2026` (ver sección de seguridad, esto hay que cambiarlo)

Para comprobar que todo anda después de cualquier cambio (recorre el flujo
completo del panel sobre una base temporal, no toca la tuya):

```bash
python test_app.py
```

## 2. Cómo se usa el panel

1. Entrás a `/admin/login` con la clave.
2. "Nuevo post": le ponés un título y se abre el editor.
3. El editor **es el post**: ves la misma página que van a ver los lectores,
   con el mismo diseño, pero vacía. Hacés click en cualquier texto
   (etiqueta, título, copete) y escribís ahí mismo.
4. Con los botones de abajo de todo ("+ Agregar") sumás bloques, que
   aparecen en el lugar exacto donde van a quedar:
   - **Título de sección**: se numera solo con números romanos (I, II, III...).
   - **Párrafo**: texto corrido. Línea en blanco = párrafo nuevo. Seleccioná
     texto y tocá **B** o **I** (aparecen al pasar el mouse) para negrita o
     itálica: mientras editás se ve como `**así**`, en el post se ve en
     negrita.
   - **Destacado**: un recuadro de color (naranja / navy / granate) para un
     dato clave o una advertencia.
   - **Gráfico**: elegís el tipo (hay 20, agrupados: comparación, evolución
     en el tiempo, composición, distribución e indicadores), el color, y
     cargás los datos como texto simple, una fila por línea:
     ```
     Mayo 2026 | 959.1 | 1172
     Junio 2026 | 401.3 | 918
     ```
     Cada tipo dice qué va en cada columna: el editor lo muestra en una
     línea "Columnas: ..." arriba de la tabla, con un ejemplo gris adentro.
     Los tipos son: barras agrupadas, barras horizontales, barras
     divergentes, mancuernas, dispersión, líneas, barras + línea (eje
     derecho), áreas apiladas, ranking en el tiempo (bump), mapa de calor,
     cascada, pronóstico con bandas (fan), barras apiladas, barras 100 %,
     treemap, Sankey, mapa esquemático por zona, caja y bigotes, bullet y
     velocímetro. El gráfico se dibuja arriba mientras escribís.
   - **Imagen**: hacés click en el recuadro y elegís un archivo (PNG, JPG,
     GIF o WebP, hasta 10 MB), o lo arrastrás, o pegás una URL; más un
     epígrafe. Las subidas quedan en `instance/uploads/`.
5. Al pasar el mouse por un bloque aparecen sus controles: subir, bajar,
   borrar, y el color si corresponde.
6. Arriba a la derecha elegís el **color de acento** del post (pinta el
   borde del encabezado, la etiqueta y los numerales de sección). La paleta
   es fija a propósito, para que todos los posts se vean parte de la misma
   publicación.
7. **Guardar** (o Ctrl+S) guarda todo de una vez. Si cerrás la pestaña con
   cambios sin guardar, el navegador te avisa.
8. **Publicar** guarda y hace público el post. Antes de eso es un borrador
   que solo ves vos, logueado ("Ver post ↗" te lo muestra tal cual va a
   quedar).

## 3. Estructura del proyecto

```
instituto-app/
├── app.py              → toda la lógica: rutas, base de datos, autenticación
├── seed.py              → carga un post de ejemplo (opcional, corré una vez)
├── test_app.py          → test automático de todo el flujo (corrélo antes de subir cambios)
├── requirements.txt
├── Procfile             → le dice al hosting cómo arrancar la app (gunicorn)
├── .env.example         → plantilla de la configuración secreta (copiar como .env)
├── venv/                → el entorno virtual de Python (local, no va a git)
├── instance/            → TODO el contenido del sitio vive acá (no va a git; hacé backup)
│   ├── instituto.db     → la base de datos (se crea sola)
│   └── uploads/         → las imágenes subidas desde el panel
├── static/
│   ├── style.css        → el sistema de diseño del sitio público (el que ya conocés)
│   ├── admin.css         → estilos del panel y del editor visual
│   ├── charts.js         → dibuja los gráficos (lo usan el post y el editor, para que se vean igual)
│   └── img/              → logos, ya como archivos normales (no base64)
└── templates/
    ├── base.html         → header + footer compartidos
    ├── index.html         → portada / listado de posts
    ├── post.html          → un post individual (acá se arman los gráficos)
    ├── admin_login.html
    ├── admin_dashboard.html
    └── admin_edit.html    → el editor de bloques
```

Para cambiar cualquier cosa visual del sitio (colores, tipografía, el
tamaño del logo, etc.), el único lugar que hay que tocar es
`static/style.css` — como es un solo archivo compartido, el cambio se ve
en todos los posts a la vez.

## 4. Seguridad — hacer esto antes de ponerla en producción

Ahora mismo el panel tiene **una sola clave compartida** (simple a propósito,
para arrancar rápido). Antes de que esto sea público en internet:

1. **Cambiá la clave.** No la dejes en el código: copiá `.env.example` como
   `.env` (en la misma carpeta que `app.py`) y completá `ADMIN_PASSWORD` y
   `SECRET_KEY`. La app lee ese archivo sola al arrancar, y `.env` está en
   `.gitignore` para que nunca se suba al repo. Para generar el
   `SECRET_KEY`:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   En el hosting, esos mismos dos valores se cargan como "variables de
   entorno" en el panel del servicio (Render, Railway y PythonAnywhere
   tienen una pantalla para eso; no hace falta subir el `.env`).
2. Si van a ser varias personas cargando posts (Pedro, Luciano, alumnos...)
   y quieren saber quién publicó qué, hay que pasar de "una clave" a
   "usuarios con nombre" — es un cambio chico sobre esta misma base
   (una tabla `users` en vez de una sola clave), avisame cuando lo necesiten
   y lo sumo.
3. Serví el sitio detrás de HTTPS (cualquier hosting moderno lo da gratis:
   Render, Railway, PythonAnywhere, o un VPS con Caddy/Nginx + Let's Encrypt).

## 5. Deploy — opciones, de más simple a más control

| Dónde | Cómo | Costo aprox. |
|---|---|---|
| **Render.com** | Conectás el repo de GitHub, elegís "Web Service", Python, comando de arranque `gunicorn app:app`. Deploy automático en cada push. | Gratis para empezar, después ~7 USD/mes para que no se duerma |
| **Railway.app** | Muy parecido a Render, así de simple. | Similar |
| **PythonAnywhere** | Pensado específicamente para apps chicas de Flask, sin Docker ni nada. | Gratis para probar, planes desde ~5 USD/mes |
| **VPS propio** (DigitalOcean, Hetzner) | Más control, pero hay que instalar y mantener vos mismo Nginx + gunicorn + certificados. | Desde ~5 USD/mes, pero más trabajo de mantenimiento |

El comando de arranque en producción (en vez de `python app.py`) es
`gunicorn app:app`. Ya está en `requirements.txt` y en el `Procfile`, así que
Render y Railway lo detectan solos. (`gunicorn` no corre en Windows; en tu
máquina seguí usando `python app.py`, que es solo para desarrollo.)

**Ojo con la base de datos antes de elegir hosting.** SQLite guarda todo el
contenido en un archivo (`instance/instituto.db`). En Render y Railway el
disco del servicio se **borra en cada deploy o reinicio**, salvo que
contrates un "disco persistente" (Render lo cobra aparte) y apuntes la app a
él con la variable de entorno `DB_PATH` (ej. `DB_PATH=/var/data/instituto.db`).
PythonAnywhere no tiene ese problema: el disco es persistente de entrada, y
por eso para una app así de chica es la opción más simple. Sea cual sea el
hosting, bajate una copia de la carpeta `instance/` cada tanto (la base más
las imágenes subidas): es todo el sitio. El paso a paso completo del deploy
está en `DEPLOY.md`.

El dominio (`institutodeenergia.austral.edu.ar` o el que elijan) se apunta
después, cuando el hosting esté elegido — es un paso aparte e independiente
de todo este trabajo.

## 6. Qué NO incluye esta primera versión (y se puede sumar después)

- Editor de texto enriquecido tipo Word (hoy los párrafos son texto plano
  con `**negrita**`/`*itálica*` simple — funciona, pero no es "arrastrar y
  soltar").
- Usuarios con nombre y permisos distintos (hoy es una clave compartida).
- Búsqueda dentro del texto completo de cada post (hoy busca en
  título/copete/etiqueta desde la portada).

Ninguna de estas es difícil de sumar sobre esta base — las dejé afuera para
que la primera versión sea chica, funcione, y la puedan probar ya.
