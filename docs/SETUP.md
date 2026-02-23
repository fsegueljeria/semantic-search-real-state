# Guía paso a paso: ejecutar el proyecto en tu máquina

Sigue estos pasos en orden para tener el proyecto corriendo en local.

---

## Requisitos previos

- **Python 3.9+**
- **Docker** (para Qdrant)
- **Git** (ya lo tienes si clonaste el repo)

---

## Paso 1: Clonar / entrar al proyecto

```bash
cd /ruta/a/semantic-search-real-state
```

---

## Paso 2: Crear y activar el entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
```

En Windows (PowerShell): `.venv\Scripts\Activate.ps1`

Verás `(.venv)` en el prompt cuando esté activo.

---

## Paso 3: Instalar dependencias de Python

```bash
pip install -r requirements.txt
```

---

## Paso 4: Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` y ajusta si hace falta (por defecto sirve para desarrollo local):

- `QDRANT_HOST=localhost` (cuando Qdrant corre en Docker en tu máquina)
- `CSV_FILE_PATH`: ruta al CSV de propiedades (ej. `./lyon_balmaceda_scraper.csv`)

---

## Paso 5: Levantar Qdrant con Docker

El frontend de chat y la búsqueda semántica usan Qdrant. Tienes dos opciones.

### Opción A: Solo Qdrant (recomendado para desarrollo)

```bash
docker run -d -p 6333:6333 -p 6334:6334 --name qdrant qdrant/qdrant:latest
```

### Opción B: Todo el stack con docker-compose

```bash
docker-compose up -d
```

Eso levanta Qdrant y el servicio `chat` (Streamlit) dentro de Docker. Si quieres correr Streamlit **en tu máquina** con el venv, usa la Opción A.

---

## Paso 6: (Opcional) Ejecutar el ETL para cargar datos

Si la colección en Qdrant está vacía, carga los datos con el pipeline:

```bash
python -m src.etl.main
```

(Requiere que el CSV indicado en `CSV_FILE_PATH` exista.)

---

## Paso 7: Lanzar el frontend de chat (Streamlit)

**Importante:** las apps de Streamlit deben ejecutarse con el comando `streamlit run`, **no** con `python script.py`.

Con el venv activado:

```bash
streamlit run scripts/chat_search_frontend.py
```

O sin activar el venv, usando el Python del venv:

```bash
.venv/bin/streamlit run scripts/chat_search_frontend.py
```

Se abrirá (o te indicará) la URL, normalmente: **http://localhost:8501**

---

## Resumen de comandos (desarrollo local)

```bash
# 1. Entorno
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Config
cp .env.example .env
# editar .env si hace falta

# 3. Qdrant
docker run -d -p 6333:6333 -p 6334:6334 --name qdrant qdrant/qdrant:latest

# 4. (Opcional) Cargar datos
python -m src.etl.main

# 5. Frontend (siempre con streamlit run)
streamlit run scripts/chat_search_frontend.py
```

---

## Errores frecuentes

| Síntoma | Causa | Solución |
|--------|--------|----------|
| `ModuleNotFoundError: streamlit` | Dependencias no instaladas o no estás en el venv | `pip install -r requirements.txt` y usar `source .venv/bin/activate` |
| `Warning: to view this Streamlit app... run with streamlit run` | Ejecutaste `python scripts/chat_search_frontend.py` | Usar **`streamlit run scripts/chat_search_frontend.py`** |
| No hay resultados / error de conexión | Qdrant no está corriendo o host/puerto incorrectos | Levantar Qdrant (Paso 5) y revisar `QDRANT_HOST` y `QDRANT_PORT` en `.env` |
| Colección vacía | Aún no se ha ejecutado el ETL | Ejecutar `python -m src.etl.main` (Paso 6) |
