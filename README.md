# ACA 2 - RAG conversacional de ventas

Proyecto integrado de Computación en la Nube (CUN): continuidad de la base vectorial del ACA 1, generación con LLM, chat con historial, exploración documental y evaluación. **El código disponible, las ejecuciones verificadas y los entregables publicados son estados diferentes**: revisar `documentacion/estado_integracion.md` y los registros, no deducir aprobación por la existencia de este README.

El corpus tiene tres documentos académicos simulados. Sus políticas y plazos no son condiciones oficiales de Superstore; el dataset tabular aporta contexto, no reglas comerciales ni información en tiempo real.

## Arquitectura y archivos

- `rag_backend.py`: Qdrant Cloud de solo lectura, MiniLM multilingüe de 384 dimensiones, prompt, generación y validación estructural de citas.
- `reconstruir_qdrant.py`: preparación del corpus ACA 1 y creación protegida de una base propia; operación separada de la aplicación de consulta.
- `app.py`: Streamlit con **Chat con fuentes**, **Documentos y fragmentos** y **Supervisión del índice**; historial aislado por sesión y reinicio.
- `p1_adapter.py`: conexión del backend con la evaluación; el nombre conserva trazabilidad del reparto original, no un módulo pendiente de otro compañero.
- `banco_pruebas.py` / `evaluacion_aca2.py`: 12 casos, 13 turnos, cuatro controles funcionales, registros, revisión asistida y métricas con denominadores.
- `contenidos_p2.py` / `materiales_aca2.py`: documentación, guion y póster derivados de configuración/resultados reales.
- `referencia/`: versión saneada no ejecutable del ACA 1, recursos y guías. No ejecutar referencias como aplicación del ACA 2.

No hay funciones de inserción, borrado o recreación de la colección original. El panel consulta los datos efectivamente indexados; las cantidades locales de documentos/secciones no demuestran el conteo remoto de fragmentos.

## Reconstrucción de la base en una cuenta propia

El destino activo **publicado y verificado** es `superstore_rag_docs_aca2_propio` en el clúster propio `aca2-rag-brayan` de Qdrant Cloud (15 de noviembre de 2026). La colección del compañero no se altera. Se conservan tres documentos, dieciséis secciones y ocho consultas de la referencia del ACA 1; la comparación local está en `resultados/procedencia_reconstruccion_aca1.json`. Es una reconstrucción reproducible de las fuentes disponibles, no un snapshot ni una copia verificada del índice remoto.

Las secciones 4A y 4B del notebook separan preparación local y publicación cloud. La preparación crea documentos canónicos independientes de los Markdown de presentación (el parser ACA 1 exige encabezados con `|`), usa fragmentación 500/80 y verifica el tokenizer antes de producir embeddings normalizados de 384 dimensiones. Si un fragmento excede el límite del modelo, se bloquea y registra; no se trunca silenciosamente. La publicación requiere confirmación, un destino nuevo y credenciales propias. No recrea ni vacía colecciones existentes; una discrepancia se conserva como conflicto.

La preparación local incluida fue ejecutada realmente: **47 fragmentos**, embeddings normalizados **47 x 384**, máximo **108 tokens** frente al límite de **128**, cero fragmentos truncados. El manifiesto y las versiones utilizadas están en `resultados/embeddings_reconstruccion_local.json`. La publicación posterior en Cloud quedó acreditada por separado en `resultados/publicacion_cloud_propia_20261115.json`: 47 puntos y siete índices, con verificación integral del contenido remoto. La generación RAG se verificó después mediante 12 casos reales y 13 turnos; estos pasos constituyen evidencias distintas. El notebook reutiliza esos vectores comprobando sus hashes; la carpeta canónica de fuentes y la de vectores se conservan por separado.

Las consultas deben usar la misma revisión del modelo: `RAG_EMBEDDING_REVISION=e8f8c211226b894fcb81acc59f3b34ba3efd5f42`. La sección 4A la obtiene del manifiesto verificado y configura el backend. La revisión, colección y huella de reconstrucción quedan congeladas por corrida; no se exportan resultados antiguos bajo una configuración diferente.

El diagnóstico `resultados/recuperacion_local_reconstruida.json` ejecutó trece consultas con estos vectores en Qdrant **local en memoria**, sin Cloud ni LLM. Además, `resultados/recuperacion_cloud_real_20261115.json` registra **13 búsquedas autenticadas y reales en Qdrant Cloud**: 9 de 13 recuperaron todas las secciones de referencia y tres combinaciones de filtros cumplieron sus restricciones. C06 no recupera `ENV_SAME_DAY` con k=3; encontrar una sección tampoco garantiza recuperar todos sus pasajes. El caso C09 pide precios actuales ausentes del corpus y debe reconocer ese límite. Estos resultados miden recuperación, **no calidad de respuestas del LLM**; requieren evaluación posterior. El banco original se conserva para no ocultar fallos.

Durante la publicación mantener la colección nueva sin otros escritores. Las comprobaciones previas de IDs y contenido no son un bloqueo atómico frente a escrituras concurrentes; ante cualquier conflicto, la ingesta se detiene y no elimina datos.

El clúster gratuito **ya se creó** en la cuenta del equipo y su colección fue publicada y auditada. La [documentación de Qdrant](https://qdrant.tech/documentation/cloud/create-cluster/) describe condiciones de inactividad; el servicio gratuito no promete disponibilidad indefinida. Repetir las comprobaciones de índice, corpus, Top-k y RAG desde la sesión del Colab antes de presentar la demostración.

## Ruta principal: Colab AI

El notebook configura `RAG_LLM_BACKEND=colab_ai` y solicita `GEMINI_MODEL=google/gemini-3.8-flash` mediante `google.colab.ai.generate_text`. El SDK administra autenticación con el entorno autorizado; no se extraen tokens internos ni se incrusta una API key de Gemini.

La interfaz pública utilizada no expone temperatura, límite de salida, uso de tokens ni versión interna resuelta. En esta ruta se registran como no expuestos, no como cero ni como valores aplicados. El nombre mostrado es el identificador solicitado. Acceso y cuota dependen de la cuenta, modelo y disponibilidad del servicio; no se promete gratuidad ni acceso universal.

1. Abrir la copia integrada del Colab y ejecutar de arriba abajo las celdas preparatorias.
2. Guardar **`QDRANT_PROPIO_API_KEY`** en Secretos y conceder acceso a esa copia. La URL pública de la cuenta propia ya viene preconfigurada en el notebook; no contiene credenciales. `RAG_QDRANT_DESTINO=propio` evita leer las claves del compañero. No escribir el valor privado en el notebook, chat o documentación.
3. Comprobar el runtime y acceso al modelo con la celda de diagnóstico. La prueba del LLM y la de Qdrant se registran por separado: una no demuestra la otra.
4. Comprobar la reconstrucción desde 4A; la publicación desde 4B ya se realizó, así que dejar la escritura desactivada y verificar `superstore_rag_docs_aca2_propio` en las celdas de índice, corpus y búsqueda antes de la batería RAG.
5. Iniciar Streamlit con la celda del notebook. El subproceso debe heredar la configuración protegida. Abrir el enlace que devuelve el entorno; no reutilizar un proxy de una sesión anterior.
6. Consultar índice/documentos, enviar una pregunta real, abrir fuentes y probar un seguimiento.

El enlace de la app dentro de un runtime es **temporal**: necesita la sesión activa y los permisos apropiados. No equivale a una publicación persistente ni garantiza acceso anónimo del profesor. Los archivos de `/content` no se conservan porque el notebook esté guardado en Drive; descargar/guardar los resultados necesarios.

## Dependencias y ejecución fuera de Colab

Se recomienda Python 3.11 o superior. `requirements.txt` fija Streamlit 1.67.0, requests 2.34.2 y ReportLab 4.4.9, comprobados localmente, y recupera las versiones declaradas en ACA 1 de Sentence Transformers, Transformers, el fragmentador y Qdrant Client. No es un lock completo ni acredita ejecución RAG cloud en Python 3.13. Después de instalar, guardar versiones reales y verificar `pip check`; no copiar un freeze con rutas privadas o URLs autenticadas.

```bash
python -m venv .venv
# Activar .venv según el sistema operativo.
python -m pip install -r requirements.txt
python -m pip check
python -m unittest discover -p "test_*.py" -v
```

Fuera de Colab seleccionar la ruta opcional `gemini_api`. Esta llama directamente a Gemini REST, requiere una API key propia y puede consumir cuota del proveedor. No sustituye automáticamente la ruta evaluada: crear una corrida nueva si se cambia de backend/modelo.

Configurar las variables del proceso con un mecanismo seguro. Streamlit también admite un archivo local **no compartido** `.streamlit/secrets.toml` con claves raíz. Ejemplo de estructura, usando valores propios solamente en el entorno privado:

```toml
RAG_QDRANT_DESTINO = "propio"
QDRANT_PROPIO_URL = "https://TU_CLUSTER.cloud.qdrant.io"
QDRANT_PROPIO_API_KEY = ""
RAG_EMBEDDING_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
RAG_LLM_BACKEND = "gemini_api"
GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_API_KEY = ""
RAG_TEMPERATURE = "0"
RAG_MAX_OUTPUT_TOKENS = "1536"
RAG_TIMEOUT_S = "60"
```

El identificador de modelo REST debe estar disponible en la cuenta y confirmarse antes de ejecutar. No se garantiza esa disponibilidad ni se considera que la ruta REST se haya probado por documentarla aquí. `.env.example` es una referencia de nombres; el backend **no carga automáticamente un archivo `.env`**. No confundir esa plantilla con secretos configurados.

```bash
python -m streamlit run app.py
```

Al utilizar el backend desde un script local, las variables deben estar ya en `os.environ`; el archivo `secrets.toml` se procesa en el arranque de Streamlit, no por `p1_adapter` al importarse.

## Uso y evaluación

En la barra lateral seleccionar Top-k y filtros. Para la batería usar Todas/Todos; k=3 salvo C05, k=5. **Reiniciar conversación** limpia historial de la sesión, no documentos ni índice. En el chat revisar tanto fuentes citadas como contexto enviado; el score no es probabilidad de exactitud.

Registrar una versión de app/prompt/corpus/modelo por corrida. Ejecutar pruebas reales solo mediante la celda expresamente habilitada del notebook; no usar respuestas esperadas como resultados. Guardar todos los turnos de C07 y mantener conversaciones independientes entre casos. Los fallos, reintentos y bloqueos deben conservarse, no sustituirse por una corrida favorable sin trazabilidad.

### Evidencia RAG real del 15 de noviembre de 2026

Colab ejecutó **12 casos, 13 turnos y cero errores de ejecución** contra la colección propia de Qdrant Cloud y el LLM solicitado `google/gemini-3.8-flash`. La latencia media del adaptador fue **7,2192 segundos**. El registro `resultados/evaluacion_llm_real_20261115.json` conserva las respuestas originales. Los casos **C02** y **C06** quedaron inicialmente incompletos con `top_k=3`; se conservaron y se reensayaron con éxito utilizando **`top_k=5`**, registrados por separado en `resultados/evaluacion_reensayo_top5_20261115.json`. La revisión en `resultados/revision_asistida_20261115.json` es asistida y requiere validación humana. Se distingue expresamente de las pruebas visuales de Streamlit y de la disponibilidad pública permanente, pendientes de verificación.

El evaluador usa revisión documentada de afirmaciones y citas. Si la realiza un asistente, identificarla como **revisión asistida**; la confirmación humana del equipo no se presume. Los tests offline y los AppTest con fixtures verifican contratos/renderizado, no la calidad ni conectividad real del LLM/Qdrant.

- Fidelidad: afirmaciones respaldadas / afirmaciones revisadas.
- Respuestas sustentadas: casos respondibles que cumplen criterios / casos respondibles revisados. Se excluyen abstenciones y aclaración.
- Citas válidas: atribuciones realmente revisadas y respaldadas / atribuciones revisadas.
- Abstención: casos correctos / casos de abstención revisados; informar cobertura de los tres previstos.
- Latencia del adaptador: pipeline hasta respuesta completa, sin render de UI. No mezclar con cronómetro de interfaz en una misma corrida.
- `null`: pendiente/no calculable; no rendimiento cero ni éxito implícito.

F01-F04 requieren evidencias de panel, sesiones, errores y reproducibilidad. Una prueba con dependencia simulada debe declararse como tal y no acredita por sí sola una observación real completa de UI. No hay un umbral numérico oficial de aprobación.

## Generar documentación y materiales

`config_proyecto.json` contiene metadatos públicos y ubicaciones de evidencias, nunca claves. Antes de generar, seleccionar explícitamente el registro de la corrida evaluada. `generar_entrega.py` conserva el registro histórico `datos/corrida_01.json`; no asumir que es la última corrida si se creó otra. La celda de entrega del notebook debe pasar el registro actual a `generar_todo`.

```python
from pathlib import Path
from evaluacion_aca2 import cargar_json
from materiales_aca2 import generar_todo

base = Path.cwd()
config = cargar_json(base / "config_proyecto.json")
corpus = cargar_json(base / "corpus_fuente.json")
# Sustituir por la corrida real elegida; no por resultados de tests sintéticos.
registro = cargar_json(base / "datos" / "corrida_01.json")
generar_todo(base, config, registro, corpus)
```

El generador distingue configuración/evidencia técnica, evaluación y cierre editorial/publicación. Un video pendiente no significa que el código del LLM falte, pero impide declarar la entrega completa. Inspeccionar visualmente los PDF antes de entregar.

## Seguridad y continuidad

No incluir `.env` reales, `secrets.toml`, claves, cookies, tokens, cachés privados ni capturas sensibles. La guía del profesor prohíbe credenciales públicas aunque el corpus sea simulado. Quitar una clave del código o moverla a Secretos **no la revoca ni elimina revisiones anteriores de Drive**. El uso autorizado de una clave heredada no permite marcarla como rotada; informar ese pendiente por separado.

El escaneo de archivos es heurístico y complementa la revisión; no garantiza ausencia de todos los secretos. El original ACA 1 permanece como referencia y no debe sobrescribirse para simplificar este trabajo.

## Entrega oficial y pasos humanos

Los cuatro entregables son notebook técnico, póster PDF, aplicación/código en GitHub y video de 3 a 5 minutos. El ZIP es respaldo y no los sustituye. Antes del cierre: confirmar autores, revisar resultados asistidos, grabar voz real, medir duración y comprobar enlaces/permisos de app, repositorio y video. No publicar como terminadas las piezas que no tienen evidencia real.
