"""Contenido integrado ACA 2; no contiene resultados ficticios.

Los marcadores [[...]] se completan desde configuración y registros reales.
El nombre histórico se conserva por compatibilidad. No hay red al importar.
"""

REFERENCIAS = sorted([
    "Google. (s. f.). *Colaboratory frequently asked questions*. https://research.google.com/colaboratory/faq.html",
    "Google Colaboratory. (s. f.). *Colaboratory tools* [Código fuente]. GitHub. https://github.com/googlecolab/colabtools",
    "Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., "
    "Küttler, H., Lewis, M., Yih, W.-t., Rocktäschel, T., Riedel, S., & Kiela, D. "
    "(2020). *Retrieval-augmented generation for knowledge-intensive NLP tasks* "
    "[Prepublicación]. arXiv. https://arxiv.org/abs/2005.11401",
    "Qdrant. (s. f.). *Search*. https://qdrant.tech/documentation/search/search/",
    "Streamlit. (s. f.). *Secrets management*. https://docs.streamlit.io/develop/concepts/connections/secrets-management",
])

DOCUMENTOS = {
    "manual_verificacion.md": r"""# Manual de uso y verificación del proyecto integrado

## Estado y alcance

Este expediente reúne implementación técnica y evaluación del ACA 2. Los nombres P1/P2 se conservan en algunos archivos por trazabilidad del reparto original; ya no representan módulos que deba construir otro compañero. La existencia del código no acredita por sí sola conectividad, resultados, publicación o video: consultar el registro de ejecución y el estado de cierre.

El profesor exige un LLM real, recuperación sobre la base vectorial del ACA 1, chat con historial, fuentes, panel documental, evaluación, notebook, GitHub, póster y video de 3 a 5 minutos. Los 12 casos/13 turnos y 4 controles son la propuesta del equipo. No exige varios LLM, entrenamiento ni CRUD completo.

## Configuración que identifica esta versión

- Modelo solicitado: [[MODELO]]. Proveedor/modalidad: [[PROVEEDOR]].
- Aplicación: [[VERSION_APP]]. Prompt: [[VERSION_PROMPT]].
- Corpus académico simulado: versión 1.0.0, tres documentos y dieciséis secciones locales.
- Embeddings: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2; 384 dimensiones; similitud coseno.
- Colección histórica ACA 1: superstore_rag_docs; no se modifica. Destino propio publicado: superstore_rag_docs_aca2_propio (clúster aca2-rag-brayan, 15/11/2026).
- Reconstrucción: mismo corpus local y pipeline de ACA 1. No es una restauración del índice remoto inaccesible. Publicación cloud real: 47 puntos, siete índices; evidencia en resultados/publicacion_cloud_propia_20261115.json.
- La aplicación solamente consulta la colección elegida; la ingesta propia es un paso separado y explícitamente autorizado.
- Top-k: tres por defecto; cinco en C05, por requerir soporte y garantía de fuentes distintas.
- Parámetros generativos: [[PARAMETROS]].
- App: [[APP_URL]]. Código: [[REPO_URL]].

La ruta Colab AI usa `google.colab.ai.generate_text` y autenticación administrada por el SDK. No requiere copiar una API key de Gemini. El identificador solicitado no equivale a una versión interna resuelta: el SDK utilizado no la expone, ni expone temperatura, límite de salida o uso de tokens. No se afirma que valores configurados para REST se hayan aplicado en esta ruta.

Gemini REST es una ruta opcional para ejecución fuera de Colab y sí utiliza GEMINI_API_KEY. Tiene parámetros propios; cambiar de ruta/modelo requiere otra corrida. No se declara evaluada por el solo hecho de estar implementada.

## Base vectorial propia sin depender del compañero

La comparación por AST de los recursos saneados acredita coincidencia local de los tres documentos, dieciséis secciones y ocho consultas del ACA 1. La evidencia es resultados/procedencia_reconstruccion_aca1.json. No se pudo consultar el índice remoto; su causa de indisponibilidad no está confirmada.

La sección 4A del notebook reconstruye documentos canónicos en una carpeta separada, con encabezados compatibles con el parser original. Mantiene fragmentación de 500 caracteres y solapamiento objetivo de 80, el mismo modelo MiniLM, 384 dimensiones, vectores normalizados y Cosine. Se audita la longitud real del tokenizer antes de publicar; un exceso bloquea la ingesta y no se recorta silenciosamente.

La sección 4B opera contra un clúster Qdrant Cloud propio ya creado. Su URL pública está preconfigurada y la clave QDRANT_PROPIO_API_KEY se lee por Secretos de Colab; RAG_QDRANT_DESTINO=propio impide reutilizar las claves antiguas. La operación crea exclusivamente una colección nueva o verifica una reconstrucción coincidente; no borra, recrea ni sobrescribe la base del compañero. La publicación y auditoría se ejecutaron el 15/11/2026: 47 puntos y siete índices, con comparación de hashes y metadatos remotos. El cambio de despliegue debe declararse al docente; no se presupone equivalencia bit a bit con el servicio original ni aceptación académica automática.

El diagnóstico local usa los 47 vectores reales en memoria, sin Cloud ni LLM. Además, una batería independiente hizo 13 búsquedas **reales en Qdrant Cloud**: 9/13 recuperaron todas las secciones de referencia, y los tres filtros combinados cumplieron sus reglas (`resultados/recuperacion_cloud_real_20261115.json`). C06 no recupera ENV_SAME_DAY con k=3, C09 solicita precios actuales ausentes y C11/C12 evidencian límites de cobertura. Esto prueba conectividad, búsqueda y filtros, **no fidelidad del LLM ni aprobación de respuestas**. Mantener la colección sin otros escritores durante una eventual nueva publicación: los controles previos no constituyen una exclusión atómica.

## Cómo utilizar la interfaz

1. Ejecutar las celdas de preparación y configuración del notebook. Los secretos se leen por el mecanismo seguro previsto, sin imprimir valores. Verificar que runtime y modelo estén disponibles.
2. Abrir la aplicación. Mantener visibles el aviso de corpus simulado y el modelo solicitado. El enlace de un runtime Colab es temporal, no un despliegue persistente.
3. En **Supervisión del índice**, pulsar **Verificar índice ahora**. Revisar estado y conteos obtenidos del servicio; un error debe aparecer como indisponibilidad.
4. En **Documentos y fragmentos**, pulsar **Consultar documentos**, escoger una fuente y abrir fragmentos/metadatos. La vista puede estar paginada: una página no equivale al total del índice.
5. En **Chat con fuentes**, escribir en **Pregunta sobre el corpus de ventas…** y enviar. **Fragmentos Top-k**, **Categoría** y **Modo de envío** limitan recuperación; dejar Todas/Todos para el banco sin filtros.
6. Leer respuesta y **Fuentes citadas por el modelo**; abrir el contexto enviado al LLM y contrastar una afirmación con su evidencia.
7. Hacer seguimientos sin reiniciar. **Reiniciar conversación** permite empezar otro caso; no borra corpus ni colección.

No copiar un secreto al chat para comprobar el sistema. No se consultan precios, inventario ni ubicaciones de pedidos en tiempo real.

## Ejecución y revisión

Congelar modelo, versión de app/prompt, corpus, colección, embedding, k y filtros antes de cada corrida. Conservar pregunta, historial, respuesta original, fuentes, contexto, tiempos, errores y reintentos. El evaluador impide sobrescribir casos ejecutados; usar otra corrida después de corregir.

Un mock o test unitario no se registra como respuesta real. Una lista de fragmentos tampoco acredita generación. La revisión de calidad es **asistida** cuando la realiza el asistente; identificarlo en revisor y observaciones. La confirmación del equipo es un paso distinto, no se presupone realizada.

Comprobar pertinencia, completitud, respaldo de cada afirmación, citas, historial y reconocimiento de límites. Leer los pasajes: una fuente existente o similitud alta no demuestra fidelidad. Una afirmación correcta sin respaldo en el contexto de ese turno no acredita recuperación documentada.

C08 y C09 deben abstenerse por falta de evidencia; C11 debe rechazar la política inventada. C12 debe aclarar el producto/caso. Una abstención injustificada en una pregunta respondible no es éxito de completitud.

## Métricas

- Fidelidad: afirmaciones materiales respaldadas / afirmaciones materiales revisadas.
- Respuestas sustentadas: casos respondibles que cumplen todos los criterios / casos respondibles revisados. Excluye tres abstenciones y C12; ocho casos potenciales con evidencia.
- Citas válidas: atribuciones existentes y pertinentes / atribuciones emitidas revisadas. Mantener la misma unidad de conteo.
- Abstención: advertencias correctas / casos de abstención revisados; informar cobertura de los tres previstos.
- Latencia del adaptador: pipeline hasta respuesta completa, sin renderizado de navegador. La medición manual UI es otra modalidad; no mezclarlas en una corrida.
- `null` o pendiente: no calculable/no medido, nunca cero de calidad. Errores y espera agotada se informan aparte.

Una batería pequeña no garantiza calidad general ni ausencia de alucinaciones. Los tests offline verifican código, no disponibilidad de nube.

## Controles funcionales

F01 compara documentos/metadatos/fragmentos con el índice consultado. Tres documentos y dieciséis secciones no implican dieciséis puntos: consultar chunks remotos.

F02 comprueba seguimiento, reinicio y dos sesiones independientes; el historial no debe compartirse globalmente.

F03 rechaza entrada vacía y observa un fallo controlado sin invalidar claves reales. Identificar la dependencia simulada: no acredita conectividad ni rendimiento cloud.

F04 instala y ejecuta en entorno limpio, verifica README, dependencias y seguridad. No marcar observación de UI completa a partir solo de inspección o mocks.

## Evidencias, seguridad y entrega

Capturas de chat complejo, historial, abstención y panel deben proceder de la app real, omitiendo claves, correos privados y notificaciones. Conservar fallos relevantes; no reconstruir pantallas con respuestas esperadas.

La guía prohíbe credenciales en repositorios públicos. Una clave heredada puede usarse con autorización para consultar, pero eso no significa que haya sido rotada. Retirarla del código no la revoca ni elimina versiones previas de Drive. Registrar rotación por separado.

Confirmar autores, revisar conclusiones, grabar voz real y verificar enlaces finales. El guion de 4:30 incluye navegación y esperas; comprobar que el archivo audiovisual final dura entre 3 y 5 minutos.
""".strip(),

    "informe_integrante2.md": r"""# Informe del proyecto integrado ACA 2

## Identificación

Institución: CUN. Asignatura: Computación en la Nube. Pilar: Ventas.

Autores: [[AUTORES]]. Estado de confirmación: [[ESTADO_AUTORES]].

App: [[VERSION_APP]]. Prompt: [[VERSION_PROMPT]]. Modelo solicitado: [[MODELO]].

Acceso app: [[APP_URL]]. Repositorio: [[REPO_URL]]. Video: [[VIDEO_URL]].

## Problema y objetivo

Las consultas comerciales pueden requerir relacionar devoluciones, logística y ayuda técnica. Recuperar fragmentos permite localizar evidencia, pero no produce necesariamente una respuesta conversacional integrada. Un modelo generativo puede sintetizarla y también añadir afirmaciones no sustentadas.

El objetivo es integrar un LLM con la base vectorial del ACA 1 y una interfaz de chat que conserve historial, muestre fuentes, permita explorar documentos y reconozca información ausente. La pregunta orientadora es cómo construir una consulta comercial trazable sin atribuir al corpus condiciones que no contiene.

## Corpus y límites

Se conserva Ventas y el corpus del ACA 1: tres documentos de devoluciones/garantías, SLA/logística y catálogo/soporte, con dieciséis secciones. El CSV de Superstore aporta contexto tabular y categorías, no demuestra políticas, ventanas de garantía ni tiempos de entrega reales.

Las reglas son simuladas; no representan condiciones oficiales de Superstore, derechos legales ni asesoría especializada. General/All son convenciones de alcance, no categorías del CSV. No existen precios actuales, inventario ni estados de pedidos en vivo en este corpus. No se necesitan nombres de clientes para la demostración.

## Arquitectura implementada

Streamlit conserva el diálogo por sesión. El backend combina pregunta e historial pertinente para recuperar, genera embeddings con MiniLM multilingüe y consulta la colección configurada de Qdrant Cloud en modo de solo lectura. Ante la indisponibilidad de la conexión heredada, se prepara una reconstrucción propia desde el corpus local de ACA 1, cuya publicación debe verificarse por separado. Conserva texto, documento, sección, metadatos y score de los Top-k.

El prompt delimita contexto, historial e instrucciones; exige evidencia, citas de fragmento y abstención/aclaración cuando falte información. El LLM genera salida estructurada. El backend comprueba correspondencia entre citas emitidas y fragmentos disponibles; la UI muestra respuesta, fuentes y contexto. Este control estructural no demuestra respaldo semántico por sí solo: se complementa con revisión asistida documentada.

El panel consulta documentos, metadatos, fragmentos, estado y conteos del índice. No incorpora borrado ni recreación. Notebook y app.py utilizan el mismo backend. La ejecución verificable se acredita mediante el registro, no por esta descripción del código.

## Modelo y decisiones

Proveedor/modalidad: [[PROVEEDOR]]. Modelo solicitado: [[MODELO]].

Justificación registrada: [[JUSTIFICACION]]. Limitación registrada: [[LIMITACION_LLM]].

Colab AI administra autenticación mediante `google.colab.ai.generate_text`, sin incrustar una API key de Gemini. El SDK utilizado no expone temperatura, límite de salida, tokens ni versión interna resuelta; se documenta la limitación en lugar de inventar valores. El identificador mostrado es el solicitado.

Existe una alternativa Gemini REST para ejecución fuera de Colab. Tiene clave del entorno y parámetros propios; sus resultados no se consideran probados o equivalentes salvo corrida separada.

Top-k se mantiene en tres para preguntas simples y cinco para C05 multifuente: decisión del protocolo, no exigencia numérica del docente. MiniLM realiza embeddings, no es el LLM generativo.

## Evaluación registrada

Doce casos/trece turnos prefijados cubren consultas directas, combinación de fuentes, paráfrasis, seguimiento, ausencia de evidencia, premisa falsa, petición de inventar y ambigüedad. Cuatro controles revisan panel, historial, errores y reproducibilidad.

Casos completos reales: [[N_CASOS]] de 12. Revisados: [[N_REVISADOS]] de 12. Controles funcionales revisados: [[N_FUNCIONALES]] de 4.

[[TABLA_RESULTADOS]]

La latencia de pipeline se diferencia del renderizado de UI. La revisión asistida identifica afirmaciones/citas respaldadas; no equivale automáticamente a revisión humana del equipo. Conservar fallos y correcciones por versión. Las autopruebas del código se presentan separadas de la batería real.

## Conclusiones y limitaciones

La implementación reúne búsqueda, generación, conversación y exploración documental. Su calidad debe juzgarse por la relación entre respuesta y evidencia, no por fluidez, nombre del modelo o puntuación vectorial.

Las métricas describen únicamente ejecuciones y revisiones registradas. Sin revisión no se concluye fidelidad; pendiente no significa fracaso ni éxito. Corpus pequeño y simulado limita generalización. La disponibilidad depende de servicios/runtime y un enlace temporal de Colab no garantiza acceso persistente.

Estado técnico, evaluación, publicación y video se verifican por separado en estado_integracion.md. Confirmar autores, permisos, referencias y versión antes de entregar. No presentar un póster con pendientes editoriales como entrega final completa.

## Rúbrica

Integración RAG 20%; configuración LLM 20%; interfaz 20%; fidelidad 15%; póster 15%; video 10%. Los pesos califican el proyecto, no la dedicación individual. El reparto preserva trazabilidad sin atribuir una validación independiente humana que no ocurrió.
""".strip(),

    "handoff_persona1.md": r"""# Handoff del proyecto integrado al equipo

## Continuidad

El nombre histórico de este archivo se conserva por compatibilidad. Implementación y evaluación se reúnen en el mismo paquete; ya no se espera que otro compañero construya LLM, backend o interfaz. Los pendientes son los del registro y checklist actuales, no los del plan inicial.

## Componentes

- rag_backend.py: configuración, recuperación Qdrant, prompt, Colab AI/alternativa REST, citas y errores seguros.
- reconstruir_qdrant.py: reconstrucción trazable del ACA 1 y creación protegida de una colección propia. No sustituye la validación cloud ni modifica el índice del compañero.
- p1_adapter.py: contrato entre backend real y evaluador.
- app.py: chat con historial por sesión, fuentes, fragmentos, documentos e índice.
- banco_pruebas.py / evaluacion_aca2.py: expectativas prefijadas, ejecución, revisión asistida y métricas.
- materiales_aca2.py / contenidos_p2.py: documentación, guion y póster derivados del registro; no generan respuestas ficticias.
- referencia/: ACA 1 saneado y guías; no ejecutar esas referencias como la aplicación nueva.

## Información de entrega

| Campo | Dato registrado |
| --- | --- |
| App / prompt | [[VERSION_APP]] / [[VERSION_PROMPT]] |
| Modelo solicitado | [[MODELO]] |
| Proveedor/modalidad | [[PROVEEDOR]] |
| Parámetros | [[PARAMETROS]] |
| App | [[APP_URL]] |
| Código | [[REPO_URL]] |
| Video | [[VIDEO_URL]] |
| Corpus | Simulado 1.0.0; tres documentos / dieciséis secciones locales |
| Embeddings / índice propio previsto | MiniLM multilingüe; 384 dimensiones; Cosine; superstore_rag_docs_aca2_propio |
| Casos reales completos / revisados | [[N_CASOS]] / [[N_REVISADOS]] |

Consultar las cantidades remotas: no deducir chunks desde secciones locales. Las claves no forman parte de estas tablas ni del paquete.

## Cierre del equipo

Comprobar cuatro entregables y permisos. Una llamada real breve al modelo no acredita toda la batería ni la UI; tests offline no acreditan conectividad. Conservar fallos y corridas anteriores.

Confirmar autores, revisar resultados, capturar la app y grabar el video de 3-5 minutos. Verificar URLs de repositorio/video e indicar que el proxy Colab es temporal. Guardar una clave en Secretos no equivale a revocarla.
""".strip(),

    "checklist_entrega.md": r"""# Checklist de entrega integrada ACA 2

Marcar únicamente con evidencia. Es un control del equipo, no un certificado ni resultado automático de tests.

## Implementación y evaluación

- [ ] Se preservó corpus/pilar ACA 1 y se documentó la reconstrucción propia sin alterar la colección del compañero.
- [ ] Se verificó Qdrant, dimensión, embeddings, metadatos y Top-k real.
- [ ] El LLM produjo respuestas reales y se identifica el modelo solicitado sin inventar versión interna.
- [ ] Se explica que Colab AI no expone temperatura, tokens ni versión resuelta; no se atribuyen parámetros REST a esa ruta.
- [ ] Chat, seguimiento, reinicio, aislamiento, fuentes y panel probados en UI real.
- [ ] Vacío y errores controlados sin secretos; fallos simulados identificados.
- [ ] Registro de preguntas, respuestas, citas, contexto, tiempos, versiones e incidencias.
- [ ] Revisión identificada como asistida; confirmación humana del equipo diferenciada.
- [ ] Denominadores explícitos; latencia pipeline/UI separada; tests offline distintos de casos reales.
- [ ] README y notebook probados en entorno limpio con dependencias declaradas.

## Notebook y código GitHub

- [ ] Notebook ordenado: instalación, secretos, recuperación, generación y diálogos con citas.
- [ ] App, auxiliares, requirements y README en repositorio real accesible.
- [ ] Versiones instaladas registradas; un rango no se presenta como lock probado.
- [ ] Sin claves, .env reales, secrets.toml, tokens ni datos personales en código, historial público o salidas.

## Póster

- [ ] Autores confirmados, objetivo, problema y pilar Ventas.
- [ ] Arquitectura Qdrant cloud, embeddings, contexto, LLM, UI e historial.
- [ ] Capturas reales de chat/citas y documentos/índice sin información sensible.
- [ ] Ejemplo observado, métricas registradas, conclusiones y límites del corpus.
- [ ] Referencias APA 7, PDF legible de alta resolución, enlaces reales app/GitHub/video.
- [ ] Se retiraron marcadores y estados provisionales resueltos; pendientes verdaderos visibles.

## Video y publicación

- [ ] Grabación real con narración del equipo; un guion no se entrega como video.
- [ ] Duración 3:00-5:00, incluida navegación/esperas.
- [ ] Explicación LLM/arquitectura y demo compleja, seguimiento, citas y panel.
- [ ] Consulta sin evidencia mostrada sin sustituir la respuesta por texto preparado.
- [ ] App, repositorio y video abren con permisos necesarios; enlaces temporales identificados.
- [ ] Autores, versiones, datos, capturas, póster y video coherentes.

## Seguridad independiente

- [ ] Clave previamente expuesta revocada/rotada y nueva conexión comprobada, si corresponde. No marcar por guardar la heredada en Secretos.
- [ ] Permisos y antecedentes de exposición revisados antes de publicar.

Cuatro entregables: notebook, póster PDF, app/código GitHub y video. El ZIP es respaldo, no sustituto. Rúbrica: 20/20/20/15/15/10.
""".strip(),
}

DOCUMENTOS["informe_integrante2.md"] += "\n\n## Referencias\n\n" + "\n\n".join(REFERENCIAS) + "\n"

GUION_BLOQUES = [
    {
        "tiempo": "0:00-0:30",
        "pantalla": "Antes de grabar, confirmar autores y abrir póster/app. Mostrar título, autores, pilar Ventas y objetivo del póster. No abrir Secretos ni la cuenta Google. Completar cualquier dato pendiente antes de narrar.",
        "locucion": "Somos [[AUTORES]] y presentamos el ACA dos de Computación en la Nube de la CUN. Trabajamos en el pilar de ventas. Integramos búsqueda documental y un modelo de lenguaje para consultar devoluciones, logística y soporte, con fuentes visibles e historial. Los tres documentos son una simulación académica: sus reglas no representan políticas comerciales reales de una empresa.",
    },
    {
        "tiempo": "0:30-1:10",
        "pantalla": "Enfocar arquitectura del póster: Streamlit, MiniLM, Qdrant cloud, contexto, Colab AI/Gemini y respuesta con fuentes. Señalar el identificador solicitado del modelo. Pasar a la app y abrir Chat con fuentes.",
        "locucion": "Usamos el modelo [[MODELO]] mediante [[PROVEEDOR]]. La conexión Colab AI utiliza la autenticación del entorno y evita incrustar una clave de Gemini. Esta interfaz no expone temperatura, consumo de tokens ni versión interna resuelta, por eso no inventamos esos valores. MiniLM convierte la consulta en un vector; Qdrant recupera fragmentos pertinentes. El contexto y las instrucciones llegan al modelo, que redacta una respuesta con citas. Streamlit permite conversar y revisar evidencia.",
    },
    {
        "tiempo": "1:10-2:40",
        "pantalla": "Configurar Fragmentos Top-k = 5, Categoría = Todas, Modo de envío = Todos. Pulsar Reiniciar conversación. En Chat con fuentes enviar C05: «Recibí un teléfono hace treinta días y ya no carga. Quiero conservar mis archivos. Según estos documentos académicos, ¿qué reviso primero y qué información necesito para tramitar la garantía si la falla continúa?». Esperar respuesta completa. Mostrar Fuentes citadas por el modelo y abrir los fragmentos de soporte/garantía que aparezcan. Sin reiniciar, enviar «¿Debo restaurarlo de fábrica como primer paso?». Mostrar respuesta real. Este seguimiento de demo no se incluye automáticamente en las métricas del banco.",
        "locucion": "La primera consulta combina dos necesidades: un teléfono dejó de cargar y queremos conservar sus archivos, pero también entender el trámite de garantía del ejercicio. Usamos cinco fragmentos porque puede necesitar evidencia de soporte y devoluciones. Esperamos la respuesta completa y revisamos qué partes logra responder. Ahora abrimos las fuentes. No basta con mostrar un nombre: el pasaje debe respaldar la afirmación correspondiente. Comparamos especialmente la orientación inicial, la protección de archivos y las condiciones de la garantía simulada. Sin reiniciar, preguntamos si debemos restaurar el equipo de fábrica como primer paso. Así comprobamos si conserva el contexto del teléfono y sus archivos. Si falta evidencia, debe reconocerlo; no puede llenar el vacío con una promesa. Mostramos la respuesta obtenida en esta sesión, no un texto de ejemplo preparado.",
    },
    {
        "tiempo": "2:40-3:25",
        "pantalla": "Abrir Documentos y fragmentos; pulsar Consultar documentos si falta la consulta. Seleccionar una fuente citada y mostrar texto/metadatos. Abrir Supervisión del índice, pulsar Verificar índice ahora y mostrar cifras reales. No mostrar claves.",
        "locucion": "En el panel revisamos fuentes almacenadas, metadatos y contenido de sus fragmentos. Podemos relacionar una cita del chat con su documento. La vista puede estar paginada: distinguimos esta página del total de la colección. En supervisión consultamos el estado real del índice. La aplicación solo consulta; reiniciar una conversación no borra la base. Un fallo debe mostrarse como indisponibilidad, nunca como un estado operativo inventado.",
    },
    {
        "tiempo": "3:25-3:55",
        "pantalla": "Volver a Chat con fuentes, Reiniciar conversación y enviar C09: «¿Cuál es el precio exacto de venta de hoy de un teléfono y qué descuento vigente tiene?». Esperar y mostrar resultado real. Si inventa cifras, señalar fallo; no leer una explicación de éxito.",
        "locucion": "Ahora preguntamos por precio y descuento vigente. El tema es comercial, pero esos datos no están en el corpus. Comprobamos que reconozca la limitación y no convierta una venta histórica en una oferta de hoy. Mostramos lo que responde realmente y revisamos si evita inventar importes o afirmar una consulta en tiempo real.",
    },
    {
        "tiempo": "3:55-4:30",
        "pantalla": "Regresar al póster: resultados registrados, límites y enlaces. No narrar pendientes como resultados. Ensayar incluyendo esperas reales, detener cerca de 4:30 y comprobar duración final 3-5 minutos.",
        "locucion": "El registro conserva [[N_CASOS]] casos completos con ejecución real y [[N_REVISADOS]] con revisión documentada. Las métricas se leen con denominadores y tipo de revisión, identificada como asistida hasta confirmación del equipo. El tiempo del adaptador mide el pipeline, no todo el navegador. Corpus y muestra son pequeños; no garantizan todas las respuestas futuras. El valor del prototipo está en relacionar respuesta y evidencia y reconocer límites. Gracias por acompañarnos.",
    },
]
