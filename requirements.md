
1. Arquitectura General del Sistema
Este diagrama muestra cómo interactúan los componentes principales: el usuario, la API, el cerebro (LLM) y el almacenamiento (Vector DB).


```mermaid
graph TD
    %% --- Estilos ---
    classDef user fill:#f9f,stroke:#333,stroke-width:2px,color:black;
    classDef api fill:#bbf,stroke:#333,stroke-width:2px,color:black;
    classDef logic fill:#dfd,stroke:#333,stroke-width:2px,color:black;
    classDef db fill:#ff9,stroke:#333,stroke-width:2px,color:black;
    
    %% --- Nodos ---
    User[👤 Usuario]:::user
    
    %% Backend y Lógica
    API[🚀 API Gateway / FastAPI]:::api
    ETL[⚙️ ETL Worker]:::logic
    LLM[🧠 LLM Router]:::logic
    Embed[🔢 Modelo Embeddings]:::logic
    Rerank[⚖️ Re-ranker]:::logic

    %% Bases de Datos
    VDB[(🗄️ Vector DB - Qdrant)]:::db
    Cache[(⚡ Redis Cache)]:::db
    CSV[📂 CSV Propiedades]:::db

    %% --- Flujo Online (Búsqueda) ---
    User -->|1. Prompt| API
    API -.->|2. Cache Check| Cache
    API -->|3. Extraer Filtros| LLM
    LLM -->|4. JSON Filtros + Query| API
    
    API -->|5. Vectorizar Texto| Embed
    Embed -->|Vector| API
    
    API -->|6. Búsqueda Híbrida| VDB
    VDB -->|7. Top 50 Candidatos| API
    
    API -->|8. Re-ranking| Rerank
    Rerank -->|9. Top 10 Ordenados| API
    API -->|10. Respuesta JSON| User

    %% --- Flujo Offline (Carga de Datos) ---
    CSV -->|Lectura| ETL
    ETL -->|Generar Vector| Embed
    ETL -->|Guardar Datos + Vector| VDB
```


2. Flujo de Secuencia: Búsqueda Semántica
Este diagrama detalla paso a paso qué sucede cuando un usuario hace una búsqueda, destacando la separación entre la parte semántica y los filtros duros ("Hard Filters").

```mermaid
sequenceDiagram
    participant U as 👤 Usuario
    participant API as 🚀 Backend API
    participant LLM as 🧠 LLM (Extractor)
    participant EMB as 🔢 Embedding Model
    participant DB as 🗄️ Vector DB (Qdrant)

    Note over U, API: Ejemplo: "Casa en Buin por menos de 5000 UF con piscina"

    U->>API: POST /search { prompt: "..." }
    
    rect rgb(230, 240, 255)
        Note right of API: 1. Entendimiento de la Query
        API->>LLM: Analizar Prompt
        LLM-->>API: Retorna JSON Estructurado
        Note right of API: { "semantic": "casa con piscina",<br/>"filters": { "comuna": "Buin", "precio": {"lt": 5000} } }
    end

    rect rgb(255, 245, 230)
        Note right of API: 2. Vectorización
        API->>EMB: Generar Embedding("casa con piscina")
        EMB-->>API: Vector [0.12, -0.98, ..., 0.05]
    end

    rect rgb(230, 255, 230)
        Note right of API: 3. Ejecución de Búsqueda Híbrida
        API->>DB: Search(Vector, Filter=metadata_filters)
        Note right of DB: Filtra primero por Precio/Comuna<br/>Luego busca cercanía vectorial
        DB-->>API: Retorna Top 20 Propiedades
    end

    API-->>U: Respuesta JSON con Propiedades
```


3. Pipeline de Ingesta de Datos (ETL)
Este diagrama es crucial para el equipo de ingeniería de datos. Muestra cómo transformar el CSV adjunto en vectores utilizables, manejando la limpieza de los campos sucios detectados.

```mermaid
flowchart TD
    %% Nodos principales
    RawData[📄 CSV Original] --> Load[📥 Carga con Pandas]
    
    %% Subgrafo 1: Limpieza
    subgraph Limpieza ["Limpieza y Normalización"]
        Load --> Clean1[🧹 Limpieza de Strings]
        Clean1 --> Norm[📏 Normalización Numérica]
        Norm --> Missing[🚫 Manejo de Nulos]
    end

    %% Subgrafo 2: Semántica
    subgraph Semantica ["Enriquecimiento Semántico"]
        Missing --> Concat[📝 Crear Blob de Texto Unificado]
        Concat --> Token[✂️ Tokenización y Recorte]
    end

    %% Subgrafo 3: Vectores
    subgraph Indexado ["Vectorización e Indexado"]
        Token --> Vectorize[⚡ Generar Embedding]
        Missing --> Payload[📦 Preparar Metadata JSON]
        
        Vectorize --> Batch[📦 Agrupar en Lotes]
        Payload --> Batch
        
        Batch --> Upsert[🚀 Insertar en Vector DB]
    end

    %% Almacenamiento
    Upsert --> DB[(🗄️ Base de Datos Qdrant)]
```    