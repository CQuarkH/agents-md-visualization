# Pipeline Data Enrichment

Este documento describe la fase de Ingesta y Enriquecimiento de Datos del pipeline.

## Fase 1: Enriquecimiento de Agentes (`scripts/1_enrich_agents.py`)

Este paso se encarga de procesar los datos en crudo (`raw_dataset.csv`) que contienen definiciones estructuradas de repositorios y acoplarles su respectivo documento de agente descargado (almacenado en la caché).

### Proceso:
1. **Lectura de Entrada**: El script lee el archivo `dataset/raw_dataset.csv`.
2. **Generación de Metadatos**: Extrae el nombre del repositorio (`owner/repo`) y sus etiquetas (categorías) asociadas de las columnas correspondientes a las Labels.
3. **Validación de Caché**: Para cada repositorio, busca si existe el archivo markdown correspondiente (`owner_repo.md`) dentro del directorio de caché (`dataset/agents_cache/`). Si el archivo no está cacheado localmente, el script **ignora** la fila en cuestión, imprime un aviso ("Skipping...") y continúa, evitando intentos de descarga externos.
4. **Enriquecimiento**: Si el archivo caché está presente, se lee su contenido y se inyecta un bloque de metadatos (YAML Frontmatter) en la cabecera. Este bloque incluye el identificador completo del repositorio y el listado de categorías extraídas del CSV original.
5. **Generación de Salida**: Escribe el nuevo documento en la carpeta `dataset/enriched_agents/`, conservando el nombre original del archivo cacheado pero ahora enriquecido y estructurado para las próximas fases.

### Inputs:
- `dataset/raw_dataset.csv` (o `raw-dataset.csv`): Archivo CSV base con el listado tabular de repositorios y sus categorías.
- `dataset/agents_cache/`: Directorio temporal/repositorio local con todos los archivos markdown crudos para cada agente (`owner_repo.md`).

### Outputs:
- `dataset/enriched_agents/`: Directorio final que contiene los archivos `.md` resultantes, con el YAML Frontmatter implementado inyectado al tope de cada documento.

### Ejemplo de Salida:
```markdown
---
repo: "0x-j/aptos-full-stack-template"
categories: ["System Overview", "Architecture", "Development Process", "Test", "Configuration & Environment", "Maintanability"]
---
content...
```

## Fase 2: Extracción Estructurada

Para propósitos de evaluación académica comparando la eficiencia y fiabilidad de métodos LLM vs métodos determinísticos tradicionales, esta fase cuenta con **tres variantes**. Todas ellas procesan los archivos resultantes de la Fase 1 y generan un objeto JSON que representa un AST (Abstract Syntax Tree) normalizado del contexto del documento, categorizando las reglas extraídas.

### Estructura del JSON Esperado (Output)
Independientemente de la variante utilizada, el esquema de salida unificado es el siguiente:

```json
{
  "projectInfo": {
    "repoName": "<nombre_repo>",
    "agentsMdSource": "<archivo_origen.md>"
  },
  "rootNode": {
    "id": "root",
    "label": "AGENTS.md Context",
    "type": "root",
    "children": [
      {
        "id": "cat_<nombre_seguro_categoria>",
        "label": "<Nombre Categoría>",
        "type": "category",
        "count": <total_reglas_en_categoria>,
        "children": [
          {
            "id": "rule_<num_secuencial>",
            "type": "rule",
            "content": {
              "text": "<Instrucción completa identificada en el markdown>",
              "originalHeader": "<Título de la sección H2/H3 a la que pertenece>"
            },
            "metadata": {
              "strength": "<MUST|SHOULD>",
              "format": "<ListItem|Paragraph>"
            }
          }
        ]
      }
    ]
  }
}
```

### Variante A: LLM Local (`scripts/2a_extract_json_llm.py`)
Utiliza un modelo Local Small Language Model (SLM) iterando con un servidor compatible (ej. LMStudio con Qwen 2.5).
- **Proceso**: El script extrae el bloque de metadatos del archivo y le pasa el texto en crudo al modelo junto con el diccionario maestro de categorías. Luego parsea la salida en crudo garantizando la estructura dictada de JSON.
- **Input**: Archivos `.md` de `dataset/enriched_agents/`.
- **Output**: Árboles JSON guardados en `dataset/json_trees/llm/`.

### Variante B: AST Parser Determinista (`scripts/2b_extract_json_parser.py`)
No utiliza IA; emplea heurísticas determinísticas y la estructura generada por **Pandoc**.
- **Proceso**: 
  - Ejecuta la CLI de `pandoc` subyacentemente para transformar de Markdown a JSON AST nativo de Pandoc.
  - Recorre el JSON de manera recursiva asegurando extraer texto de nodos anidados (como `Quoted`, `Table`, `Header`, `Para`, `BulletList`).
  - Asigna la categoría macheando palabras clave contra el diccionario de categorías general o el array inyectado previamente, y detecta semántica imperativa (`MUST/SHOULD`) usando expresiones regulares (Regex).
- **Input**: Archivos `.md` de `dataset/enriched_agents/`.
- **Output**: Árboles JSON guardados en `dataset/json_trees/parser/`.

### Variante C: LLM Comercial vía API (`scripts/2c_extract_json_llm_api.py`)
Utiliza un modelo comercial de alto rendimiento de Anthropic (Claude 4.5 Sonnet) a través de su API oficial.
- **Proceso**: Similar a la Variante A, extrae contexto y pide la estructuración JSON AST exacta. Destaca por su alta fiabilidad y capacidad intelectual. Requiere una clave de API válida.
- **Input**: Archivos `.md` de `dataset/enriched_agents/`.
- **Output**: Árboles JSON guardados en `dataset/json_trees/llm_api/`.