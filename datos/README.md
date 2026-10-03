# Captura de datos (EIA) e informe

Dos formas de usarlo, con el mismo código:

**A mano, desde el panel** — `/admin` → **Datos EIA**. Están las series con un
casillero cada una y lo que ya tenemos guardado de cada una; se marca lo que se
quiere, se aprieta **Traer datos y armar el borrador** y listo. La página
muestra el avance ("2 de 4: Gas natural exportado") y, cuando termina, el botón
para abrir el borrador. Tarda unos segundos: el trabajo corre aparte, así que
se puede cerrar la página y volver después.

Tres casillas al lado del botón:

- *sumar lo que publicó la EIA* (marcada por defecto): ver más abajo.
- *el borrador con todas las series guardadas*: trae de la EIA solo lo marcado,
  pero el post incluye además las otras series que ya tengamos. Sirve para
  actualizar una sola serie sin perder el resto del informe.
- *bajar el histórico entero*: por defecto se re-baja solo el último año (que
  es donde la EIA corrige datos) y el resto ya está guardado; esta casilla
  fuerza a traer todo de nuevo.

**Automático**, una vez por semana, sin que nadie abra nada:

1. se baja de la **API pública de la EIA** cada serie que seguimos,
2. se guarda en una **base histórica propia** (`datos/datos.db`), anotando los
   datos nuevos y las **revisiones** de datos ya publicados,
3. se escribe un post en **borrador** en el blog, con un gráfico y un párrafo
   de números por serie.

El borrador **no se publica**: queda en el panel (`/admin`) para revisar,
escribir el análisis y publicar a mano. Es a propósito: el criterio del
Instituto es que el texto lo escribe una persona; el automático trae los
datos ya ordenados y los gráficos ya dibujados.

## Lo que la EIA *escribe*, además de lo que mide

El borrador termina con una sección **"Qué publicó la EIA"**: citas de sus
textos, en inglés, con fecha y link, como material para quien escriba el
análisis. Dos fuentes:

| fuente | qué es | cada cuánto |
|---|---|---|
| **Today in Energy** | artículos cortos sobre datos y tendencias | casi diario (vía RSS) |
| **Short-Term Energy Outlook** | el informe mensual de perspectivas | mensual (alrededor del 6) |

Antes de elegirlas se revisó cuáles siguen vivas, y dos quedaron afuera a
propósito: el **Natural Gas Weekly Update** está congelado desde enero de 2026
y **This Week in Petroleum**, desde octubre de 2025. Las páginas siguen
online: un script que las leyera traería texto viejo con cara de nuevo, que es
justo el problema de "información desactualizada" que marcó Luciano. Si alguna
vez vuelven, agregarlas es una entrada más en `FUENTES` de
`datos/publicaciones.py`.

Las citas van **cortas, entrecomilladas y con el link**, debajo de un aviso
que dice que son de la EIA y no del Instituto. La EIA es una agencia del
gobierno de Estados Unidos, así que sus textos son de dominio público y
citarlos no tiene problema legal; la razón de marcarlos así es editorial: el
análisis lo escribe el equipo y el lector tiene que ver de un vistazo qué es
nuestro y qué no. Cada cita es un bloque aparte: en el editor se borran de a
una sin tocar las demás.

## Qué series trae hoy

| serie | qué es | frecuencia | unidad |
|---|---|---|---|
| `propano_exp_usa` | exportaciones de propano y propileno de EE.UU. | semanal | miles de barriles por día |
| `gas_exp_usa` | exportaciones totales de gas natural de EE.UU. | mensual | millones de pies cúbicos |
| `gnl_exp_usa` | exportaciones de GNL de EE.UU. | mensual | millones de pies cúbicos |
| `crudo_prod_usa` | producción de petróleo crudo de EE.UU. | mensual | miles de barriles por día |

Todas son de **Estados Unidos**. La EIA no es fuente para Argentina: para eso
van la Secretaría de Energía, el ENARGAS y el INDEC (ver
`CONTEXTO_PROYECTO.md`). Este módulo está armado para que sumar esas fuentes
después sea agregar un archivo al lado de `eia_api.py`, sin tocar el resto.

## Puesta en marcha (una sola vez)

**1. La clave de la EIA.** Es gratis, sale en el momento:
<https://www.eia.gov/opendata/register.php>. Llega por mail una clave de 40
caracteres. Se agrega al archivo `.env` del proyecto:

```
EIA_API_KEY=la-clave-que-llego-por-mail
```

**2. Probarlo.** Sin tocar el blog de verdad: el modo `--demo` usa series
inventadas, así se ve todo el circuito (incluso sin clave).

```bash
venv\Scripts\python.exe datos\semanal.py --demo
```

(El modo demo guarda en `datos/demo.db`, una base aparte: los datos inventados
nunca se mezclan con la historia real. El borrador sí se crea de verdad en el
blog, así que después se borra desde el panel.)

Con la clave puesta, la corrida real:

```bash
venv\Scripts\python.exe datos\semanal.py
```

Imprime una línea por serie y una última con el borrador creado. Después se
abre `http://127.0.0.1:5000/admin` y ahí está.

**3. Que corra solo** (opcional: con el botón del panel alcanza para trabajar a
demanda; esto es para que además aparezca el borrador cada lunes sin que nadie
entre).

*En Windows* (la máquina de Pedro) — Programador de tareas, una sola vez en
una consola `cmd`:

```
schtasks /create /tn "Instituto - informe EIA" /tr "C:\Users\User\Downloads\instituto-app\instituto-app\datos\correr_semanal.bat" /sc weekly /d MON /st 07:30
```

Correrlo a mano para probar: `schtasks /run /tn "Instituto - informe EIA"`.
Ojo: la máquina tiene que estar prendida a esa hora.

*En el servidor del blog* (lo recomendable, así el borrador aparece
directamente en el panel de producción) — una sola vez, por SSH:

```bash
(crontab -l 2>/dev/null; echo "30 7 * * 1 cd \$HOME/instituto-app && venv/bin/python datos/semanal.py --silencioso") | crontab -
```

Lunes 7:30. El resultado de cada corrida queda en `datos/semanal.log`.

## Todos los comandos

```bash
python datos/semanal.py                      # lo normal: capturar + borrador
python datos/semanal.py --series propano_exp_usa,gas_exp_usa
python datos/semanal.py --solo-captura       # bajar y guardar, sin post
python datos/semanal.py --solo-informe       # armar el post con lo ya guardado
python datos/semanal.py --completo           # re-bajar el histórico entero
python datos/semanal.py --sin-publicaciones  # sin la sección de citas de la EIA
python datos/semanal.py --demo               # circuito completo con datos inventados
python datos/semanal.py --estado             # qué hay en la base histórica
python datos/semanal.py --db ruta/blog.db    # escribir en otra base del blog
python datos/semanal.py --datos ruta/datos.db
```

Para buscar series nuevas sin adivinar códigos:

```bash
python datos/semanal.py --explorar natural-gas/move/expc
python datos/semanal.py --explorar natural-gas/move/expc --faceta series --contiene propane
```

## Cómo agregar una serie

Una entrada en `datos/series.py` y listo: la captura, la base y el informe la
toman solas. Lo único que hay que averiguar es la **ruta** y el **código de
serie**, con `--explorar` (arriba) o en el navegador de la EIA
(<https://www.eia.gov/opendata/browser/>): el código es el que aparece en las
URLs del tipo `LeafHandler.ashx?...&s=W_EPLLPZ_EEX_NUS-Z00_MBBLD`.

Dos campos merecen atención:

- `agregacion`: `"promedio"` si la serie es un **caudal** (barriles *por día*)
  y `"suma"` si es un **volumen del período** (pies cúbicos *del mes*). De eso
  depende que el "acumulado del año" signifique algo.
- `candidatos`: se puede poner más de un `(ruta, código)`. Se prueban en orden
  y se usa el primero que devuelva datos — la EIA a veces publica la misma
  serie en dos rutas y cambia alguna sin avisar.

Después, conviene correr `--series la_nueva --solo-captura` para ver que baje
bien antes de meterla en el informe.

## Qué hay en cada archivo

| archivo | qué hace |
|---|---|
| `series.py` | **qué** datos seguimos. El único archivo que se toca para sumar series |
| `eia_api.py` | cliente de la API v2 de la EIA (solo biblioteca estándar) |
| `almacen.py` | la base histórica propia: altas, revisiones, log de capturas |
| `publicaciones.py` | lo que la EIA escribe: Today in Energy (RSS) y STEO |
| `informe.py` | las cuentas del análisis y el armado del borrador en el blog |
| `semanal.py` | el programa que se ejecuta: junta todo y tiene los comandos |
| `correr_semanal.bat` | lo que llama el Programador de tareas de Windows |
| `test_datos.py` | 116 chequeos, sin internet ni clave (`python datos/test_datos.py`) |

La pantalla del panel es `templates/admin_datos.html` y las dos rutas
(`/admin/datos` y `/admin/datos/traer`) están al final de `app.py`. La página
no hace el trabajo: crea una **tarea** (tabla `tareas` de la base histórica) y
larga un hilo que corre `semanal.correr_tarea()`. El avance vive en la base y
no en la memoria del proceso, así que la página lo muestra bien aunque el
servidor tenga varios workers de gunicorn.

## Decisiones que conviene conocer

- **La base histórica es nuestra, no un caché.** Si mañana la EIA cambia una
  ruta, se cae o deja de publicar una serie, lo capturado sigue estando y el
  informe se arma igual (con un aviso de qué serie no se pudo actualizar).
- **Las revisiones quedan registradas.** La EIA corrige datos ya publicados,
  sobre todo en las series semanales. En cada corrida se compara lo que llega
  con lo guardado: si un valor cambió, se anota en la tabla `revisiones`, el
  gráfico lo dice en su nota al pie y el borrador avisa arriba. Es el tipo de
  control que el Instituto quiere poder mostrar, y es gratis hacerlo así.
- **El post se arma con las mismas funciones que el editor visual**
  (`block_data_from_form()` de `app.py`). Un gráfico generado por el
  automático es indistinguible de uno cargado a mano: se edita, se le cambia
  el color o el tipo, se le mueven los bloques, igual que cualquier otro.
- **Una búsqueda por vez.** Si alguien aprieta el botón mientras otra está
  corriendo, se avisa y no se larga una segunda. Una tarea que quedó colgada
  más de 10 minutos (por ejemplo, porque se reinició el servidor) se da por
  perdida sola.
- **Correr dos veces el mismo día no duplica nada**: si el borrador del día
  todavía no se publicó, se reemplaza su contenido. Si ya se publicó, no se
  toca: se crea uno nuevo.
- **El texto automático es deliberadamente seco** (último dato, variación
  semanal/mensual, interanual, promedio móvil, acumulado del año, máximo y
  mínimo de la ventana). Nada de adjetivos ni de causas: eso lo escribe el
  equipo.
- **Las fuentes de texto se leen por donde sea más estable.** Today in Energy
  tiene RSS, que es un formato pensado para programas: no hay que adivinar
  nada. El STEO no tiene, así que se leen los puntos de su portada buscando el
  encabezado "Forecast overview" y no una posición fija: si mañana cambian el
  diseño, la sección queda afuera con un aviso en vez de traer texto
  equivocado, que sería peor.
- **La clave nunca se escribe en un log ni en un mensaje de error** (se tapa
  con `***`), porque viaja en la URL de cada pedido.
- **No agrega dependencias**: `urllib` y `sqlite3` de la biblioteca estándar.
  El mismo `venv` del blog alcanza.

## Si algo falla

- `Falta la clave de la EIA` → falta la línea `EIA_API_KEY=` en el `.env`.
- `La EIA no devolvió datos para la serie ...` → cambió el código o la ruta.
  Buscarlo con `--explorar RUTA --faceta series --contiene ...` y corregir
  `series.py`.
- `La EIA respondió 403` → clave inválida o vencida: pedir otra.
- El borrador no aparece en el panel → el script escribió en **otra** base.
  `--db` apunta a la base del blog; sin ese parámetro usa la misma que
  `app.py` (`DB_PATH` del `.env`, por defecto `instance/instituto.db`). En el
  servidor, correrlo desde `~/instituto-app` para que lea ese `.env`.
- Nada corrió esta semana → mirar `datos/semanal.log` (cada corrida escribe
  una línea por serie) y `--estado` para ver la fecha de la última captura.
