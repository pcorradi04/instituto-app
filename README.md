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
   (etiqueta, título, copete) y escribís ahí mismo. Arriba hay una **guía**
   de cinco pasos (se puede ocultar; el navegador se acuerda) y una fila de
   progreso que dice qué le falta al post: título, etiqueta, copete,
   bloques, guardado, publicado. Un post vacío ofrece "Empezar con una
   estructura de ejemplo": una sección, un párrafo, un gráfico con datos de
   muestra y un destacado, para ver cómo se combinan y editar encima.
4. Con los botones de abajo de todo ("+ Agregar al final", cada uno dice
   para qué sirve) sumás bloques al final. Para meter uno **entre** dos
   bloques que ya están, pasá el mouse por la línea que los separa: aparece
   "insertar acá" con los seis tipos. Los bloques aparecen en el lugar
   exacto donde van a quedar:
   - **Título de sección**: se numera solo con números romanos (I, II, III...).
   - **Párrafo**: texto corrido. Línea en blanco = párrafo nuevo. Seleccioná
     texto y tocá **B** o **I** (aparecen al pasar el mouse) para negrita o
     itálica: mientras editás se ve como `**así**`, en el post se ve en
     negrita.
   - **Destacado**: un recuadro de color (naranja / navy / granate) para un
     dato clave o una advertencia.
   - **Gráfico**: elegís el tipo (hay 20, agrupados: comparación, evolución
     en el tiempo, composición, distribución e indicadores), el color de
     cada serie y los datos como texto simple, una fila por línea. Si no
     sabés qué formato lleva el tipo que elegiste, tocá **Cargar ejemplo**:
     llena la tabla con datos de muestra y editás sobre eso. Los colores:
     hay un botón por serie (o por bloque en el treemap, por destino en el
     Sankey) debajo del gráfico, y también podés **hacer clic sobre la
     serie en el gráfico mismo** (una barra, un punto, un bloque, o su
     nombre en la leyenda): se abre la paleta al lado. La paleta tiene 64
     colores en seis grupos (institucionales, vivos, pastel, tierra,
     oscuros, grises) y un selector libre para cualquier otro color
     (o escribís el código, ej. `#1F77B4`). Los datos:
     ```
     Mayo 2026 | 959.1 | 1172
     Junio 2026 | 401.3 | 918
     ```
     Cada tipo dice qué va en cada columna: el editor lo muestra en una
     línea "Columnas: ..." arriba de la tabla, con un ejemplo gris adentro.
     Las columnas pueden ir separadas con `|`, coma, punto y coma o
     tabulación: se detecta solo (o lo elegís en "Separador"), así que
     podés copiar celdas de Excel y pegarlas tal cual, o pegar un CSV. Los
     decimales pueden ir con coma (`959,1`) o con punto, y los miles con
     punto (`1.172,5`). Si la primera fila trae los nombres de las
     columnas, se toma como encabezado: no se grafica y, en los gráficos
     con leyenda, esos nombres pasan a ser los de las series. También
     podés **subir el archivo** directamente ("Subir Excel o CSV": .xlsx,
     .xls o .csv; si el Excel tiene varias hojas, elegís cuál), o bajar
     una **plantilla Excel** del tipo elegido, con las columnas que lleva
     y filas de ejemplo, para completarla y subirla. Al guardar, la tabla
     queda siempre en el formato con `|`.
     El **Sankey** dibuja los niveles que hagan falta: cada fila es un
     camino de nombres con el valor al final (`TGS | Oferta nacional |
     74.1` es una entrada; `Oferta nacional | Demanda interna | Usinas |
     34.5` una salida en dos pasos), y los tramos que se repiten se suman.
     Su plantilla Excel es un balance en dos bloques, como los que arma el
     Instituto: a la izquierda las entradas (Origen, Concepto, Valor: el
     concepto entra al origen) y a la derecha las salidas (Origen del
     Destino, Destino, Concepto, Valor). Al subirla, el editor la reconoce
     por el encabezado y la convierte en caminos. Los colores son uno por
     nodo de destino; los nodos que solo son origen van en gris oscuro.
     Los tipos son: barras agrupadas, barras horizontales, barras
     divergentes, mancuernas, dispersión, líneas, barras + línea (eje
     derecho), áreas apiladas, ranking en el tiempo (bump), mapa de calor,
     cascada, pronóstico con bandas (fan), barras apiladas, barras 100 %,
     treemap, Sankey, mapa esquemático por zona, caja y bigotes, bullet y
     velocímetro. El gráfico se dibuja arriba mientras escribís. Los de
     Chart.js tienen una opción "Alto del gráfico (px)" por si el
     estándar queda chico o grande. En el post, cada gráfico tiene botones
     "Copiar PNG" y "Descargar PNG" para llevárselo como imagen (tarjeta
     completa: título, gráfico, fuente y marca de agua).
   - **Figura (2 o 3 gráficos juntos)**: como los "exhibits" de las
     consultoras: varios gráficos uno al lado del otro, cada uno con su
     tipo, sus datos, su color y su título chico, y en común el título, el
     subtítulo, la nota al pie y la fuente. Se copia o descarga como un
     solo PNG. En pantallas chicas los gráficos se apilan.
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

**Duplicar.** En la barra de herramientas de cada bloque (aparece al pasar
el mouse) está "⧉ duplicar": hace una copia completa justo debajo, para
cambiarle pocas cosas (típico: el mismo gráfico con otra serie). En una
figura, cada panel tiene su propio "duplicar", que lo copia como un panel
más a la derecha.

**Destacado dentro del gráfico.** Debajo del dibujo, cada gráfico y cada
figura tienen un campo "Destacado": un recuadro beige adentro de la
tarjeta para la lectura clave, en una o dos líneas ("En 2024 el gas fue el
**47 %** del consumo"). Admite `**negrita**`, que sale en el color de
acento. Vacío no se muestra. Sale también en el PNG.

**Proyección automática.** Tipo de gráfico "Proyección automática
(tendencia + bandas)", en "Evolución en el tiempo": cargás solo la serie
histórica (Período | valor) y la app proyecta los períodos siguientes.
Método: tendencia lineal por mínimos cuadrados; estacionalidad aditiva
opcional (opción "Estacionalidad": 12 si es mensual, 4 si es trimestral;
hacen falta al menos dos ciclos completos de datos, si no se ignora);
escala logarítmica opcional para series que crecen a un porcentaje
("Crecimiento porcentual: si"); bandas de confianza (por defecto 80 y
95 %) que son intervalos de predicción de la regresión, calculados con la
dispersión de los residuos y que se ensanchan hacia el futuro. Los
períodos futuros se rotulan solos siguiendo el formato de los cargados
(2026-07 → 2026-08, 2024 → 2025, Ene-26 → Feb-26, 2026-Q1 → 2026-Q2). El
método queda escrito al pie del gráfico, para que el lector sepa que es una
proyección estadística simple. Cuando los números salen de un modelo
propio, usá "Pronóstico con bandas", que muestra lo que cargás.

## 2a. Gráficos con play ("videos") y embeds

Hay dos tipos de gráfico que se mueven en el tiempo, pensados para mostrar
una evolución como si fuera un video: **Carrera de barras** (las barras se
reordenan y crecen período a período, como los rankings animados) y
**Líneas que se dibujan** (un gráfico de líneas que se va trazando). Los
dos se cargan igual que cualquier otro: una fila por período (año, mes) y
una columna por país, empresa o fuente, a mano, pegando desde Excel o con
"Subir Excel o CSV" (la "Plantilla Excel" trae la estructura). Tienen
botón de play y pausa, una barra de tiempo para ir a cualquier período, y
velocidad (lento, normal, rápido). En el post arrancan solos cuando el
lector llega al gráfico (opción "Arranca solo al verse: no" para que
espere el play). Opciones: cuántas barras se ven, unidad, título del eje.
Los botones "Copiar PNG" y "Descargar PNG" sacan la imagen del momento
que se está viendo.

El bloque **Embed / HTML** muestra adentro del post cualquiera de estas
dos cosas:
- **Código HTML completo**, por ejemplo un gráfico animado que te haya
  generado una IA (con Plotly, D3, Chart.js o lo que sea). Se pega, o se
  sube el archivo `.html` con el botón "Subir archivo HTML" (o se arrastra
  sobre el bloque); hasta 200 mil caracteres. Corre aislado
  en un recuadro ("iframe" con sandbox): puede usar librerías de internet
  y mostrar lo que quiera, pero no puede leer ni tocar el sitio, la sesión
  del panel ni los comentarios.
- **Una dirección https sola**: la de un gráfico de Our World in Data
  (con los países elegidos, ej. `...?country=ARG~BRA`), un video de
  YouTube (sirve el link normal de "watch"), etc. Solo se aceptan
  direcciones seguras (https). También sirve pegar el "código para
  embeber" que dan esos sitios (un `<iframe src="https://...">`): el
  bloque saca de ahí la dirección y el alto.
Se le pone el alto en píxeles y un epígrafe opcional; en el editor se ve
la misma vista previa que va a ver el lector.

## 2b. Comentarios de lectores

Cada post publicado tiene al pie una sección de comentarios. Cualquier
lector puede comentar con nombre y, opcionalmente, mail (no se publica);
no hace falta registrarse.

- **Moderación posterior** (la opción por defecto): los comentarios se
  publican al instante y el equipo borra los que no corresponden. Si
  prefieren revisar antes de publicar, en el `.env` se pone
  `COMMENTS_MODERATION=pre` y se reinicia: ahí los comentarios quedan
  pendientes, el panel muestra un aviso amarillo con la cantidad, y se
  aprueban desde el panel, desde el post o desde el mail.
- **Borrar y responder desde el post mismo**: si estás logueado y abrís un
  post, cada comentario tiene un botón "Borrar", y lo que escribas en el
  formulario se publica firmado como "Instituto de Energía". Ojo: **la
  sesión del panel es del navegador**, no de un mail. Si entraste a
  `/admin/login` en tu Chrome, todo lo que comentes desde ese Chrome sale
  como el Instituto hasta que cierres la sesión (el formulario avisa y
  tiene el link). Para comentar con tu nombre, cerrá la sesión o usá una
  ventana de incógnito.
- **Respuestas de un solo nivel**: se puede responder a un comentario, y
  las respuestas quedan debajo, indentadas. Responder a una respuesta la
  cuelga del comentario original, así el hilo no se vuelve un árbol.
- **Anti-spam sin molestar al lector**: un campo invisible que solo llenan
  los robots (si viene lleno, se descarta en silencio) y un máximo de 15
  comentarios cada 10 minutos por dirección de internet (se cambia con
  `COMMENT_LIMIT_PER_10MIN` en el `.env`).
- Borrar un comentario borra sus respuestas. Borrar un post borra sus
  comentarios.
- **Links**: en comentarios y en párrafos, una dirección escrita tal cual
  (`https://...` o `www...`) se vuelve clicable sola, y también se puede
  escribir `[texto](https://...)` para un link con texto. Los comentarios
  que traen links quedan para autorizar aunque la moderación sea
  posterior (así un robot no puede publicar propaganda; se apaga con
  `COMMENTS_HOLD_LINKS=0`).
- **Aviso por mail** (opcional): si configurás una cuenta de Gmail en el
  `.env` (ver `DEPLOY.md`, sección 5b), cada comentario nuevo llega por
  mail con dos links, "Aprobar" y "Borrar", que funcionan sin entrar al
  panel. Los links llevan una firma criptográfica, así que solo sirven
  para ese comentario y esa acción.

Cada post publicado recibe un **número correlativo** (N.º 1, N.º 2...) la
primera vez que se publica; no cambia aunque se despublique y se vuelva a
publicar. Se ve en la portada y arriba del título.

La banda beige con el título grande es solo de la portada; en cada post el
encabezado va dentro del cuerpo: el número del post en una caja azul a la
izquierda del título, la etiqueta arriba y la firma abajo, y el copete
debajo a todo el ancho (los párrafos también usan todo el ancho, igual que
las tarjetas de gráficos). Cada gráfico lleva el logo gris del Instituto
arriba a la derecha, que también sale en el PNG.

**Etiquetas.** El campo arriba del título es la etiqueta o categoría del
post (libre: la escribís vos). Podés poner varias separadas por punto y
coma ("Hidrocarburos; Vaca Muerta"): en la portada salen como "Publicado
en Hidrocarburos, Vaca Muerta", cada una es un link y al tocarla se
listan los posts con esa etiqueta. No hay carpetas ni subgrupos: es un
rótulo para encontrar posts parecidos.

**Banner, portada y pie.** El banner es blanco con el logo gris del
Instituto, la palabra "Blog", un buscador y los íconos de las redes
sociales: aparecen solo las que tengan su dirección en el `.env`
(`SOCIAL_X`, `SOCIAL_INSTAGRAM`, `SOCIAL_FACEBOOK`, `SOCIAL_LINKEDIN`,
`SOCIAL_YOUTUBE`, `SOCIAL_PINTEREST`; ver `.env.example`). La portada
muestra una tarjeta por post: categoría, número, título, autor, fecha,
cantidad de comentarios, un resumen (el copete o, si no hay, el primer
párrafo recortado) y el botón "Seguir leyendo". El pie es una banda gris
con el logo blanco del Instituto y el texto legal; ese texto se edita en
`templates/_footer.html`.

Además, cada post muestra autor y fecha debajo del título (el autor se
carga en el editor, en la línea "Por ...") y, al final del texto, los logos
de X, LinkedIn y WhatsApp para compartirlo, más un botón "Copiar link". Son
links simples, sin rastreo.

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

## 4b. Varias personas a la vez

Es una aplicación web con una base de datos: cada persona que entra al
panel trabaja en su navegador y no hay "archivo en uso" ni bloqueos. Dos
personas pueden editar dos posts distintos al mismo tiempo sin enterarse
una de la otra. La única regla práctica: **un mismo post, una persona a
la vez.** Al guardar, el editor manda el post entero, así que si dos
personas tienen abierto el mismo post y guardan, queda lo del último que
guardó y lo del otro se pierde. Si eso empieza a pasar seguido, avisá y le
agrego un aviso ("este post cambió desde que lo abriste") antes de guardar.

## 5. Deploy — opciones, de más simple a más control

| Dónde | Cómo | Costo aprox. |
|---|---|---|
| **Render.com** | Conectás el repo de GitHub, elegís "Web Service", Python, comando de arranque `gunicorn app:app`. Deploy automático en cada push. | Gratis para empezar, después ~7 USD/mes para que no se duerma |
| **Railway.app** | Muy parecido a Render, así de simple. | Similar |
| **PythonAnywhere** | Pensado específicamente para apps chicas de Flask, sin Docker ni nada. | Gratis para probar, planes desde ~5 USD/mes |
| **VPS propio** (DigitalOcean, Hetzner) | Más control, pero hay que instalar y mantener vos mismo Nginx + gunicorn + certificados. | Desde ~5 USD/mes, pero más trabajo de mantenimiento |
| **Dentro del sitio del Instituto** (ieaustral.com/blog) | El servidor del sitio pasa `/blog` por proxy a gunicorn; la app se monta bajo ese prefijo con `URL_PREFIX=/blog`. Ficha técnica y configuración de ejemplo en `DEPLOY.md`, sección 8. | El hosting que ya tengan |

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
- Aviso por mail cuando llega un comentario (hoy: el aviso está en el
  panel). Feed RSS, etiquetas clickeables, paginación de la portada y
  suscripción por mail: son la "fase 2" del blog.

Ninguna de estas es difícil de sumar sobre esta base — las dejé afuera para
que la primera versión sea chica, funcione, y la puedan probar ya.
