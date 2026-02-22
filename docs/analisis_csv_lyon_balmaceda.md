# Análisis del CSV Lyon Balmaceda (columnas y formatos)

**Archivo de referencia:** `lyon_balmaceda_scraper_summary.csv` (en el repo no existe `.xlsx`; si trabajas con Excel, exporta/guarda como CSV con el mismo nombre de columnas).

El CSV tiene **28 columnas** separadas por coma (`,`). A continuación se listan en orden, con formato esperado y ejemplos de los primeros registros.

---

## Formato general del archivo

- **Separador:** coma (`,`).
- **Codificación:** UTF-8.
- **Cabecera:** una línea con los nombres de columna (sin comillas en el archivo pequeño; en `lyon_balmaceda_scraper_summary.csv` cada fila de datos va envuelta entre comillas dobles `"..."`; en `lyon_balmaceda_summary_10.csv` las filas no llevan esa comilla externa).
- **Campos con comas internas:** `IMAGES` (JSON) y `DESCRIPCION` (texto) contienen comas; en formato estándar deben ir entre comillas para no romper columnas.

---

## Columnas (índice, nombre, tipo, ejemplo y validación)

| # | Columna | Tipo esperado | Formato / validación | Ejemplo (primer registro) |
|---|---------|----------------|----------------------|----------------------------|
| 0 | **EXECUTION_TIME** | datetime / string | ISO con timezone (`YYYY-MM-DD HH:MM:SS.ffffff±HH`) | `2026-01-15 21:19:10.362911-03` |
| 1 | **URL_PROPIEDAD** | string (URL) | URL absoluta del anuncio | `https://www.portalinmobiliario.com/MLC-3448621696-linda-y-acogedora-casa-en-umbrales-de-buin-_JM` |
| 2 | **PORTAL** | string | Nombre del portal | `Portal Inmobiliario` |
| 3 | **TIPO_PROPIEDAD** | string (categórico) | Ej.: casa, departamento | `casa` |
| 4 | **OPERACION** | string (categórico) | Arriendo, Venta | `Arriendo` |
| 5 | **COMUNA** | string | Comuna o ciudad | `Lo Barnechea` |
| 6 | **BARRIO** | string | Barrio o sector; puede ir vacío | `` (vacío) o `Las Condes` |
| 7 | **LATITUD** | numérico (float) | Decimal, ej. WGS84 (-90 a 90) | `-33.7340171` |
| 8 | **LONGITUD** | numérico (float) | Decimal, ej. WGS84 (-180 a 180) | `-70.7622574` |
| 9 | **PRECIO_UF** | numérico (float) | Precio en UF; > 0 | `13.83569483488356` |
| 10 | **M2_UTIL** | numérico (entero) | Metros cuadrados útiles; puede vacío | `65` |
| 11 | **M2_TOTAL** | numérico (entero) | Metros cuadrados totales | `110` |
| 12 | **DORMITORIOS** | numérico (entero) | Cantidad | `3` |
| 13 | **BANIOS** | numérico (entero) | Cantidad | `2` |
| 14 | **CORREDORA** | string | Nombre corredora; puede vacío | `` |
| 15 | **CODIGO_INTERNO** | string o entero | Código interno del portal | `45296` |
| 16 | **URL_PLP** | string (URL) | URL de la lista/búsqueda | `https://www.portalinmobiliario.com/arriendo/casa/...` |
| 17 | **POSICION** | numérico (entero) | Posición en listado | `23` |
| 18 | **SELLER_THERMOMETER** | numérico (entero) | Índice o nivel vendedor | `3` |
| 19 | **ESTACIONAMIENTO** | numérico (entero) | Cantidad de estacionamientos | `2` |
| 20 | **BODEGA** | numérico (entero) | Cantidad de bodegas | `0` |
| 21 | **ORIENTACION** | string | Orientación; puede vacío | `` |
| 22 | **GASTOS_COMUNES** | numérico (float) | Monto aproximado; puede vacío | `` o `100000` |
| 23 | **PISO** | numérico (entero) | Piso (para departamentos); puede vacío | `` o `1` |
| 24 | **ANIO** | numérico (entero) | Año construcción o entrega | `2026` |
| 25 | **TITULO_PROPIEDAD** | string | Título del anuncio, sin saltos de línea | `Linda Y Acogedora Casa En Umbrales De Buin` |
| 26 | **IMAGES** | string (JSON) | Objeto JSON: `{"n_img": N, "images": ["url1", "url2", ...]}`. En el CSV las comillas pueden estar escapadas como `""` o `""""`. | `{"n_img": 5, "images": ["https://http2.mlstatic.com/...", ...]}` |
| 27 | **DESCRIPCION** | string (texto largo) | Descripción; puede incluir `\n`, comas y comillas. A veces viene como lista Python: `['texto']`. | `['Arriendo Casa en Umbrales de Buin...']` o texto plano |

---

## Resumen de tipos por columna

- **Texto corto/categórico:** PORTAL, TIPO_PROPIEDAD, OPERACION, COMUNA, BARRIO, CORREDORA, ORIENTACION, TITULO_PROPIEDAD.
- **Texto largo:** DESCRIPCION.
- **URL:** URL_PROPIEDAD, URL_PLP.
- **Numérico entero:** M2_UTIL, M2_TOTAL, DORMITORIOS, BANIOS, POSICION, SELLER_THERMOMETER, ESTACIONAMIENTO, BODEGA, PISO, ANIO.
- **Numérico decimal:** LATITUD, LONGITUD, PRECIO_UF, GASTOS_COMUNES.
- **Fecha/hora:** EXECUTION_TIME.
- **Código/ID:** CODIGO_INTERNO (string o entero según origen).
- **JSON (string):** IMAGES.

---

## Validación de los primeros registros

Con el parser actual del ETL (`ETLLoader._parse_csv_row`) aplicado a `lyon_balmaceda_scraper_summary.csv`:

- Las **28 columnas** se leen correctamente en orden.
- **EXECUTION_TIME** cumple formato datetime con timezone.
- **URL_PROPIEDAD** y **URL_PLP** son URLs válidas.
- **LATITUD/LONGITUD** son numéricos en rango típico para Chile (lat ~ -33, lon ~ -70).
- **PRECIO_UF, M2_UTIL, M2_TOTAL, DORMITORIOS, BANIOS, ESTACIONAMIENTO, BODEGA** son numéricos coherentes en las filas revisadas.
- **IMAGES** llega como string con JSON donde las comillas pueden estar escapadas (`""` o `""""`); para uso en código suele normalizarse a `"` antes de `json.loads`.
- **DESCRIPCION** puede venir como `['...']` (lista de un elemento) o texto plano; el cleaner del ETL normaliza para búsqueda semántica.

---

## Diferencia entre los dos CSV del repo

| Archivo | Filas (aprox.) | Formato de fila |
|---------|----------------|------------------|
| `lyon_balmaceda_scraper_summary.csv` | 150 | Cada fila de datos va entre una sola comilla doble `" ... "` (toda la línea es un solo campo si se lee con pandas por defecto). Requiere el parser custom del ETL. |
| `lyon_balmaceda_summary_10.csv` | 38413 | Filas sin comilla externa; columnas separadas por coma; campos con comas (IMAGES, DESCRIPCION) entre comillas. Más estándar para `pd.read_csv`. |

Las **28 columnas** y sus nombres son los mismos en ambos archivos; solo cambia el formato de comillas de cada fila.

---

## Cabecera exacta (copiar/pegar para validar)

```
EXECUTION_TIME,URL_PROPIEDAD,PORTAL,TIPO_PROPIEDAD,OPERACION,COMUNA,BARRIO,LATITUD,LONGITUD,PRECIO_UF,M2_UTIL,M2_TOTAL,DORMITORIOS,BANIOS,CORREDORA,CODIGO_INTERNO,URL_PLP,POSICION,SELLER_THERMOMETER,ESTACIONAMIENTO,BODEGA,ORIENTACION,GASTOS_COMUNES,PISO,ANIO,TITULO_PROPIEDAD,IMAGES,DESCRIPCION
```

Si en tu entorno tienes un archivo **.xlsx** con el mismo nombre de columnas, al exportar a CSV asegura que el separador sea coma y que IMAGES y DESCRIPCION se exporten entre comillas si contienen comas.
