# Cómo publicar el sitio — paso a paso en PythonAnywhere

Esta guía deja el sitio online en `https://USUARIO.pythonanywhere.com`,
con HTTPS, en menos de una hora y sin costo. Después, si quieren un dominio
propio (`institutodeenergia.austral.edu.ar` o el que elijan), se pasa al
plan pago (~5 USD/mes) y se hace un paso extra, al final.

Por qué PythonAnywhere y no Render/Railway: la app guarda todo el contenido
en un archivo SQLite (`instance/instituto.db`) más las imágenes subidas en
`instance/uploads/`. En Render y Railway el disco se borra en cada deploy,
salvo que pagues un disco persistente. En PythonAnywhere el disco es
persistente de entrada, así que lo que cargás queda.

Donde dice `USUARIO`, va tu nombre de usuario de PythonAnywhere.

## 0. Antes de empezar: el código tiene que estar en GitHub

1. Entrá a https://github.com/new y creá un repositorio llamado
   `instituto-app`. Puede ser **público** (el código no tiene secretos: la
   clave va en `.env`, que nunca se sube) o privado (entonces el paso 2 de
   abajo necesita una clave SSH; es más engorroso, avisame si van por ahí).
   No marques "Add a README" ni nada, vacío.
2. En tu máquina, en la carpeta del proyecto (donde está `app.py`), en
   PowerShell:
   ```bash
   git remote add origin https://github.com/TU-USUARIO-GITHUB/instituto-app.git
   git push -u origin main
   ```
   La primera vez GitHub te va a pedir que te loguees en una ventana del
   navegador. Listo: el código está en GitHub.

## 1. Crear la cuenta

1. https://www.pythonanywhere.com → "Pricing & signup" → **"Create a
   Beginner account"** (gratis).
2. Elegí bien el nombre de usuario: va a ser la dirección del sitio
   (`USUARIO.pythonanywhere.com`). Algo como `institutoenergia` queda bien.
3. Confirmá el mail.

## 2. Bajar el código y preparar Python

En el panel de PythonAnywhere: pestaña **"Consoles"** → **"Bash"**. Se abre
una terminal en el navegador. Pegá estos comandos, de a uno:

```bash
git clone https://github.com/TU-USUARIO-GITHUB/instituto-app.git
```

```bash
cd instituto-app
```

```bash
mkvirtualenv --python=python3.12 venv-instituto
```

(Si dice que `python3.12` no existe, usá `python3.11` o `python3.10`; la app
anda con cualquiera de los tres. Anotá cuál usaste: se elige de nuevo en el
paso 4.)

```bash
pip install -r requirements.txt
```

## 3. La configuración secreta (`.env`)

Todavía en la consola Bash:

```bash
cp .env.example .env
```

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Copiá la cadena larga que imprime. Ahora pestaña **"Files"** → carpeta
`instituto-app` → click en `.env` para editarlo. Completá:

- `ADMIN_PASSWORD=` la clave del panel (larga, distinta a cualquier otra).
- `SECRET_KEY=` la cadena que copiaste recién.
- `SECURE_COOKIES=1`

Guardá (botón "Save"). Este archivo nunca sale de PythonAnywhere.

Si querés que el sitio arranque con el post de ejemplo, volvé a la consola
Bash y corré `python seed.py`. Si no, arranca vacío y cargás desde el panel.

## 4. Crear la web app

1. Pestaña **"Web"** → **"Add a new web app"**.
2. Te avisa que el dominio va a ser `USUARIO.pythonanywhere.com` → Next.
3. Framework: elegí **"Manual configuration"** (NO "Flask": esa opción arma
   una app de ejemplo que después hay que borrar).
4. Versión de Python: la misma del paso 2 (3.12, o la que hayas usado).
5. Next. Ya tenés la web app creada, pero apunta a un "Hello world". Ahora
   se configura, todo en esa misma pestaña "Web":

**Sección "Virtualenv"**: en el campo de texto escribí
`/home/USUARIO/.virtualenvs/venv-instituto` y tildá.

**Sección "Code"** → click en el link del **"WSGI configuration file"**. Se
abre un editor. Borrá TODO lo que tiene y pegá el contenido del archivo
`pythonanywhere_wsgi.py` de este repo (podés abrirlo desde "Files"),
cambiando `USUARIO` por tu usuario. Guardá.

**Sección "Static files"**: agregá una fila:
- URL: `/static/`
- Directory: `/home/USUARIO/instituto-app/static`

Esto hace que los logos y el CSS los sirva el servidor directo, sin pasar
por Python: más rápido.

**Sección "Security"**: **"Force HTTPS"** → Enabled.

## 5. Encender

Arriba de la pestaña "Web", botón verde **"Reload USUARIO.pythonanywhere.com"**.
Abrí `https://USUARIO.pythonanywhere.com`. Tiene que verse la portada.
Panel: `https://USUARIO.pythonanywhere.com/admin/login` con la clave del `.env`.

Si ve un error en vez del sitio: pestaña "Web" → sección "Log files" →
**error log**. Las últimas líneas dicen qué pasó (casi siempre: una ruta con
`USUARIO` sin reemplazar, o la versión de Python del virtualenv distinta a la
de la web app).

## 6. Mantenimiento

**Cada vez que cambie el código** (después de un `git push` desde tu
máquina): consola Bash →

```bash
cd ~/instituto-app && git pull && workon venv-instituto && pip install -r requirements.txt
```

y después pestaña "Web" → **Reload**. Los posts y las imágenes no se tocan:
viven en `instance/`, que no está en git.

**Cuenta gratis: cada 3 meses** PythonAnywhere te manda un mail y hay que
entrar a la pestaña "Web" y apretar **"Run until 3 months from today"**. Si
no, el sitio se apaga (no se borra nada; volvés a apretar y vuelve).

**Backup**: pestaña "Files" → `instituto-app/instance/` → descargá
`instituto.db` y la carpeta `uploads/`. Eso es TODO el contenido del sitio.
Hacelo antes de cualquier cambio grande, y cada tanto.

## 7. Dominio propio (opcional, más adelante)

1. Pasar al plan **"Hacker"** (~5 USD/mes) en "Account" → "Upgrade".
2. Pestaña "Web" → "Add a new web app" con el dominio que elijan, o editar
   el dominio de la existente.
3. PythonAnywhere muestra un valor CNAME (algo como
   `webapp-XXXX.pythonanywhere.com`). Eso hay que pasárselo a quien
   administra el DNS de `austral.edu.ar` (sistemas de la Universidad) para
   que creen el registro `institutodeenergia CNAME webapp-XXXX...`.
4. Cuando el DNS propague (hasta 24 h), en "Web" → "Security" → activar el
   certificado HTTPS automático (Let's Encrypt) y Force HTTPS.

## Alternativa: Render / Railway

El repo también trae `Procfile` y `gunicorn` en `requirements.txt`, así que
en Render o Railway se conecta el repo y arranca solo. Pero acordate de la
trampa del disco: hay que contratar el disco persistente, montarlo (por
ejemplo en `/var/data`) y cargar en las variables de entorno del servicio
`DB_PATH=/var/data/instituto.db` y `UPLOAD_DIR=/var/data/uploads`, además de
`ADMIN_PASSWORD`, `SECRET_KEY` y `SECURE_COOKIES=1`.
