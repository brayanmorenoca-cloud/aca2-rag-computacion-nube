"""Evaluación ACA 2. Sin red, credenciales ni inferencia al importar.

Las pruebas unitarias NO son resultados del chatbot. Solo se computan métricas
de registros etiquetados como ejecución real y revisados explícitamente.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import math
import re
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

SCHEMA_VERSION = "2.0.0-p2"
MODO_REAL = "llm_rag_real"


def guardar_json(ruta, datos):
    p = Path(ruta)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(p)
    return p


def cargar_json(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def ahora():
    return datetime.now(timezone.utc).isoformat()


def catalogar_corpus(corpus):
    filas = []
    for doc in corpus["DOCS"]:
        for sec in doc["sections"]:
            filas.append({"fuente": doc["filename"], "titulo_documento": doc["title"],
                          "seccion": sec["id"], "titulo_seccion": sec["title"],
                          "texto": sec["text"], "metadatos": sec["metadata"],
                          "sha256_texto": hashlib.sha256(sec["text"].encode()).hexdigest()})
    return filas


def validar_banco(casos, funcionales, corpus):
    catalogo = catalogar_corpus(corpus)
    secciones = {r["seccion"]: r["fuente"] for r in catalogo}
    fuentes = {r["fuente"] for r in catalogo}
    assert len({c["id"] for c in casos + funcionales}) == len(casos) + len(funcionales), "IDs duplicados"
    for c in casos:
        assert c["turnos"] and all(isinstance(q, str) and q.strip() for q in c["turnos"])
        assert c["respuesta_esperada"] and c["criterios"]
        assert set(c["secciones_esperadas"]) <= secciones.keys(), c["id"]
        assert set(c["fuentes_esperadas"]) <= fuentes, c["id"]
        for sid in c["secciones_esperadas"]:
            assert secciones[sid] in c["fuentes_esperadas"], (c["id"], sid)
    return {"casos_conversacionales": len(casos), "turnos_previstos": sum(len(c["turnos"]) for c in casos),
            "pruebas_funcionales": len(funcionales), "documentos_locales": len(fuentes),
            "secciones_documentales": len(catalogo), "integridad_banco": "verificada_localmente",
            "nota": "Secciones no equivalen a fragmentos/chunks. No se verificó el índice cloud ni el LLM."}


def registro_vacio(casos, funcionales, version_app=None):
    banco_sha = hashlib.sha256(json.dumps(casos, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"schema_version": SCHEMA_VERSION, "creado_utc": ahora(), "version_app": version_app,
            "proposito": "evaluacion_academica_real", "banco_sha256": banco_sha, "config_ejecucion": None,
            "casos": [{"id": c["id"], "estado": "no_ejecutado", "origen": None,
                       "ejecucion_real": False, "version_app": version_app,
                       "turnos": [], "latencia_total_s": None, "revision": None,
                       "incidencia": "Pendiente de ejecución end-to-end del proyecto integrado; no es un resultado del modelo."} for c in casos],
            "funcionales": [{"id": c["id"], "estado": "no_ejecutado", "cumple": None,
                            "evidencia": None, "revisor": None, "observaciones": None} for c in funcionales]}


def inicializar_registro(ruta, casos, funcionales, version_app=None):
    if Path(ruta).exists():
        r = cargar_json(ruta)
        assert r["schema_version"] == SCHEMA_VERSION, "Versión de registro incompatible: conservar y migrar explícitamente."
        esperado = registro_vacio(casos, funcionales)
        assert r.get("banco_sha256") == esperado["banco_sha256"], "El banco cambió: crear una corrida nueva."
        assert {x["id"] for x in r["funcionales"]} == {x["id"] for x in funcionales}, "Controles distintos."
        return r
    r = registro_vacio(casos, funcionales, version_app)
    guardar_json(ruta, r)
    return r


def _fila(registro, caso_id, grupo="casos"):
    found = [r for r in registro[grupo] if r["id"] == caso_id]
    if len(found) != 1:
        raise ValueError("ID no encontrado o duplicado: " + caso_id)
    return found[0]


def _secreto(texto):
    patterns = [r"\bsk-[A-Za-z0-9_-]{20,}", r"\bAIza[A-Za-z0-9_-]{25,}",
                r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                r"(?i)\b(?:QDRANT(?:_PROPIO)?_API_KEY|OPENAI_API_KEY|GEMINI_API_KEY|ANTHROPIC_API_KEY|NGROK_AUTHTOKEN)[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9_-]{16,}"]
    return any(re.search(p, texto) for p in patterns)


def _sin_secretos(obj):
    if isinstance(obj, str) and _secreto(obj):
        raise ValueError("Posible secreto detectado: no se guardó ni se imprimió su valor.")
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and _secreto(str(key) + "=" + value):
                raise ValueError("Posible secreto detectado en campo estructurado.")
            _sin_secretos(value)
    elif isinstance(obj, list):
        for value in obj:
            _sin_secretos(value)


def _config_congelada(config):
    for key in ("version_app", "modelo_llm", "version_prompt", "corpus_sha256"):
        if not config.get(key):
            raise ValueError("Registrar antes de ejecutar: " + key)
    keys = ("version_app", "modelo_llm", "proveedor_llm", "version_prompt", "corpus_sha256",
            "temperatura", "max_output_tokens", "top_k", "usar_top_k_por_caso",
            "destino_qdrant", "coleccion_activa", "corpus_version_remota_verificada",
            "reconstruccion_manifest_sha256", "modelo_embeddings_aca1", "modelo_embeddings_revision",
            "dimension_embeddings", "distancia")
    return {k: config.get(k) for k in keys}


def _congelar(registro, config, metodo):
    frozen = _config_congelada(config)
    frozen["metodo_medicion"] = metodo
    if registro.get("config_ejecucion") not in (None, frozen):
        raise ValueError("App, modelo, prompt, corpus o parámetros cambiaron. Crear otra corrida; no mezclar versiones.")
    registro["config_ejecucion"] = frozen
    registro["version_app"] = config["version_app"]


def validar_coherencia_exportacion(registro, config):
    """Impide presentar una corrida anterior como evidencia de otra configuración.

    Es una comprobación de lectura: no actualiza ni migra registros. Las claves
    opcionales ausentes en una configuración histórica se comparan como None;
    cualquier valor nuevo exige una corrida compatible, no una reetiquetación.
    Un borrador sin ejecuciones puede no tener todavía configuración congelada.
    """
    def tiene_actividad(fila):
        return (fila.get("estado", "no_ejecutado") != "no_ejecutado"
                or fila.get("ejecucion_real") is True or bool(fila.get("turnos")))

    congelada = registro.get("config_ejecucion")
    filas = registro.get("casos", [])
    if congelada is None:
        if any(tiene_actividad(fila) for fila in filas + registro.get("funcionales", [])):
            raise ValueError("Hay observaciones o ejecuciones sin configuración congelada. Conservar el registro y revisar su procedencia antes de exportar.")
        return True
    if not isinstance(congelada, dict):
        raise ValueError("La configuración congelada del registro no tiene un formato válido; no se exportó ni modificó la evidencia.")
    vigente = _config_congelada(config)
    if any(congelada.get(key) != value for key, value in vigente.items()):
        raise ValueError("La configuración vigente difiere de la corrida registrada. Conservar los resultados y crear otra corrida; no mezclar modelo, índice, corpus o parámetros en la exportación.")
    if any(tiene_actividad(fila) and fila.get("config_ejecucion") != congelada for fila in filas):
        raise ValueError("Hay ensayos con una configuración distinta de la corrida. No se exportó ni modificó la evidencia; separar los registros.")
    return True


def validar_respuesta(respuesta, catalogo):
    """Valida estructura, no veracidad semántica; esta última requiere revisión."""
    if not isinstance(respuesta, dict):
        raise ValueError("Se requiere respuesta generativa dict; una lista Top-k no es un chatbot LLM.")
    if respuesta.get("modo") != MODO_REAL:
        raise ValueError("El adaptador debe declarar modo='llm_rag_real' y llamar al LLM real.")
    for key in ("respuesta", "modelo"):
        if not isinstance(respuesta.get(key), str) or not respuesta[key].strip():
            raise ValueError("Falta campo obligatorio: " + key)
    if not isinstance(respuesta.get("fuentes"), list) or not isinstance(respuesta.get("fragmentos"), list):
        raise ValueError("fuentes y fragmentos deben ser listas, incluso cuando estén vacías.")
    pares = {(r["fuente"], r["seccion"]) for r in catalogo}
    avisos = []
    fuentes = []
    for f in respuesta["fuentes"]:
        if not isinstance(f, dict) or not all(isinstance(f.get(k), str) for k in ("fuente", "seccion")):
            raise ValueError("Cada fuente debe contener fuente y seccion como texto.")
        fuentes.append({"fuente": f["fuente"], "seccion": f["seccion"]})
        if (f["fuente"], f["seccion"]) not in pares:
            avisos.append("Referencia no encontrada en el corpus: " + f["seccion"])
    fragmentos = []
    for f in respuesta["fragmentos"]:
        if not isinstance(f, dict) or not all(isinstance(f.get(k), str) for k in ("fuente", "seccion", "texto")):
            raise ValueError("Cada fragmento requiere fuente, seccion y texto.")
        fragmentos.append({k: f[k] for k in ("fuente", "seccion", "texto")})
        if (f["fuente"], f["seccion"]) not in pares:
            avisos.append("Fragmento con documento/sección desconocido: " + f["seccion"])
    limpio = {"respuesta": respuesta["respuesta"], "modelo": respuesta["modelo"],
              "modo": MODO_REAL, "fuentes": fuentes, "fragmentos": fragmentos,
              "avisos_estructura": avisos}
    _sin_secretos(limpio)
    return limpio


def ejecutar_bateria(responder: Callable, casos, registro, catalogo, config, *, confirmar_real=False, ids=None):
    """Llama al adaptador explícito del backend real del proyecto integrado.

    responder(pregunta=str, historial=list[dict], top_k=int) -> dict
    Debe usar timeout en el proveedor y devolver la respuesta final, no streaming.
    Esta función NO instala, inicia, modifica ni descubre aplicaciones o modelos.
    """
    if not confirmar_real:
        raise ValueError("La ejecución real requiere confirmación explícita y puede consumir cuota del proveedor.")
    if not callable(responder):
        raise TypeError("responder debe ser una función del sistema real.")
    _config_congelada(config)
    selected = set(ids or [c["id"] for c in casos])
    if selected - {c["id"] for c in casos}:
        raise ValueError("Hay IDs desconocidos.")
    result = copy.deepcopy(registro)
    _congelar(result, config, "adaptador_pipeline_sin_render_ui")
    for selected_id in selected:
        if _fila(result, selected_id)["estado"] != "no_ejecutado":
            raise ValueError("No se sobrescriben ensayos anteriores. Crear otra corrida: " + selected_id)
    for caso in casos:
        if caso["id"] not in selected:
            continue
        fila = _fila(result, caso["id"])
        if fila["estado"] != "no_ejecutado":
            raise ValueError("No se sobrescriben ensayos anteriores. Crear una nueva corrida: " + caso["id"])
        fila.update(origen="adaptador_p1", ejecucion_real=True, version_app=config["version_app"],
                    version_prompt=config["version_prompt"], fecha_utc=ahora(), run_id=str(uuid.uuid4()),
                    top_k=caso.get("top_k", 3) if config.get("usar_top_k_por_caso", True) else config.get("top_k", 3),
                    config_ejecucion=copy.deepcopy(result["config_ejecucion"]),
                    estado="en_ejecucion", revision=None, incidencia=None)
        historial = []  # nunca compartir conversaciones entre casos
        duraciones = []
        for pregunta in caso["turnos"]:
            inicio = time.perf_counter()
            try:
                raw = responder(pregunta=pregunta, historial=copy.deepcopy(historial), top_k=fila["top_k"])
                elapsed = time.perf_counter() - inicio
                resp = validar_respuesta(raw, catalogo)
                if resp["modelo"] != config["modelo_llm"]:
                    raise ValueError("Modelo diferente del configurado: excluir el intento de esta corrida.")
                fila["turnos"].append({"pregunta": pregunta, **resp, "latencia_s": round(elapsed, 6)})
                duraciones.append(elapsed)
                historial.extend([{"role": "user", "content": pregunta}, {"role": "assistant", "content": resp["respuesta"]}])
            except Exception as error:
                fila["estado"] = "error"
                fila["incidencia"] = ("Fallo " + type(error).__name__ +
                    ". Revisar el adaptador de forma privada; se omitió el mensaje para no divulgar claves o cabeceras.")
                fila["tiempo_hasta_error_s"] = round(time.perf_counter() - inicio, 6)
                break
        else:
            fila["estado"] = "ejecutado_sin_revision"
            fila["latencia_total_s"] = round(sum(duraciones), 6)
    return result


def registrar_manual(registro, casos, catalogo, caso_id, turnos, config, evidencia, *, confirmar_real=False):
    """Importación explícita de respuestas observadas en la UI real, no ejemplos."""
    if not confirmar_real or not evidencia:
        raise ValueError("Confirmar observación real, versión de la app y ruta/URL de evidencia.")
    caso = next(c for c in casos if c["id"] == caso_id)
    if len(turnos) != len(caso["turnos"]):
        raise ValueError("Registrar todos los turnos del caso, en orden.")
    result = copy.deepcopy(registro)
    _congelar(result, config, "observacion_ui_hasta_respuesta_completa")
    fila = _fila(result, caso_id)
    if fila["estado"] != "no_ejecutado":
        raise ValueError("Conservar el registro existente y abrir otra corrida.")
    verificados = []
    for pregunta, turno in zip(caso["turnos"], turnos):
        if turno.get("pregunta") != pregunta:
            raise ValueError("La pregunta debe coincidir con el banco congelado.")
        latencia = turno.get("latencia_s")
        if isinstance(latencia, bool) or not isinstance(latencia, (int, float)) or not math.isfinite(latencia) or latencia <= 0:
            raise ValueError("Registrar latencia positiva medida hasta respuesta final completa.")
        verificado = validar_respuesta(turno, catalogo)
        if verificado["modelo"] != config["modelo_llm"]:
            raise ValueError("Modelo diferente de la configuración congelada.")
        verificados.append({"pregunta": pregunta, **verificado, "latencia_s": latencia})
    _sin_secretos(evidencia)
    fila.update(estado="ejecutado_sin_revision", origen="observacion_ui_real", ejecucion_real=True,
                version_app=config["version_app"], version_prompt=config["version_prompt"],
                config_ejecucion=copy.deepcopy(result["config_ejecucion"]),
                top_k=caso.get("top_k", 3) if config.get("usar_top_k_por_caso", True) else config.get("top_k",3),
                evidencia=evidencia, fecha_utc=ahora(),
                run_id=str(uuid.uuid4()), turnos=verificados,
                latencia_total_s=sum(t["latencia_s"] for t in verificados), incidencia=None)
    return result


def revisar_caso(registro, casos, caso_id, *, revisor, evidencia, afirmaciones_totales,
                 afirmaciones_respaldadas, citas_totales, citas_correctas, cumple,
                 abstencion_correcta=None, observaciones=""):
    result = copy.deepcopy(registro)
    fila = _fila(result, caso_id)
    if not fila.get("ejecucion_real") or fila["estado"] not in ("ejecutado_sin_revision", "revisado"):
        raise ValueError("No se califica un caso que no ha sido ejecutado con el LLM real.")
    if not revisor.strip() or not evidencia.strip() or not isinstance(cumple, bool):
        raise ValueError("Se requieren revisor, evidencia y cumple booleano.")
    conteos = [afirmaciones_totales, afirmaciones_respaldadas, citas_totales, citas_correctas]
    if any(type(x) is not int or x < 0 for x in conteos):
        raise ValueError("Los conteos deben ser enteros no negativos.")
    if afirmaciones_respaldadas > afirmaciones_totales or citas_correctas > citas_totales:
        raise ValueError("El numerador no puede superar el denominador.")
    caso = next(c for c in casos if c["id"] == caso_id)
    if caso["debe_abstenerse"] and not isinstance(abstencion_correcta, bool):
        raise ValueError("Evaluar explícitamente la abstención en este caso.")
    if not caso["debe_abstenerse"] and abstencion_correcta is not None:
        raise ValueError("La abstención no aplica a este caso; usar None.")
    if cumple:
        if afirmaciones_respaldadas != afirmaciones_totales or citas_correctas != citas_totales or abstencion_correcta is False:
            raise ValueError("Aprobación contradictoria: hay afirmaciones/citas sin respaldo o abstención incorrecta.")
        if not caso["debe_abstenerse"] and not caso["requiere_aclaracion"] and (not afirmaciones_totales or not citas_totales):
            raise ValueError("Una respuesta documental aprobada requiere afirmaciones y citas revisadas.")
        if any(t.get("avisos_estructura") for t in fila["turnos"]):
            raise ValueError("Resolver las referencias desconocidas o diferencias de modelo antes de aprobar.")
    _sin_secretos([revisor, evidencia, observaciones])
    fila["revision"] = {"revisor": revisor, "evidencia": evidencia, "fecha_utc": ahora(),
                        "afirmaciones_totales": afirmaciones_totales,
                        "afirmaciones_respaldadas": afirmaciones_respaldadas,
                        "citas_totales": citas_totales, "citas_correctas": citas_correctas,
                        "cumple": cumple, "abstencion_correcta": abstencion_correcta,
                        "observaciones": observaciones}
    fila["estado"] = "revisado"
    return result


def registrar_funcional(registro, prueba_id, *, cumple, evidencia, revisor, observaciones=""):
    if not isinstance(cumple, bool) or not evidencia or not revisor:
        raise ValueError("Registrar resultado real, evidencia y revisor.")
    result = copy.deepcopy(registro)
    _sin_secretos([evidencia, revisor, observaciones])
    fila = _fila(result, prueba_id, "funcionales")
    fila.update(estado="revisado", cumple=cumple, evidencia=evidencia,
                revisor=revisor, observaciones=observaciones, fecha_utc=ahora(), origen="observacion_ui_real")
    return result


def _porcentaje(n, d):
    return round(100 * n / d, 2) if d else None


def _percentil(valores, p):
    if not valores:
        return None
    s = sorted(valores)
    pos = (len(s) - 1) * p
    low, high = math.floor(pos), math.ceil(pos)
    return round(s[low] + (s[high] - s[low]) * (pos - low), 4)


def calcular_metricas(registro, casos):
    completas = [r for r in registro["casos"] if r.get("ejecucion_real") and r.get("origen") in ("adaptador_p1", "observacion_ui_real")
                 and r["estado"] in ("ejecutado_sin_revision", "revisado") and r.get("turnos")
                 and all(t.get("modo") == MODO_REAL for t in r["turnos"])]
    if registro.get("proposito") != "evaluacion_academica_real":
        completas = []
    for row in completas:
        if not row.get("config_ejecucion") or row["config_ejecucion"] != registro.get("config_ejecucion"):
            raise ValueError("Registros de configuraciones diferentes: separar corridas antes de calcular métricas.")
    revisadas = [r for r in completas if r["estado"] == "revisado" and r.get("revision")]
    at = sum(r["revision"]["afirmaciones_totales"] for r in revisadas)
    ar = sum(r["revision"]["afirmaciones_respaldadas"] for r in revisadas)
    ct = sum(r["revision"]["citas_totales"] for r in revisadas)
    cc = sum(r["revision"]["citas_correctas"] for r in revisadas)
    ids_abstencion = {c["id"] for c in casos if c["debe_abstenerse"]}
    abstenciones = [r for r in revisadas if r["id"] in ids_abstencion]
    ac = sum(r["revision"]["abstencion_correcta"] is True for r in abstenciones)
    ids_con_evidencia = {c["id"] for c in casos if not c["debe_abstenerse"] and not c["requiere_aclaracion"]}
    con_evidencia = [r for r in revisadas if r["id"] in ids_con_evidencia]
    sustentadas = sum(r["revision"]["cumple"] is True and r["revision"]["afirmaciones_totales"] > 0
                     and r["revision"]["afirmaciones_totales"] == r["revision"]["afirmaciones_respaldadas"] for r in con_evidencia)
    lat = [t["latencia_s"] for r in completas for t in r["turnos"]]
    funcionales_reales = [f for f in registro["funcionales"] if f.get("origen") == "observacion_ui_real"
                         and registro.get("proposito") == "evaluacion_academica_real"]
    errores_reales = [r for r in registro["casos"] if r["estado"] == "error" and r.get("ejecucion_real")
                      and r.get("origen") in ("adaptador_p1", "observacion_ui_real")
                      and registro.get("proposito") == "evaluacion_academica_real"]
    return {"casos_previstos": len(casos), "casos_ejecutados_completos": len(completas),
            "casos_revisados": len(revisadas), "casos_con_error": len(errores_reales),
            "afirmaciones_revisadas": at, "afirmaciones_respaldadas": ar,
            "fidelidad_pct": _porcentaje(ar, at), "citas_revisadas": ct, "citas_correctas": cc,
            "consultas_con_evidencia_revisadas": len(con_evidencia), "respuestas_sustentadas": sustentadas,
            "respuestas_sustentadas_pct": _porcentaje(sustentadas, len(con_evidencia)),
            "citas_correctas_pct": _porcentaje(cc, ct),
            "casos_abstencion_previstos": len(ids_abstencion), "casos_abstencion_revisados": len(abstenciones),
            "abstencion_correcta_pct": _porcentaje(ac, len(abstenciones)),
            "casos_que_cumplen": sum(r["revision"]["cumple"] is True for r in revisadas),
            "cumplimiento_casos_pct": _porcentaje(sum(r["revision"]["cumple"] is True for r in revisadas), len(revisadas)),
            "turnos_con_latencia": len(lat),
            "latencia_media_s": round(statistics.mean(lat), 4) if lat else None,
            "latencia_mediana_s": _percentil(lat, .5), "latencia_p95_s": _percentil(lat, .95),
            "funcionales_revisadas": sum(f["estado"] == "revisado" for f in funcionales_reales),
            "funcionales_aprobadas": sum(f["cumple"] is True for f in funcionales_reales),
            "nota": "None significa pendiente/no calculable, nunca cero de rendimiento. Calidad mediante revisión documentada de afirmaciones y citas, no coincidencia de palabras. Identificar revisión asistida en revisor/observaciones; la confirmación humana del equipo es distinta y no se presume. Muestra pequeña, no demuestra rendimiento general."}


def pendientes_cierre(registro, config, casos):
    pendientes = []
    m = calcular_metricas(registro, casos)
    # Solo una verificación explícita permite retirar estos bloqueos. Tener
    # código, modelo o claves configurados no demuestra conexión real.
    if config.get("qdrant_conexion_real_verificada") is not True:
        destino = ("la colección propia reconstruida desde las fuentes del ACA 1"
                   if config.get("destino_qdrant") == "propio"
                   else "la base vectorial del ACA 1")
        pendientes.append("Conectividad Qdrant: verificar la conexión real a " + destino + "; está pendiente o bloqueada y no se acredita recuperación cloud.")
    if config.get("destino_qdrant") == "propio":
        if config.get("base_propia_publicada") is not True:
            pendientes.append("Conectividad Qdrant: publicar y verificar la colección propia en Qdrant Cloud; la preparación local de corpus y embeddings no acredita publicación cloud.")
        if config.get("corpus_cloud_verificado") is not True:
            pendientes.append("Conectividad Qdrant: auditar la correspondencia del corpus cloud propio con las fuentes del ACA 1; una colección accesible y compatible no demuestra su contenido.")
    if config.get("llm_conexion_real_verificada") is not True:
        pendientes.append("Conectividad LLM: verificar una llamada real al modelo configurado; el código o las credenciales disponibles no acreditan ejecución.")
    if m["casos_revisados"] < len(casos):
        pendientes.append("Evaluación: ejecutar y revisar los 12 casos con recuperación cloud y LLM reales; una prueba aislada del LLM no acredita RAG.")
    if m["funcionales_revisadas"] < len(registro["funcionales"]):
        pendientes.append("Evaluación: documentar las 4 pruebas funcionales con evidencias reales; distinguir las comprobaciones con fixtures.")
    if any(r["estado"] == "error" or (r.get("revision") and not r["revision"]["cumple"]) for r in registro["casos"]):
        pendientes.append("Evaluación: resolver o documentar los casos fallidos; no ocultarlos.")
    if any(f["cumple"] is False for f in registro["funcionales"]):
        pendientes.append("Evaluación: resolver/documentar fallos funcionales.")
    for key in ("modelo_llm", "proveedor_llm", "version_app", "version_prompt", "justificacion_llm", "url_app", "url_repositorio", "url_video"):
        if not config.get(key):
            etiqueta = "Publicación" if key.startswith("url_") else "Configuración técnica"
            pendientes.append(etiqueta + ": completar dato real " + key)
    for key in ("captura_chat", "captura_documentos"):
        if not config.get(key) or not Path(config[key]).is_file():
            pendientes.append("Materiales: incorporar captura real sin secretos " + key)
    if not config.get("acceso_enlaces_verificado"):
        pendientes.append("Publicación: probar los enlaces con los permisos requeridos para el profesor; no asumir acceso anónimo.")
    if not config.get("video_voz_real_verificado"):
        pendientes.append("Video: grabar y verificar 3 a 5 minutos con voz real y pantalla; el guion no sustituye el archivo audiovisual.")
    if not config.get("credenciales_rotadas_confirmadas"):
        pendientes.append("Seguridad: rotación/revocación de credenciales previamente expuestas no confirmada; uso autorizado o retirada del código no equivalen a rotación.")
    if not config.get("autores_confirmados"):
        pendientes.append("Materiales: confirmar autores heredados del ACA 1 antes de entregar el póster.")
    return pendientes


def exportar_registros(registro, casos, carpeta):
    _sin_secretos(registro)
    if registro.get("proposito") != "evaluacion_academica_real" or any(r.get("origen") == "prueba_unitaria" for r in registro["casos"]):
        raise ValueError("Las pruebas unitarias no se exportan como resultados académicos.")
    out = Path(carpeta)
    out.mkdir(parents=True, exist_ok=True)
    metricas = calcular_metricas(registro, casos)
    guardar_json(out / "resultados_reales.json", registro)
    guardar_json(out / "metricas.json", metricas)
    fields = ["id", "estado", "origen", "version_app", "preguntas", "respuesta_final", "fuentes", "latencia_total_s", "cumple", "evidencia", "incidencia"]
    with (out / "registro_evaluacion.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in registro["casos"]:
            rev = r.get("revision") or {}
            row = {k: r.get(k) for k in fields}
            row.update(preguntas=" | ".join(next(c for c in casos if c["id"] == r["id"])["turnos"]),
                       respuesta_final=r["turnos"][-1]["respuesta"] if r["turnos"] else None,
                       fuentes=json.dumps(r["turnos"][-1]["fuentes"], ensure_ascii=False) if r["turnos"] else None,
                       cumple=rev.get("cumple"), evidencia=rev.get("evidencia", r.get("evidencia")))
            # Evitar que una respuesta maliciosa se ejecute como fórmula al abrir CSV.
            row = {k: ("'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v) for k, v in row.items()}
            w.writerow(row)
    incidencias = [{"id": r["id"], "estado": r["estado"], "detalle": r.get("incidencia") or (r.get("revision") or {}).get("observaciones"),
                    "responsable_solucion": "Equipo - bloque técnico integrado", "responsable_revalidacion": "Equipo - revisión documentada"}
                   for r in registro["casos"] if r["estado"] == "error" or (r.get("revision") and not r["revision"]["cumple"])]
    guardar_json(out / "incidencias.json", incidencias)
    return metricas


def escanear_paquete(carpeta):
    """Escaneo heurístico adicional; nunca devuelve el valor de una credencial."""
    hallazgos = []
    for p in Path(carpeta).rglob("*"):
        if not p.is_file() or "__pycache__" in p.parts:
            continue
        if p.name == ".env" or p.name == "secrets.toml":
            hallazgos.append({"archivo": str(p.relative_to(carpeta)), "motivo": "archivo de secretos no permitido"})
        if p.suffix in (".py", ".md", ".json", ".ipynb", ".html", ".txt", ".csv"):
            if _secreto(p.read_text(encoding="utf-8", errors="replace")):
                hallazgos.append({"archivo": str(p.relative_to(carpeta)), "motivo": "patrón de posible secreto"})
    return hallazgos
