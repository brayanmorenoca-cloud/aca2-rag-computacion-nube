"""Requisitos del ACA 2 integrado y trazabilidad del reparto original.

Fuentes leídas completas:
- ACA_2_Computacion_Nube_RAG_CUN.pdf, 6 páginas. La rúbrica y los entregables
  oficiales están en las páginas 4 y 5; el alcance funcional, en las páginas 1 a 3.
- Distribucion_ACA_2_Computacion_Nube_RAG.pdf, 6 páginas. La distribución es una
  propuesta de organización; las tareas P2 están en la página 3, las pruebas en
  la página 4 y el cierre en las páginas 5 y 6.

Este módulo contiene datos, no resultados de ejecución ni calificaciones.
No ejecuta notebooks, consulta servicios, carga credenciales o modifica índices.
RUBRICA usa peso entero y los demás campos como texto. ENTREGABLES y BANDERAS
son listas de texto para tablas, documentos o listas de verificación.
"""

RUBRICA = [
    {
        "criterio": "Integración RAG",
        "peso": 20,
        "exigencia": (
            "Conectar la base vectorial del ACA 1 con el LLM, recuperar contexto "
            "semánticamente pertinente e incorporarlo correctamente en el prompt. "
            "Se mantiene el pilar y corpus del ACA 1. Guía oficial, pp. 2-4."
        ),
        "evidencia": (
            "Ejecución real y reproducible con pregunta, fragmentos Top-k, "
            "identificación de fuentes, contexto suministrado al LLM y respuesta "
            "generada. Registrar versión del sistema y del corpus."
        ),
        "aporte_p2": (
            "Preparar casos y evidencia esperada desde el corpus; comprobar la "
            "recuperación y su relación con la respuesta; registrar fallos y "
            "repetir los casos afectados después de corregir el bloque técnico."
        ),
        "depende_p1": (
            "Bloque técnico integrado: conexión, pipeline, formato de fuentes e "
            "instrucciones. Debe acreditarse ejecución end-to-end; disponer del "
            "código o de una prueba aislada del LLM no acredita recuperación cloud."
        ),
    },
    {
        "criterio": "Configuración LLM",
        "peso": 20,
        "exigencia": (
            "Implementar correctamente un LLM local o mediante API, justificar "
            "sus hiperparámetros y gestionar las credenciales con variables de "
            "entorno o secretos de la plataforma. Guía oficial, pp. 3-5."
        ),
        "evidencia": (
            "Identificación del modelo y modalidad, parámetros documentados, "
            "justificación de la elección, llamada real al LLM y revisión de "
            "código y salidas sin divulgar valores de credenciales."
        ),
        "aporte_p2": (
            "Revisar y explicar la elección y parámetros reales; contrastar la "
            "documentación con la implementación y comprobar las instrucciones "
            "de ejecución y el tratamiento seguro de secretos."
        ),
        "depende_p1": (
            "Modelo y adaptadores están incluidos en el bloque técnico. Registrar "
            "modelo solicitado, ruta efectiva y justificación sin inventar costos, "
            "cuotas, parámetros no expuestos o versión interna del proveedor."
        ),
    },
    {
        "criterio": "Interfaz Gráfica (UI)",
        "peso": 20,
        "exigencia": (
            "Aplicación interactiva con chat e historial conversacional, "
            "visualización de fuentes citadas y panel de consulta y exploración "
            "de documentos, metadatos y fragmentos recuperados. Guía oficial, "
            "pp. 3 y 4."
        ),
        "evidencia": (
            "Recorrido real del chat y de un seguimiento conversacional; "
            "capturas de respuestas con fuentes y del panel documental; "
            "comprobación de acceso a la aplicación."
        ),
        "aporte_p2": (
            "Preparar el recorrido y los criterios; probar chat, historial, "
            "fuentes y panel; documentar uso y limitaciones y recoger capturas "
            "de la versión que realmente se evaluó."
        ),
        "depende_p1": (
            "Frontend y backend forman parte del proyecto integrado; la UI "
            "requiere pruebas reales de historial, fuentes y panel. Tests con "
            "fixtures verifican renderizado/contratos, no conectividad cloud."
        ),
    },
    {
        "criterio": "Fidelidad de Respuestas",
        "peso": 15,
        "exigencia": (
            "Respuestas fundamentadas estrictamente en la evidencia indexada, "
            "citas de fuentes y mitigación de alucinaciones; advertencia cuando "
            "no existe información. Evaluar consultas complejas, fuera de "
            "contexto y tiempo de respuesta. Guía oficial, pp. 3 y 4."
        ),
        "evidencia": (
            "Casos prefijados con pregunta, contexto del diálogo, fuente "
            "esperada, respuesta obtenida, citas, tiempo y juicio de "
            "pertinencia y fidelidad; registrar aciertos, fallos y denominadores."
        ),
        "aporte_p2": (
            "Definir expectativas antes de observar respuestas, ejecutar la "
            "validación, revisar si las citas respaldan lo afirmado, calcular "
            "métricas con criterios explícitos y redactar límites y conclusiones."
        ),
        "depende_p1": (
            "La batería y el adaptador están integrados; mediciones y conclusiones "
            "requieren recuperación y generación reales. Identificar la revisión "
            "asistida. Resultados ACA 1 y autopruebas no acreditan fidelidad ACA 2."
        ),
    },
    {
        "criterio": "Póster Infografía (PDF)",
        "peso": 15,
        "exigencia": (
            "Póster visual y sintético con nombres, objetivo, problema, pilar, "
            "arquitectura RAG completa, stack, capturas, ejemplos de interacción "
            "con citas y conclusiones. PDF de alta resolución con APA 7 y "
            "enlaces funcionales a aplicación, código y video. Guía oficial, "
            "pp. 4 y 5."
        ),
        "evidencia": (
            "PDF final legible, referencias pertinentes, arquitectura y "
            "capturas de la versión implementada; ejemplos y conclusiones "
            "respaldados por pruebas y tres hipervínculos comprobados."
        ),
        "aporte_p2": (
            "Diseñar la base en paralelo; redactar contexto, corpus y "
            "referencias; completar la arquitectura real, evidencias y "
            "conclusiones; exportar y revisar el PDF final."
        ),
        "depende_p1": (
            "La arquitectura describe el código integrado. Estado técnico, "
            "capturas, resultados, autores y publicación se comprueban por "
            "separado; cualquier cierre editorial pendiente mantiene el borrador."
        ),
    },
    {
        "criterio": "Sustentación en Video",
        "peso": 10,
        "exigencia": (
            "Video de 3 a 5 minutos: justificación de la opción LLM, "
            "arquitectura RAG, demostración en vivo del chatbot con consultas "
            "complejas y gestión documental, y sustentación del póster. "
            "Guía oficial, pp. 4 y 5."
        ),
        "evidencia": (
            "Archivo audiovisual final cronometrado, demostración real del "
            "chatbot y panel, explicación del póster y enlace accesible para "
            "la revisión; narración humana conforme al reparto, p. 6."
        ),
        "aporte_p2": (
            "Preparar guion y recorrido, coordinar la narración humana, "
            "grabar o recibir las tomas reales, editar, verificar duración "
            "y publicación y comprobar permisos. Un guion no es el video."
        ),
        "depende_p1": (
            "Requiere app y arquitectura estables para la demostración. "
            "La grabación con voz real y la publicación del video son pasos "
            "humanos pendientes hasta contar con evidencia verificable."
        ),
    },
]

# Títulos de los cuatro entregables de la guía oficial, p. 4, en el mismo orden.
ENTREGABLES = [
    "Notebook Técnico Reproducible (.ipynb)",
    "Póster Sintético tipo Infografía (.pdf)",
    "Aplicación Interactiva y Código Fuente (GitHub)",
    "Video de Sustentación (3 a 5 min)",
]

BANDERAS = [
    (
        "OBLIGATORIO | Continuar el pilar y corpus de ACA 1, conectando la base "
        "vectorial con un LLM y la interfaz. No presentar solo recuperación "
        "de fragmentos como un chatbot RAG generativo. Guía, pp. 1-4."
    ),
    (
        "OBLIGATORIO | Chat con historial, fuentes visibles y panel de "
        "documentos, metadatos y fragmentos. La demostración debe mostrar "
        "chat y gestión documental, no solo tablas del notebook. Guía, pp. 3-4."
    ),
    (
        "OBLIGATORIO | GitHub debe contener aplicación, auxiliares, "
        "requirements.txt y README con instrucciones de ejecución. La "
        "reproducibilidad se comprueba, no se infiere del nombre del archivo. "
        "Guía, pp. 4-5."
    ),
    (
        "OBLIGATORIO | Póster con nombres, arquitectura completa, capturas, "
        "ejemplos con citas, conclusiones, APA 7 y enlaces operativos a app, "
        "código y video. Portada, enlace a una carpeta o borrador de póster "
        "no sustituyen los cuatro entregables. Guía, pp. 4-5; reparto, p. 5."
    ),
    (
        "PROPUESTA DEL REPARTO | Los 12 casos conversacionales y 4 controles "
        "funcionales son el plan de trabajo del equipo, no un mínimo impuesto "
        "por el docente. Prepararlos antes de observar respuestas. Reparto, p. 4."
    ),
    (
        "PROPUESTA DEL REPARTO | Fidelidad, citas válidas, abstención y "
        "latencia se registran con criterios, denominadores y condiciones de "
        "medición. No se inventan umbrales oficiales de aprobación ni se "
        "convierte similitud coseno en exactitud del chatbot. Reparto, pp. 3-4."
    ),
    (
        "PROPUESTA DEL REPARTO | El recorrido de 4:30 es sugerido; el límite "
        "oficial es 3:00 a 5:00, medido sobre el video final. La voz real y "
        "el acceso sin restricciones se conservan por las recomendaciones "
        "previas recogidas en el reparto, p. 6."
    ),
    (
        "TRAZABILIDAD | El reparto original separó desarrollo y validación; "
        "ahora se integran ambos bloques. Mediciones, capturas y video "
        "requieren ejecución real, no solo código disponible. El reparto "
        "no demuestra una carga exacta 50/50 ni revisión humana independiente."
    ),
    (
        "EVIDENCIA | Diferenciar preparado, pendiente, ejecutado y revisado. "
        "Las pruebas sin ejecutar no tienen un resultado cero ni aprobado. "
        "Resultados ACA 1, demostraciones simuladas o métricas de fixtures "
        "no acreditan respuestas del nuevo LLM. Reparto, pp. 3-4 y 6."
    ),
    (
        "EVIDENCIA | Conservar la versión evaluada y las expectativas "
        "originales; no modificar respuestas esperadas para ocultar fallos. "
        "Reportar incidencias y volver a probar después de las correcciones "
        "del bloque técnico. Reparto, pp. 3-4 y 6."
    ),
    (
        "SEGURIDAD | No ejecutar automáticamente celdas heredadas que "
        "recreen o borren colecciones, ni publicar claves incrustadas. El equipo "
        "registra los bloqueos; una operación destructiva o rotación de "
        "credenciales necesita autorización específica del responsable. "
        "Guía, p. 5; reparto, pp. 2, 4 y 6."
    ),
    (
        "SEGURIDAD | No incluir secretos en código, historial del repositorio, "
        "salidas, capturas o video. Si una clave se expuso, el responsable "
        "debe revocarla y sustituirla por un medio seguro; no reproducir su "
        "valor en el informe. Guía, p. 5; reparto, p. 6."
    ),
    (
        "OPCIONAL | Se admite Python nativo: LangChain/LlamaIndex no son "
        "obligatorios. La guía no exige varios LLM, entrenamiento, agentes "
        "múltiples, CRUD documental completo ni un ZIP. Un ZIP de respaldo "
        "no reemplaza GitHub. Guía, pp. 2-5; reparto, p. 5."
    ),
    (
        "PRESENTACIÓN | Las políticas de un corpus académico simulado se "
        "identifican como tales, sin atribuirlas a una empresa real. Las "
        "capturas y arquitectura deben describir lo implementado; no afirmar "
        "cuotas, disponibilidad, costo o despliegue sin evidencia vigente."
    ),
    (
        "CIERRE | Los seis pesos son 20, 20, 20, 15, 15 y 10; suman 100 y "
        "califican el proyecto, no personas ni horas. Código integrado "
        "no equivale a entrega final: verificar notebook ejecutado, app, "
        "póster, GitHub y video reales. Guía, pp. 4-5; reparto, pp. 5-6."
    ),
]
