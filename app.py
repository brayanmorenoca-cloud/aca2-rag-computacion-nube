"""Interfaz real del ACA 2: chat RAG, documentos e inspección de Qdrant.

Ejecutar: python -m streamlit run app.py

El servicio y el historial se conservan únicamente en la sesión del navegador.
No se ejecutan consultas cloud al importar este módulo ni se incluye un modo
ficticio. Las consultas al LLM y Qdrant las implementa rag_backend.py.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CATEGORIES = ("Todas", "Furniture", "Office Supplies", "Technology")
SHIPPING_MODES = ("Todos", "First Class", "Same Day", "Second Class", "Standard Class")
METADATA_FIELDS = (
    "category", "ship_mode", "segment", "region", "sub_categories",
    "source_type", "corpus_version", "seccion", "section_id", "fuente",
    "source", "title", "titulo", "chunk_id", "embedding_model", "doc_source",
    "page_section", "content_sha256", "chunk_in_section",
)
QDRANT_SECRETS_BY_DESTINATION = {
    "heredado": ("QDRANT_URL", "QDRANT_API_KEY"),
    "propio": ("QDRANT_PROPIO_URL", "QDRANT_PROPIO_API_KEY"),
}


def texto_seguro_markdown(text: Any) -> str:
    """Mantener el texto y las citas, pero no cargar imágenes ni enlaces del LLM.

    La respuesta no es HTML confiable. Se desactivan los enlaces/imágenes Markdown
    y etiquetas HTML; las referencias [F1] del corpus permanecen visibles.
    """
    value = str(text)
    value = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"!\[([^\]]*)\]\[[^\]]*\]", r"\1", value)
    value = re.sub(r"(?m)^\s*\[[^\]]+\]:\s*\S+.*$", "", value)
    value = re.sub(r"</?[A-Za-z][^>]*>", "", value)
    return value


def metadatos_publicos(metadata: Any) -> dict[str, Any]:
    """Lista permitida: nunca enviar un payload completo o claves a la vista."""
    if not isinstance(metadata, dict):
        return {}
    result: dict[str, Any] = {}
    for key in METADATA_FIELDS:
        value = metadata.get(key)
        if isinstance(value, (str, int, float, bool)) or value is None:
            if key in metadata:
                result[key] = value
        elif isinstance(value, (list, tuple)):
            result[key] = [x for x in value if isinstance(x, (str, int, float, bool))][:100]
    return result


def historial_llm(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Extraer diálogo, no resultados técnicos ni estado interno de Streamlit."""
    return [
        {"role": message["role"], "content": str(message["content"])}
        for message in messages
        if message.get("role") in ("user", "assistant") and message.get("content")
    ]


def numero_finito(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def resultado_publico(result: dict[str, Any], *, permitir_prueba: bool = False) -> dict[str, Any]:
    """Normalizar únicamente la respuesta pública prevista en el contrato RAG.

    No convierte simulaciones en inferencias reales ni acepta respuestas vacías.
    Los tests de UI pueden usar fixtures pero nunca se presentan como evidencias
    de Gemini en esta aplicación.
    """
    mode = result.get("modo")
    if mode != "llm_rag_real" and not (permitir_prueba and mode == "prueba_unitaria_simulada"):
        raise ValueError("La interfaz requiere una respuesta del servicio RAG real.")
    if not isinstance(result.get("respuesta"), str) or not result["respuesta"].strip():
        raise ValueError("El servicio no devolvió una respuesta utilizable.")
    if not isinstance(result.get("modelo"), str) or not result["modelo"].strip():
        raise ValueError("El servicio no identificó el modelo utilizado.")
    sources = []
    for source in result.get("fuentes", []):
        if isinstance(source, dict):
            sources.append({
                key: str(source.get(key, ""))
                for key in ("etiqueta", "fuente", "seccion")
            })
    chunks = []
    for chunk in result.get("fragmentos", []):
        if not isinstance(chunk, dict):
            continue
        item = {
            key: str(chunk.get(key, ""))
            for key in ("etiqueta", "fuente", "seccion", "texto", "id")
        }
        item["score"] = numero_finito(chunk.get("score"))
        item["metadatos"] = metadatos_publicos(chunk.get("metadatos", {}))
        chunks.append(item)
    timings = {}
    for key, value in result.get("tiempos_s", {}).items():
        number = numero_finito(value)
        if key in ("preparacion_y_recuperacion", "embedding", "qdrant", "busqueda_vectorial", "llm", "total", "total_s") and number is not None and number >= 0:
            timings[str(key)] = number
    return {
        "modo": mode, "modelo": result["modelo"],
        "modelo_version_reportada": result.get("modelo_version_reportada") if isinstance(result.get("modelo_version_reportada"), str) else None,
        "modelo_identificacion": str(result.get("modelo_identificacion", "Identificador comunicado por el servicio")),
        "respuesta": result["respuesta"], "fuentes": sources,
        "fragmentos": chunks, "tiempos_s": timings,
        "estado_respuesta": str(result.get("estado_respuesta", "sin_clasificar")),
        "advertencias": [str(x) for x in result.get("advertencias", [])],
    }


def exportar_conversacion(messages: list[dict[str, Any]], *, permitir_prueba: bool = False) -> str:
    """Exportación deliberadamente sin configuración, servicios ni secretos."""
    public_messages = []
    for message in messages:
        if message.get("role") not in ("user", "assistant"):
            continue
        row: dict[str, Any] = {
            "role": message["role"], "content": str(message.get("content", "")),
        }
        if message.get("role") == "assistant" and isinstance(message.get("resultado"), dict):
            row["resultado"] = resultado_publico(message["resultado"], permitir_prueba=permitir_prueba)
        public_messages.append(row)
    return json.dumps({
        "proyecto": "ACA 2 - RAG Ventas", "corpus": "académico simulado",
        "exportado_utc": datetime.now(timezone.utc).isoformat(),
        "nota": "Transcripción de esta sesión; no equivale por sí sola a una evaluación de fidelidad.",
        "mensajes": public_messages,
    }, ensure_ascii=False, indent=2, allow_nan=False)


def exportar_diagnostico(public_config: dict[str, Any], index_state: dict[str, Any] | None,
                        completed_turns: int = 0, checked_at: str | None = None) -> str:
    """Diagnóstico portable sin claves, URL del clúster, preguntas ni respuestas."""
    config_fields = (
        "coleccion", "modelo_llm", "proveedor_llm", "llm_backend", "modelo_embeddings",
        "dimension", "temperatura", "max_output_tokens", "parametros_gestionados_por_proveedor",
        "version_app", "version_prompt", "solo_lectura_qdrant", "destino_qdrant",
    )
    index_fields = ("coleccion", "estado", "puntos", "indexados", "dimension", "distancia",
                    "compatible", "solo_lectura", "version_corpus", "version_corpus_muestra")
    scalar = lambda value: isinstance(value, (str, int, float, bool)) or value is None
    config = {key: public_config[key] for key in config_fields if key in public_config and scalar(public_config[key])}
    index = {key: index_state[key] for key in index_fields if key in index_state and scalar(index_state[key])} if isinstance(index_state, dict) else None
    return json.dumps({
        "tipo": "diagnostico_interfaz_sin_secretos",
        "generado_utc": datetime.now(timezone.utc).isoformat(),
        "configuracion_publica": config, "estado_indice_observado": index,
        "fecha_consulta_indice": checked_at, "turnos_completados_sesion": int(completed_turns),
        "nota": "La configuración no demuestra conectividad ni calidad. El estado del índice solo existe si se consultó y no es un monitor continuo.",
    }, ensure_ascii=False, indent=2, allow_nan=False)


def claves_qdrant_requeridas(public_config: dict[str, Any]) -> tuple[str, str]:
    """Seleccionar una sola familia de accesos; nunca completar desde la otra."""
    destination = public_config.get("destino_qdrant", "heredado")
    if not isinstance(destination, str) or destination not in QDRANT_SECRETS_BY_DESTINATION:
        raise ValueError("El destino de Qdrant debe ser propio o heredado.")
    return QDRANT_SECRETS_BY_DESTINATION[destination]


def accesos_configurados(public_config: dict[str, Any]) -> dict[str, bool]:
    raw = public_config.get("claves_configuradas", {})
    if not isinstance(raw, dict):
        raw = {}
    names = claves_qdrant_requeridas(public_config) + ("GEMINI_API_KEY",)
    # public_dict entrega booleanos, no valores de claves ni cadenas truthy.
    return {key: raw.get(key, raw.get(key.lower(), False)) is True for key in names}


def secretos_pendientes(public_config: dict[str, Any]) -> list[str]:
    configured = accesos_configurados(public_config)
    required = list(claves_qdrant_requeridas(public_config))
    if public_config.get("requiere_gemini_key", True):
        required.append("GEMINI_API_KEY")
    return [key for key in required if not configured[key]]


def inicializar_secretos_streamlit(st):
    """Activar la lectura nativa de secretos raíz sin copiar ni mostrar valores.

    Streamlit promueve sus valores escalares raíz al entorno durante el parseo.
    Config.from_env selecciona después exclusivamente la familia del destino.
    """
    try:
        st.secrets.get("GEMINI_MODEL", None)
    except (FileNotFoundError, KeyError):
        pass


def _init_session(st, config, service_type):
    # Comparación privada completa: una rotación de clave invalida el servicio.
    # Nunca se imprime config ni se utiliza caché global de clientes o historiales.
    if st.session_state.get("_aca2_config") != config:
        st.session_state["_aca2_config"] = config
        st.session_state["_aca2_service"] = service_type(config)
        st.session_state["_aca2_messages"] = []
        st.session_state["_aca2_index"] = None
        st.session_state["_aca2_index_checked_at"] = None
        st.session_state["_aca2_docs"] = None
        st.session_state["_aca2_docs_page"] = 0
        st.session_state["_aca2_docs_filters"] = None
        st.session_state["_aca2_last_error"] = None
    return st.session_state["_aca2_service"]


def _reset_chat(st):
    st.session_state["_aca2_messages"] = []
    st.session_state["_aca2_last_error"] = None


def _controlled_error(st, error, rag_error_type, operation: str):
    # RagError garantiza mensajes seguros. Nunca mostrar traceback, repr,
    # response.text, URL de petición ni str de excepciones de terceros.
    message = str(error) if isinstance(error, rag_error_type) else (
        "No se pudo completar la operación. Revisa la configuración del servicio "
        "y vuelve a intentarlo. No se mostraron detalles internos ni credenciales."
    )
    st.error(f"{operation}: {message}")
    st.session_state["_aca2_last_error"] = message


def _render_fragment(st, chunk: dict[str, Any], index: int):
    label = str(chunk.get("etiqueta") or f"Fragmento {index}")
    source = str(chunk.get("fuente", "Fuente no indicada"))
    section = str(chunk.get("seccion", ""))
    with st.expander(f"{label} | {section} | {source}", expanded=False):
        score = numero_finito(chunk.get("score"))
        if score is not None:
            st.caption(f"Similitud: {score:.4f}. No es una probabilidad de acierto.")
        st.text(str(chunk.get("texto", "")))
        metadata = metadatos_publicos(chunk.get("metadatos", {}))
        if metadata:
            st.caption("Metadatos del fragmento")
            st.json(metadata, expanded=False)


def _render_result(st, result: dict[str, Any]):
    st.markdown(texto_seguro_markdown(result["respuesta"]), unsafe_allow_html=False)
    sources = result.get("fuentes", [])
    if sources:
        st.caption("Fuentes citadas por el modelo")
        for source in sources:
            st.text(
                f"{source.get('etiqueta', '')} · {source.get('fuente', '')} "
                f"· sección {source.get('seccion', '')}"
            )
    else:
        st.caption("Sin citas emitidas: verifica si la respuesta se abstiene o pide aclaración.")
    timings = result.get("tiempos_s", {})
    total = numero_finito(timings.get("total", timings.get("total_s")))
    elapsed = f" · {total:.2f} s de pipeline" if total is not None else ""
    st.caption(f"Modelo solicitado: {result['modelo']}{elapsed} · Estado: {result.get('estado_respuesta', '')}")
    if result.get("modelo_version_reportada"):
        st.caption(f"Versión reportada por la API: {result['modelo_version_reportada']}")
    elif result.get("modelo_identificacion"):
        st.caption(result["modelo_identificacion"])
    for warning in result.get("advertencias", []):
        st.warning(warning)
    chunks = result.get("fragmentos", [])
    if chunks:
        st.caption(f"Contexto enviado al LLM: {len(chunks)} fragmentos. Puedes inspeccionarlos.")
        for i, chunk in enumerate(chunks, 1):
            _render_fragment(st, chunk, i)


def main():
    import streamlit as st
    from rag_backend import Config, RagError, RagService

    st.set_page_config(
        page_title="RAG Ventas | ACA 2 CUN", page_icon="📘", layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown("""<style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; max-width: 1280px; }
    h1 { letter-spacing: -0.035em; }
    [data-testid="stMetric"] { border: 1px solid #dbe3e9; border-radius: 12px; padding: 12px 16px; }
    [data-testid="stChatMessage"] { border-radius: 12px; }
    </style>""", unsafe_allow_html=True)

    with st.sidebar:
        logo = Path(__file__).with_name("logo_cun.png")
        if logo.is_file():
            st.image(str(logo), width=170)
        st.caption("COMPUTACIÓN EN LA NUBE · ACA 2")
        st.subheader("RAG Ventas")
        st.caption("Qdrant cloud + LLM + Streamlit")

    inicializar_secretos_streamlit(st)

    try:
        config = Config.from_env()
        public_config = config.public_dict()
        access = accesos_configurados(public_config)
        qdrant_ready = all(access[key] for key in claves_qdrant_requeridas(public_config))
        missing_secrets = secretos_pendientes(public_config)
        chat_ready = not missing_secrets
        service = _init_session(st, config, RagService)
    except RagError as error:
        st.title("Asistente documental de ventas")
        st.error(str(error))
        st.info("Corrige la configuración en las variables de entorno o secretos y vuelve a cargar la aplicación.")
        return
    except Exception:
        st.title("Asistente documental de ventas")
        st.error("No se pudo cargar la configuración. Consulta las instrucciones del README; no se muestran detalles internos.")
        return

    with st.sidebar:
        st.divider()
        st.caption("RECUPERACIÓN")
        top_k = st.slider("Fragmentos Top-k", min_value=1, max_value=10, value=3, key="aca2_top_k")
        category = st.selectbox("Categoría", CATEGORIES, key="aca2_category")
        shipping = st.selectbox("Modo de envío", SHIPPING_MODES, key="aca2_shipping")
        st.caption("Los filtros conservan los documentos generales aplicables a todas las categorías o envíos.")
        st.divider()
        st.caption("CONFIGURACIÓN PÚBLICA")
        st.text(f"LLM: {public_config.get('modelo_llm', 'Sin indicar')}")
        st.text(f"Destino Qdrant: {public_config.get('destino_qdrant', 'heredado')}")
        st.text(f"Colección: {public_config.get('coleccion', 'Sin indicar')}")
        if public_config.get("parametros_gestionados_por_proveedor"):
            st.caption("Colab AI administra la generación. Su SDK no expone temperatura, límite de salida ni uso de tokens; no se presentan valores como si estuvieran configurados.")
        else:
            st.caption(f"Temperatura: {public_config.get('temperatura', '—')} · Límite de salida: {public_config.get('max_output_tokens', '—')} tokens")
        if chat_ready:
            st.success("Configuración disponible")
            st.caption("Esto no confirma conectividad ni cuota; se verifican al consultar.")
        else:
            st.warning("Preparación pendiente")
            st.caption("Faltan: " + ", ".join(missing_secrets))
        st.button("Reiniciar conversación", key="aca2_reset", on_click=_reset_chat, args=(st,), width="stretch")
        st.caption("El historial es temporal y exclusivo de esta sesión. No cambia los documentos ni el índice.")

    st.caption("CUN / PILAR VENTAS / CORPUS ACADÉMICO SIMULADO")
    st.title("Asistente documental de ventas")
    st.write("Consulta políticas de postventa, logística y soporte; contrasta cada respuesta con la evidencia recuperada.")
    st.info("Demostración académica: los plazos y las políticas del corpus son simulados. No representan políticas comerciales reales ni permiten consultar pedidos en vivo.")

    if not chat_ready:
        st.warning("El chatbot permanece desactivado hasta configurar los accesos. No se muestran respuestas simuladas ni se sustituyen las llamadas al LLM por respuestas memorizadas.")

    index_state = st.session_state.get("_aca2_index")
    messages = st.session_state["_aca2_messages"]
    col1, col2, col3 = st.columns(3)
    col1.metric("Turnos completados", sum(m.get("role") == "assistant" for m in messages))
    col2.metric("Puntos en Qdrant", index_state.get("puntos", "—") if index_state else "—")
    col3.metric("Recuperación configurada", f"Top-{top_k}")

    chat_tab, docs_tab, index_tab = st.tabs(["Chat con fuentes", "Documentos y fragmentos", "Supervisión del índice"])

    with chat_tab:
        st.subheader("Conversación fundamentada")
        if not messages:
            st.caption("Ejemplos para escribir en el chat:")
            st.markdown("- ¿Qué evidencia se solicita si una silla llegó dañada?\n- ¿Cuándo empieza el plazo de Standard Class y qué diferencia hay entre Order Date y Ship Date?\n- Mi teléfono no carga: ¿qué verificaciones puedo hacer y cómo tramito la garantía?")
        for message in messages:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    _render_result(st, message["resultado"])
                else:
                    st.text(message["content"])

        prompt = st.chat_input("Pregunta sobre el corpus de ventas…", disabled=not chat_ready, max_chars=2000, key="aca2_question")
        if prompt is not None:
            question = prompt.strip()
            if not question:
                st.warning("Escribe una pregunta antes de enviarla.")
            else:
                with st.chat_message("user"):
                    st.text(question)
                try:
                    with st.spinner("Recuperando evidencia de Qdrant y consultando el LLM…"):
                        raw_result = service.responder(
                            question, historial=historial_llm(messages), top_k=top_k,
                            categoria=category, envio=shipping,
                        )
                        result = resultado_publico(raw_result)
                    messages.extend([
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": result["respuesta"], "resultado": result},
                    ])
                    st.session_state["_aca2_last_error"] = None
                    st.rerun()
                except RagError as error:
                    _controlled_error(st, error, RagError, "Consulta no completada")
                except Exception as error:
                    _controlled_error(st, error, RagError, "Consulta no completada")
        if messages:
            st.download_button(
                "Descargar esta conversación y sus fuentes", exportar_conversacion(messages),
                file_name="conversacion_rag_aca2.json", mime="application/json",
                key="aca2_download_chat", width="content",
            )

    with docs_tab:
        st.subheader("Documentos almacenados en la base vectorial")
        st.caption("Esta vista consulta el contenido real de Qdrant en modo lectura. No carga, borra ni reindexa documentos.")
        doc_filter = (category, shipping)
        if st.session_state.get("_aca2_docs_filters") != doc_filter:
            st.session_state["_aca2_docs"] = None
            st.session_state["_aca2_docs_page"] = 0
            st.session_state["_aca2_docs_filters"] = doc_filter

        a, b = st.columns([1, 3])
        with a:
            first_page = st.button("Consultar documentos", key="aca2_docs_refresh", disabled=not qdrant_ready, width="stretch")
        with b:
            st.caption(f"Filtros activos: categoría {category} · envío {shipping}. Hasta 100 fragmentos por página.")
        page = st.session_state.get("_aca2_docs")
        next_page = st.button(
            "Cargar página siguiente", key="aca2_docs_next",
            disabled=not qdrant_ready or not page or page.get("next_page_offset") is None,
        )
        if first_page or next_page:
            try:
                offset = page.get("next_page_offset") if next_page and page else None
                with st.spinner("Leyendo documentos y metadatos de Qdrant…"):
                    fetched = service.explorar_documentos(
                        limit=100, offset=offset, categoria=category, envio=shipping,
                    )
                st.session_state["_aca2_docs"] = page = fetched
                st.session_state["_aca2_docs_page"] = (st.session_state["_aca2_docs_page"] + 1) if next_page else 1
            except Exception as error:
                _controlled_error(st, error, RagError, "No se pudieron consultar los documentos")

        if page:
            documents = page.get("documentos", [])
            chunks = page.get("fragmentos", [])
            st.caption(f"Página {st.session_state['_aca2_docs_page']} · {len(documents)} documentos presentes · {len(chunks)} fragmentos mostrados")
            if page.get("parcial"):
                st.warning("Esta página no representa todo el índice. Usa «Cargar página siguiente» para continuar.")
            if documents:
                st.dataframe([
                    {"Documento": str(doc.get("fuente", "")),
                     "Secciones en esta página": ", ".join(str(x) for x in doc.get("secciones", [])),
                     "Fragmentos en esta página": doc.get("fragmentos_en_pagina", 0)}
                    for doc in documents
                ], width="stretch", hide_index=True)
            if chunks:
                sources = ["Todos los documentos"] + sorted({str(chunk.get("fuente", "")) for chunk in chunks})
                selected = st.selectbox("Explorar un documento de esta página", sources, key="aca2_doc_selected")
                for i, chunk in enumerate(chunks, 1):
                    if selected == "Todos los documentos" or str(chunk.get("fuente", "")) == selected:
                        _render_fragment(st, chunk, i)
            else:
                st.info("No hay fragmentos para los filtros seleccionados.")
        else:
            st.info("Pulsa «Consultar documentos» para leer el índice. Todavía no se ha consultado esta vista.")

    with index_tab:
        st.subheader("Supervisión de la colección")
        st.caption("Verifica estado, número de puntos y compatibilidad vectorial. La consulta es de solo lectura y no consume una generación del LLM.")
        if st.button("Verificar índice ahora", key="aca2_index_refresh", disabled=not qdrant_ready):
            try:
                with st.spinner("Verificando la colección existente…"):
                    index_state = service.estado_indice()
                st.session_state["_aca2_index"] = index_state
                st.session_state["_aca2_index_checked_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception as error:
                _controlled_error(st, error, RagError, "Verificación no completada")
        if index_state:
            st.caption(f"Última consulta de estado: {st.session_state.get('_aca2_index_checked_at', 'Sin registrar')}. Es una instantánea, no un monitor continuo.")
            if index_state.get("compatible"):
                st.success("Colección consultada y compatible con la configuración del recuperador.")
            else:
                st.error("La colección no es compatible con la configuración. No se debe mezclar otro modelo de embeddings.")
            st.table([
                {"Indicador": "Colección", "Valor": str(index_state.get("coleccion", ""))},
                {"Indicador": "Estado comunicado por Qdrant", "Valor": str(index_state.get("estado", ""))},
                {"Indicador": "Puntos almacenados", "Valor": str(index_state.get("puntos", ""))},
                {"Indicador": "Vectores indexados", "Valor": str(index_state.get("indexados", ""))},
                {"Indicador": "Dimensión", "Valor": str(index_state.get("dimension", ""))},
                {"Indicador": "Métrica", "Valor": str(index_state.get("distancia", ""))},
                {"Indicador": "Versión del corpus en muestra", "Valor": str(index_state.get("version_corpus") or "No informada")},
                {"Indicador": "Modo de acceso de la aplicación", "Valor": "Solo lectura"},
            ])
            if index_state.get("metadatos_indexados"):
                st.caption("Campos de metadatos indexados")
                st.json(index_state["metadatos_indexados"], expanded=False)
            st.caption("Un número de vectores indexados distinto al total puede reflejar la estrategia de indexación de Qdrant; no implica por sí solo pérdida de documentos.")
            st.caption("La versión del corpus procede de una muestra del índice, no de una auditoría exhaustiva de todos los fragmentos.")
        else:
            st.info("Conexión todavía no verificada en esta sesión. La existencia de una clave no demuestra que el servicio esté disponible.")
        st.divider()
        st.caption("CONFIGURACIÓN DEL RECUPERADOR Y GENERADOR")
        st.table([
            {"Componente": "Embeddings", "Configuración": str(public_config.get("modelo_embeddings", ""))},
            {"Componente": "Dimensión esperada", "Configuración": str(public_config.get("dimension", ""))},
            {"Componente": "LLM seleccionado", "Configuración": str(public_config.get("modelo_llm", ""))},
            {"Componente": "Versión de aplicación", "Configuración": str(public_config.get("version_app", ""))},
            {"Componente": "Versión de prompt", "Configuración": str(public_config.get("version_prompt", ""))},
        ])
        st.download_button(
            "Descargar diagnóstico sin secretos",
            exportar_diagnostico(public_config, index_state,
                sum(m.get("role") == "assistant" for m in messages),
                st.session_state.get("_aca2_index_checked_at")),
            file_name="diagnostico_rag_aca2.json", mime="application/json",
            key="aca2_download_diagnostic",
        )

    st.divider()
    st.caption("ACA 2 · Consulta semántica + generación fundamentada · Credenciales fuera del código · Sin operaciones destructivas sobre Qdrant")


if __name__ == "__main__":
    main()
