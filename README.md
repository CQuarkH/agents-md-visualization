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
Utiliza un modelo Local Small Language Model (SLM) iterando con un servidor compatible (ej. LMStudio con Qwen 3.5).
- **Proceso**: El script extrae el bloque de metadatos del archivo y le pasa el texto en crudo al modelo junto con el diccionario maestro de categorías. Luego parsea la salida en crudo garantizando la estructura dictada de JSON.
- **Input**: Archivos `.md` de `dataset/enriched_agents/`.
- **Output**: Árboles JSON guardados en `dataset/json_trees/llm/`.

### Sub-Variante 2A: SLM vía OpenRouter (`scripts/2a_openrouter_extract_json.py`)
Utiliza un SLM de última generación (ej. `qwen/qwen-3.5-9b`) remotamente pasando a través de la API ruteada de OpenRouter, pero preservando la compatibilidad de "Structured Output" del cliente de OpenAI.
- **Proceso**: Idéntico a la variante 2A local, pero forzando garantizadamente la salida estructurada a nivel de API. Se inyecta la constante `JSON_SCHEMA` (esquema JSON duro con `strict: True` y `additionalProperties: False`) en el parámetro `response_format` del cliente de OpenAI, lo que obliga al modelo a generar una compatibilidad sintáctica perfecta del AST sin alucinaciones.
- **Dependencias y Auth**: Requiere `pip install openai` y configurar la variable de entorno `OPENROUTER_API_KEY`.
- **Input**: Archivos `.md` de `dataset/enriched_agents/`.
- **Output**: Árboles JSON guardados en una nueva sub-carpeta `dataset/json_trees/llm_forced_output/`.

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

## Fase 2.5: Validación de Resultados
Para validar cuantitativamente la calidad y la veracidad de los JSON generados por las variantes de la Fase 2 (y mitigar amenazas a la validez), se ejecutan rutinas de *testing* automáticas.

### Dependencias
Para correr los scripts de validación, necesitas instalar el validador oficial de esquemas JSON de Python:
```bash
pip install jsonschema
```

### Script 2D: Validación Estructural (Completeness & Sintaxis)
`src/scripts/2d_validate_json_schema.py`

- **¿Qué evalúa?**: Verifica matemáticamente que los JSON generados cumplan al 100% con la estructura del AST requerida. Asegura que no falten campos obligatorios (`projectInfo`, `rootNode`), que los tipos de datos sean exactos (ej. `count` debe ser Integer), y que el LLM no haya inyectado propiedades fantasma.
- **Métrica obtenida**: *Schema Compliance Rate* (Integridad del Formato). Las variaciones que pasan esta prueba están garantizadas para consumirse por una UI/Visualización downstream sin romper el código.
- **Ejecución**:
```bash
python src/scripts/2d_validate_json_schema.py
```

### Script 2E: Validación Semántica (Ground-Truth Hallucinations)
`src/scripts/2e_validate_categories.py`

- **¿Qué evalúa?**: Funciona como un test de alucinación semántica. Lee el array de categorías base original (Ground Truth) inyectado al inicio del `.md` en la **Fase 1** y lo compara contra los nodos `category` generados en el árbol AST de la **Fase 2**. 
- **Métrica obtenida**: *Hallucination Rate*. Detecta y lista si el LLM o el Parser "inventaron" nuevas categorías para encapsular reglas en lugar de ceñirse estrictamente al array asignado para ese repositorio.
- **Ejecución**:
```bash
python src/scripts/2e_validate_categories.py
```

## Fase 3: UI Visualization (Avance V1)

El objetivo de esta fase es reducir drásticamente la carga cognitiva de leer archivos `AGENTS.md` kilométricos, transformando el JSON AST crudo en interfaces gráficas interactivas renderizadas en el navegador web.

Para garantizar la integridad estricta de los datos inyectados al frontend, la arquitectura pasó de usar diccionarios crudos de Python a un **Modelo de Dominio**.

### Arquitectura Orientada a Dominio (`src/domain/models.py`)
Antes de generar cualquier gráfica, el JSON extraído es validado e instanciado imperativamente mediante **Pydantic**. 
La clase `AgentASTDocument` actúa como el Aggregate Root. Todas las propiedades visuales (como `color`, `radio` del nodo, truncamiento de etiquetas y mapeo semántico `MUST`/`SHOULD`) están encapsuladas directamente dentro de las entidades (ej: `RuleCategory` y `AgentRule`). Esto elimina la lógica de presentación redundante (spaghetti) de los scripts de generación.

### Aclaración: Definición de "Must" y "Should"

Para determinar entre "must" y "should", el LLM usa la siguiente heurística léxica basada en el estándar RFC 2119:

- Asigna "MUST": Si el texto original usa modo imperativo, comandos directos o restricciones absolutas. Palabras clave desencadenantes: "must", "always", "never", "do not", "require", o si la oración comienza directamente con un verbo de acción (ej. "Use", "Run", "Install", "Avoid").
- Asigna "SHOULD": Si el texto original usa modo condicional, sugerencias o mejores prácticas. Palabras clave desencadenantes: "should", "recommend", "prefer", "consider", "ideally", "try to", "might", "optional".</match>
<replacement>### 🛡️ Mitigación de Amenaza a la Validez: Justificación Semántica de "MUST" y "SHOULD" (Mapeo Contenido ↔ Forma)

Para evitar que la clasificación de la "fuerza" (*strength*) de una regla dependa del criterio subjetivo y probabilístico del LLM (amenaza de "caja negra"), se implementó una **heurística léxica determinista** en los prompts y parsers. 

Dado que los archivos `AGENTS.md` actúan como Especificaciones de Requisitos en Lenguaje Natural dirigidas a un actor algorítmico, esta heurística se fundamenta en la literatura de **Ingeniería de Requisitos**. Esto permite justificar académicamente el mapeo directo entre el **Contenido** (la semántica de la regla) y su **Forma** (la codificación visual en el grafo interactivo final), basándose en los siguientes estándares internacionales:

1. **[IETF RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119) (*Key words for use in RFCs to Indicate Requirement Levels*):** Estándar fundacional que estipula un vocabulario estricto para interpretar la severidad técnica de las especificaciones de software.
2. **[ISO/IEC/IEEE 29148:2018](https://standards.ieee.org/ieee/29148/7102/) (*Systems and software engineering — Requirements engineering*):** Define formalmente cómo interpretar restricciones duras (*Hard Constraints*) vs. restricciones blandas (*Soft Constraints*) en los requisitos del sistema.

Basado en esta literatura, el sistema de extracción (Fase 2) clasifica y la visualización (Fase 3) mapea visualmente las instrucciones bajo estos criterios irrefutables:

- 🔴 **Asignación "MUST" (Obligación Vinculante / *Hard Constraint*):** 
  - **Heurística Léxica:** Se asigna si el texto original usa modo imperativo absoluto, comandos directos o restricciones críticas. Se dispara con palabras clave como: *"must", "always", "never", "do not", "require"*, o si la oración comienza directamente con un verbo de acción (ej. *"Use", "Run", "Install", "Avoid"*). Romper esta regla implica un fallo garantizado en la operatividad del sistema o del agente.
  - **Mapeo Visual (Forma):** En la topología del grafo, se representará mediante **trazos sólidos y continuos**, transmitiendo al operador humano una exigencia cognitiva inmediata e inquebrantable.

- 🟡 **Asignación "SHOULD" (Recomendación / *Soft Constraint*):**
  - **Heurística Léxica:** Se asigna si el texto original usa modo condicional, sugerencias o mejores prácticas de la industria. Se dispara con palabras clave como: *"should", "recommend", "prefer", "consider", "ideally", "try to", "might", "optional"*. Implica el camino de diseño deseado, pero permite flexibilidad si el operador tiene una justificación técnica válida para desviarse.
  - **Mapeo Visual (Forma):** En la topología del grafo, se representará mediante **trazos punteados (*dashed lines*)**, comunicando visualmente que existe un grado de flexibilidad perimetral.

### Variante 1: Grafo de Fuerza Dirigida (`scripts/3_generate_visualization.py`)
Genera un archivo HTML interactivo con una **vista dividida (Split-View)**:
- **Izquierda**: Muestra el documento Markdown crudo original para lectura por referencias.
- **Derecha**: Renderiza un grafo de red usando `D3.js` (`d3.forceSimulation`). Los nodos (Reglas) orbitan dinámicamente alrededor de sus Categorías padre.
- **Interacción**: Permite hacer Zoom, Paneo (arrastrar el lienzo) y clic sobre los nodos para abrir un panel lateral con los metadatos profundos de la regla (Formato, Intensidad, Header Original).

**Ejecución:**
```bash
PYTHONPATH=. python src/scripts/3_generate_visualization.py dataset/json_trees/llm_forced_output/<archivo>.json
```

### Variante 2: Árbol Jerárquico Horizontal (`scripts/3b_generate_tree_visualization.py`)
Respondiendo a sugerencias académicas para mejorar el escaneo visual de izquierda a derecha, esta variante utiliza el layout estático `d3.tree()`.
- **Diseño**: Conecta la Raíz (Repo) con las Categorías, y estas finalmente con las Reglas Hoja en un formato de tipo "Dendrograma" estricto.
- **Ventaja**: Elimina la física caótica de colisiones presente en la variante de red, permitiendo a los desarrolladores leer secuencialmente el árbol AST de arriba hacia abajo sin que los nodos se reorganicen solos.

**Ejecución:**
```bash
PYTHONPATH=. python src/scripts/3b_generate_tree_visualization.py dataset/json_trees/llm_forced_output/<archivo>.json
```

### Escala del Radio de las Categorías en el Árbol

En la visualización de árbol jerárquico (Variante 2), el radio de los nodos de categoría escala dinámicamente según la cantidad de reglas (hijos) que contienen. Esta escala permite al lector identificar visualmente de un vistazo qué categorías concentran mayor densidad de reglas.

La fórmula de cálculo está definida en `src/domain/models.py:99-114` dentro de la propiedad `tree_graph_radius` de la clase `RuleCategory`:

```
radio = 10 + 3 × (cantidad_reglas - 1)
```

**Ejemplos prácticos:**
| Reglas en Categoría | Radio (px) |
|---------------------|------------|
| 1                   | 10         |
| 2                   | 13         |
| 5                   | 22         |
| 10                  | 37         |

- **Radio base:** 10px (para categorías con al menos 1 regla)
- **Factor de crecimiento:** 3px por cada regla adicional
- **Capping:** El crecimiento se limita a un máximo de 10 hijos (`min(self.count, 10)`) para evitar nodos desproporcionadamente grandes que rompan el layout del árbol.

### Evaluación de Carga Cognitiva (Flesch Reading Ease)

Para cuantificar la dificultad cognitiva que representa cada categoría de reglas para un desarrollador, hemos incorporado la métrica **Flesch Reading Ease (FRE)** como un indicador visual de carga cognitiva.

#### ¿Qué es FRE?

El **Flesch Reading Ease** es una fórmula validada internacionalmente (Rudolf Flesch, 1948) que evalúa la legibilidad de un texto basándose en la longitud promedio de las oraciones y la cantidad promedio de sílabas por palabra. El resultado es un score entre 0 y 100, donde:

- **Scores más altos** = texto más fácil de leer = menor carga cognitiva
- **Scores más bajos** = texto más difícil = mayor carga cognitiva

#### Justificación Académica del Cálculo a Nivel de Categoría

El cálculo de FRE se aplica a nivel de **categoría** (concatenando todas las instrucciones de sus reglas hija), y no a nivel de cada instrucción individual. Esto se debe a que:

1. Las fórmulas de legibilidad como Flesch-Kincaid **pierden validez estadística** cuando se aplican a textos muy cortos (menos de 100 palabras), generando ruido y resultados erráticos.
2. Las instrucciones individuales en AGENTS.md suelen ser frases cortas que no representan adecuadamente la complejidad léxica real del dominio.
3. Al concatenar por categoría, se obtiene una muestra textual estadísticamente representativa que refleja la **densidad cognitiva real** de esa sección del documento, permitiendo al lector identificar de un vistazo qué áreas del documento requerirán mayor esfuerzo mental.

#### Mapa de Calor (Heatmap)

En la visualización (Variante 2), cada nodo de categoría muestra un **borde de color** que representa su score FRE:

| Rango FRE | Color | Interpretación | Carga Cognitiva |
|-----------|-------|----------------|-----------------|
| < 30 | 🔴 Rojo | Very Difficult (Textos legales/técnicos) | Alta |
| 30 - 50 | 🟠 Naranja | Difficult | Media-Alta |
| 50 - 70 | 🟡 Amarillo | Fairly Difficult / Plain English | Media |
| > 70 | 🟢 Verde | Easy | Baja |

#### Implementación Técnica

- **Librería:** `textstat` (Python)
- **Cálculo:** `textstat.flesch_reading_ease(texto_concatenado)`
- **Propiedades del modelo:** 
  - `fre_score`: float (score raw de FRE)
  - `readability_color`: str (color hex según el heatmap)
- **Ubicación del código:** 
  - Modelo: `src/domain/models.py:116-138` (propiedad `readability_color`)
  - Cálculo: `src/scripts/3b_generate_tree_visualization.py:34-42` (función `calculate_category_fre`)
