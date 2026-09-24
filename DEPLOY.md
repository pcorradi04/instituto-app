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

## 5b. Avisos por mail cuando llega un comentario (opcional)

Cada comentario nuevo puede avisarse por mail, con dos links: "Aprobar" y
"Borrar". Se hace con una cuenta de Gmail (el plan gratis de PythonAnywhere
solo deja mandar mails por Gmail).

1. Entrá a la cuenta de Google que va a mandar los avisos (puede ser una
   cuenta del Instituto o la tuya). Activá la verificación en dos pasos si
   no está: https://myaccount.google.com/security
2. Creá una **contraseña de aplicación**: https://myaccount.google.com/apppasswords
   → nombre "Blog Instituto" → te da 16 letras. Copialas.
3. En PythonAnywhere, pestaña "Files" → `instituto-app` → `.env`, agregá al
   final (sin espacios alrededor del `=`):
   ```
   SMTP_USER=la-cuenta@gmail.com
   SMTP_PASSWORD=las16letrasdelacontraseñadeaplicacion
   NOTIFY_EMAIL=quien-recibe-los-avisos@ejemplo.com
   SITE_URL=https://institutoenergia.pythonanywhere.com
   ```
   (`NOTIFY_EMAIL` puede ser otra cuenta, o varias personas si usan una
   lista de distribución. Si lo dejás vacío, llega a `SMTP_USER`.)
4. Pestaña "Web" → **Reload**.

Probalo dejando un comentario como lector: en un minuto tiene que llegar el
mail. Si no llega, "Web" → "Log files" → error log dice por qué (casi
siempre: contraseña de aplicación mal copiada).

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

## 8. Integrarla en el sitio del Instituto (ieaustral.com/blog)

Ficha técnica para quien administre el hosting del sitio:

- **Qué es**: una aplicación web en **Python 3.11+** (probada con 3.12)
  hecha con **Flask 3**, con los datos en **SQLite** (un archivo). El
  frontend es HTML/CSS/JavaScript propio más Chart.js desde
  `cdnjs.cloudflare.com` (si el sitio tiene una política CSP, hay que
  permitir scripts de ese dominio). Sin Docker, sin Node, sin base de datos
  externa. Dependencias en `requirements.txt` (Flask, python-dotenv,
  gunicorn).
- **Cómo corre**: un proceso `gunicorn app:app` escuchando en un puerto
  local (ej. 8001), y el servidor web del sitio (nginx, Apache, IIS) le
  pasa por proxy inverso todo lo que empiece con `/blog`. Consume menos de
  100 MB de RAM. Con SQLite, usar 1 o 2 workers de gunicorn.
- **Qué necesita en el servidor**: la carpeta `instance/` (base de datos
  `instituto.db` + `uploads/`) en un disco persistente y con copia de
  resguardo periódica: **eso es todo el contenido**. Un archivo `.env` con
  `ADMIN_PASSWORD`, `SECRET_KEY`, `SECURE_COOKIES=1` y, para este montaje,
  `URL_PREFIX=/blog`, `BEHIND_PROXY=1` y `SITE_URL=https://ieaustral.com`
  (solo el dominio). HTTPS lo da el sitio. Salida SMTP solo si quieren los
  avisos por mail (sección 5b).
- **Rutas**: la app genera todas sus direcciones de forma relativa al
  prefijo, así que bajo `/blog` quedan `ieaustral.com/blog` (portada),
  `ieaustral.com/blog/post/<nombre>` y `ieaustral.com/blog/admin/` (panel).
  Nada que cambiar en el código: solo las variables de arriba.

Ejemplo de configuración con nginx (el proxy pasa la URL completa; la app
recorta el `/blog` sola gracias a `URL_PREFIX`):

```nginx
location /blog {
    proxy_pass         http://127.0.0.1:8001;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
    proxy_set_header   X-Forwarded-Host  $host;
    client_max_body_size 12m;   # imágenes de hasta 10 MB
}
```

Arranque (como servicio de systemd o equivalente, para que se relance
solo):

```bash
cd /ruta/instituto-app && venv/bin/gunicorn app:app --bind 127.0.0.1:8001 --workers 2
```

Si el proxy prefiere **quitar** el `/blog` antes de pasar la URL (algunos
lo hacen así), no se pone `URL_PREFIX`: alcanza con `BEHIND_PROXY=1` y que
el proxy mande el encabezado `X-Forwarded-Prefix: /blog`.

Alternativa aún más simple, si el sitio del Instituto está en un CMS
(WordPress u otro) y prefieren no tocar su servidor: un **subdominio**
(`blog.ieaustral.com`) apuntando a donde corre la app hoy, sin prefijo, y
un link "Blog" en el menú del sitio. Funciona igual y no mezcla dos
sistemas en el mismo servidor.

Actualizaciones: `git pull` en la carpeta del proyecto y reiniciar el
servicio de gunicorn. La base y las imágenes no están en el repo, así que
el `pull` nunca las pisa.

## 9. Servidor propio (cloud server de DonWeb, Ubuntu 24.04) en blog.ieaustral.com

Lo que se decidió con el Instituto (sep 2026): el sitio institucional sigue
en WordPress y el blog corre en un servidor Linux aparte, en el subdominio
`blog.ieaustral.com`, con el panel en `blog.ieaustral.com/admin/`. No hace
falta MySQL: la app usa SQLite (un archivo). Todo el trabajo son tres
partes: instalar, traer los datos, apagar la copia vieja.

### 9.1 Instalar (una vez, unos 10 minutos)

Desde tu compu, en PowerShell (Windows ya trae `ssh`):

```bash
ssh pedro@201.32.128.14 -p 5464
```

Pide la contraseña que te pasó Eugenia (no se ve mientras la escribís).
Ya adentro del servidor, bajá el script de instalación y corrélo con el
dominio y tu correo (el correo es para los avisos de vencimiento del
certificado HTTPS):

```bash
curl -fsSL https://raw.githubusercontent.com/pcorradi04/instituto-app/main/deploy/instalar.sh -o instalar.sh
bash instalar.sh blog.ieaustral.com pcorradi04@gmail.com
```

El script pregunta una sola cosa: la clave para entrar al panel (elegí una
nueva, no reutilices la de PythonAnywhere). Al terminar imprime "Listo:
https://blog.ieaustral.com". Si certbot falla, casi siempre es porque el
dominio no apunta todavía a esa IP o el puerto 80 está cerrado en el
firewall de DonWeb: pedirle a Eugenia que abra 80 y 443, y repetir el
comando que indica el script.

### 9.2 Traer los datos desde PythonAnywhere

Los posts, comentarios e imágenes están en la carpeta `instance/` de
PythonAnywhere. Se bajan a tu compu y se suben al servidor nuevo:

1. En PythonAnywhere, consola Bash:
   ```bash
   cd ~/instituto-app && zip -r ~/instance.zip instance
   ```
   Después, pestaña **Files** → `instance.zip` → botón de descarga. Queda
   en tu carpeta Descargas.
2. En tu compu, PowerShell, subirlo al servidor (pide la contraseña):
   ```bash
   scp -P 5464 "$HOME\Downloads\instance.zip" pedro@201.32.128.14:~
   ```
3. En el servidor (por `ssh`), reemplazar la carpeta vacía por la real y
   reiniciar:
   ```bash
   cd ~/instituto-app && rm -rf instance && unzip -q ~/instance.zip && sudo systemctl restart instituto-blog
   ```
4. Abrí https://blog.ieaustral.com: tienen que estar los posts. Entrá al
   panel con la clave nueva y probá guardar algo.

Conviene hacer esto en un momento en que nadie esté cargando posts, y no
cargar nada en PythonAnywhere después de bajar el zip: lo que se cargue
ahí ya no viaja.

### 9.3 Después de la mudanza

- **Apagar la copia vieja**: en PythonAnywhere, pestaña Web → "Disable".
  O dejarla un tiempo con un aviso; si querés que redirija al dominio
  nuevo, avisame y lo armo.
- **Backups automáticos**: una vez, en el servidor:
  ```bash
  (crontab -l 2>/dev/null; echo "15 3 * * * bash $HOME/instituto-app/deploy/backup.sh") | crontab -
  ```
  Deja cada noche un archivo `~/backups-blog/blog-AAAA-MM-DD.tar.gz` con la
  base y las imágenes (conserva 30). Cada tanto, bajate uno a tu compu.
- **Actualizar** cuando yo suba cambios (reemplaza al pull + Reload):
  ```bash
  bash ~/instituto-app/deploy/actualizar.sh
  ```
- **Ver qué pasa si algo falla**: `sudo systemctl status instituto-blog` y
  `sudo journalctl -u instituto-blog -n 50`.
- **Mails de aviso de comentarios** (opcional): igual que en 5b, agregando
  las variables SMTP al `.env` del servidor (`nano ~/instituto-app/.env`) y
  reiniciando el servicio.
- **Redes sociales del banner**: variables `SOCIAL_*` en ese mismo `.env`.

## Alternativa: Render / Railway

El repo también trae `Procfile` y `gunicorn` en `requirements.txt`, así que
en Render o Railway se conecta el repo y arranca solo. Pero acordate de la
trampa del disco: hay que contratar el disco persistente, montarlo (por
ejemplo en `/var/data`) y cargar en las variables de entorno del servicio
`DB_PATH=/var/data/instituto.db` y `UPLOAD_DIR=/var/data/uploads`, además de
`ADMIN_PASSWORD`, `SECRET_KEY` y `SECURE_COOKIES=1`.
