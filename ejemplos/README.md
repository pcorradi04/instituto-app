# Ejemplos para el bloque "Embed / HTML"

Archivos HTML completos, listos para pegar en el bloque **Embed / HTML** del
editor (abrir el archivo con el Bloc de notas, seleccionar todo, copiar,
pegar en el campo del bloque). Cada uno funciona solo: trae sus datos
adentro y carga la librería de gráficos desde internet.

## matriz-energetica.html

Gráfico interactivo al estilo de Our World in Data: consumo de energía
primaria por fuente (carbón, petróleo, gas, nuclear, hidro, eólica, solar,
biocombustibles, otras renovables), 1965–2024, para 14 países más el
mundo, con Argentina primero. Tiene:

- selector de país;
- TWh o % del total; áreas apiladas o líneas;
- línea de tiempo con play (el gráfico se va dibujando año a año) y barra
  para ir a cualquier año;
- un texto que se actualiza con el año elegido (total, % fósil, fuente
  principal, cuánto se multiplicó el consumo desde 1965);
- tooltip con TWh y participación de cada fuente.

Alto sugerido en el bloque: 680 px.

**Datos**: Energy Institute – Statistical Review of World Energy (2026),
vía Our World in Data (licencia CC BY, hay que citarlos; la cita ya está al
pie del gráfico). Para actualizarlos cuando salga la próxima edición:
descargar `owid-energy-data.csv` de https://github.com/owid/energy-data,
correr el script `extract_energy.py` (está en el historial del proyecto:
saca las columnas `*_consumption` de los países elegidos a un JSON) y
reemplazar el JSON que está en la línea `const DATA = ...` del HTML. Para
agregar o sacar países, editar la lista `COUNTRIES` del script.
