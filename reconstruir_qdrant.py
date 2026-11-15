"""Reconstrucción del corpus ACA 1 en un destino Qdrant propio y NUEVO.

No es una copia remota: utiliza las fuentes locales verificadas. Importar este
módulo no carga modelos, lee secretos ni conecta servicios. La publicación es
opt-in; nunca utiliza QDRANT_URL/QDRANT_API_KEY, nunca llama delete/recreate y
nunca modifica una colección ya existente, aunque le falten puntos o índices.

La carpeta canónica es distinta de ``corpus/`` (Markdown de presentación). El
pipeline ACA 1 genera allí sus encabezados ``## ID | título`` y su fragmentación
original. Las pruebas inyectadas se etiquetan como fixtures y no pueden publicar
en un cliente real. No confundir sus resultados con evidencia académica.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
import copy
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import types
from urllib.parse import urlparse


SCHEMA_VERSION = "aca2-reconstruccion-1.0"
MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSION = 384
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80
COLECCION_PROPIA = "superstore_rag_docs_aca2_propio"
LEGACY_HOST_SHA256 = "43167e7f7a4cdb90a59264ec03c7ad7f8d5df156b1f2e71675c306bdde37c74b"
CORPUS_SHA256_ACA1 = "1e34a469278740a59752a91c75d39308b48c7cf67e864d39923e2ae3a3f32ef2"
PIPELINE_SHA256_ACA1 = "0dfb7ae12175c619e3b43aa66058f2e9c085e92499bbe4d3c56aafb451422ff9"
DATASET_SHA256_ACA1 = "a9b35af6cf9530e61d42ec22ef6d485799c0ee7d2e4710f1f803a71b8f1c29cb"
KEYWORD_FIELDS = (
    "metadata.corpus_version", "metadata.category", "metadata.ship_mode",
    "metadata.segment", "metadata.region", "metadata.doc_source", "metadata.section_id",
)
MANIFEST_FILE = "manifiesto_reconstruccion.json"
ROOT = Path(__file__).resolve().parent


class ReconstruccionError(RuntimeError):
    """Error seguro: nunca contiene endpoints, valores de claves o cuerpos HTTP."""


def _sha(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        raise ReconstruccionError("No se pudo leer un artefacto local JSON. No se modificó su contenido.") from None


def _new_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(_json_bytes(data))


def _fingerprint(manifest):
    return _sha(_json_bytes(manifest))


@dataclass(frozen=True)
class DestinoPropio:
    url: str = field(repr=False)
    api_key: str = field(repr=False)
    coleccion: str = COLECCION_PROPIA

    def __post_init__(self):
        if not isinstance(self.url, str) or not isinstance(self.api_key, str):
            raise ReconstruccionError("El destino propio requiere URL y clave configuradas de forma privada.")
        try:
            parsed = urlparse(self.url.strip())
            hostname = (parsed.hostname or "").lower().rstrip(".")
            port = parsed.port
        except (TypeError, ValueError):
            raise ReconstruccionError("La URL propia tiene un formato no admitido.") from None
        if (parsed.scheme != "https" or not hostname.endswith(".cloud.qdrant.io")
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/") or port not in (None, 443, 6333)):
            raise ReconstruccionError("Se requiere un endpoint Qdrant Cloud HTTPS bajo .cloud.qdrant.io, sin rutas, parámetros ni credenciales en la URL.")
        if _sha(hostname) == LEGACY_HOST_SHA256:
            raise ReconstruccionError("Destino bloqueado: el host heredado no puede utilizarse para esta reconstrucción.")
        if not self.api_key.strip():
            raise ReconstruccionError("Falta QDRANT_PROPIO_API_KEY; no se reutiliza la clave del proyecto heredado.")
        if self.coleccion != COLECCION_PROPIA:
            raise ReconstruccionError("Solo está autorizada la colección nueva dedicada a esta reconstrucción.")
        object.__setattr__(self, "url", self.url.strip().rstrip("/"))
        object.__setattr__(self, "api_key", self.api_key.strip())

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        # Deliberadamente no se consultan los nombres estándar del destino viejo.
        return cls(url=env.get("QDRANT_PROPIO_URL", ""), api_key=env.get("QDRANT_PROPIO_API_KEY", ""))

    def public_dict(self):
        return {"coleccion": self.coleccion, "url_propia_configurada": bool(self.url),
                "clave_propia_configurada": bool(self.api_key), "host_heredado_bloqueado": True}


@dataclass
class Preparacion:
    ruta: Path
    manifiesto: dict
    chunks: list
    embeddings: list | None = None
    fixture: bool = False

    @property
    def huella(self):
        return _fingerprint(self.manifiesto)

    @property
    def publicable(self):
        return (not self.fixture and self.manifiesto.get("estado") == "embeddings_verificados"
                and self.embeddings is not None)

    def informe(self):
        keys = ("schema_version", "estado", "naturaleza", "modelo_embeddings", "dimension",
                "distancia", "chunk_size", "chunk_overlap", "corpus_version", "chunk_count",
                "doc_count", "section_count", "coleccion_destino", "fuentes", "tokenizacion",
                "modelo_revision", "entorno", "fixture")
        return {**{k: copy.deepcopy(self.manifiesto[k]) for k in keys if k in self.manifiesto},
                "manifiesto_sha256": self.huella, "publicable": self.publicable,
                "carpeta_canonica": self.ruta.name,
                "nota": "Reconstrucción desde fuentes locales del ACA 1; no copia ni comparación con el índice remoto heredado."}


def _tree_hashes(folder):
    folder = Path(folder)
    hashes = {}
    for p in sorted(folder.rglob("*")):
        if p.is_symlink():
            raise ReconstruccionError("Una carpeta canónica contiene un enlace simbólico; no se modifica ni utiliza.")
        if p.is_file() and p != folder / MANIFEST_FILE:
            hashes[p.relative_to(folder).as_posix()] = _sha(p.read_bytes())
    return hashes


def _limpiar(text):
    import unicodedata
    text = unicodedata.normalize("NFC", text).replace("\ufeff", "").replace("\r\n", "\n")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]+", " ", text)).strip()


def _validar_chunks(folder, corpus, chunks, original):
    docs = corpus.get("DOCS", [])
    section_map = {(d["filename"], s["id"]): s for d in docs for s in d["sections"]}
    if len(docs) != 3 or len(section_map) != 16 or len(corpus.get("QUERIES", [])) != 8:
        raise ReconstruccionError("Se requieren las tres fuentes, dieciséis secciones y ocho consultas del ACA 1.")
    if (not isinstance(chunks, list) or not chunks
            or [c.get("id") for c in chunks] != list(range(1, len(chunks) + 1))):
        raise ReconstruccionError("Los fragmentos requieren IDs enteros secuenciales únicos 1..N.")
    checks = {"model_id": MODEL_ID, "dimension": DIMENSION, "distance": "Cosine",
              "chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP,
              "doc_count": 3, "section_count": 16, "chunk_count": len(chunks)}
    if any(original.get(k) != v for k, v in checks.items()):
        raise ReconstruccionError("El manifiesto de fragmentación no respeta el contrato original del ACA 1.")
    coverage = {key: set() for key in section_map}
    full_texts = {key: re.sub(r"\s+", " ", _limpiar(sec["text"])) for key, sec in section_map.items()}
    pre_version = []
    seen_orders = {key: [] for key in section_map}
    for chunk in chunks:
        meta = chunk.get("metadata")
        text = chunk.get("text")
        if not isinstance(meta, dict) or not isinstance(text, str) or not text.strip() or len(text) > CHUNK_SIZE:
            raise ReconstruccionError("Hay fragmentos inválidos o mayores de 500 caracteres; no se truncaron.")
        key = (meta.get("doc_source"), meta.get("section_id"))
        if key not in section_map:
            raise ReconstruccionError("Un fragmento no corresponde a una fuente y sección del corpus verificado.")
        section = section_map[key]
        expected_meta = section["metadata"]
        for name in ("category", "ship_mode", "segment", "region", "sub_categories", "source_type"):
            if meta.get(name) != expected_meta.get(name):
                raise ReconstruccionError("Un metadato del fragmento difiere de la fuente del ACA 1.")
        if meta.get("source_type") != "academico_simulado":
            raise ReconstruccionError("El corpus debe conservar su naturaleza académica simulada.")
        if meta.get("page_section") != key[1] + " | " + section["title"]:
            raise ReconstruccionError("La referencia de sección no conserva el formato canónico del ACA 1.")
        if meta.get("content_sha256") != _sha(text):
            raise ReconstruccionError("No coincide el hash de un fragmento.")
        source = Path(folder) / "corpus" / key[0]
        if source.is_symlink() or not source.is_file() or meta.get("source_sha256") != _sha(source.read_bytes()):
            raise ReconstruccionError("No coincide la fuente Markdown canónica de un fragmento.")
        part = re.sub(r"\s+", " ", _limpiar(text))
        start = full_texts[key].find(part)
        if start < 0:
            raise ReconstruccionError("El texto de un fragmento no está en su sección fuente.")
        coverage[key].update(range(start, start + len(part)))
        seen_orders[key].append(meta.get("chunk_in_section"))
        before = copy.deepcopy(chunk)
        before["metadata"]["corpus_version"] = expected_meta.get("corpus_version")
        pre_version.append(before)
    for key, whole in full_texts.items():
        if any(i not in coverage[key] for i, char in enumerate(whole) if not char.isspace()):
            raise ReconstruccionError("Hay texto fuente no cubierto por los fragmentos; reconstrucción incompleta.")
        if seen_orders[key] != list(range(1, len(seen_orders[key]) + 1)):
            raise ReconstruccionError("El orden de fragmentos dentro de una sección no es reproducible.")
    version_input = json.dumps(pre_version, ensure_ascii=False, sort_keys=True) + f"|{CHUNK_SIZE}|{CHUNK_OVERLAP}|{MODEL_ID}"
    version = "superstore-academico-" + _sha(version_input)[:12]
    if original.get("corpus_version") != version or any(c["metadata"].get("corpus_version") != version for c in chunks):
        raise ReconstruccionError("La versión del corpus no corresponde a sus fuentes, orden y parámetros.")
    chunks_path = Path(folder) / "salidas" / "chunks_corpus.json"
    if (not chunks_path.is_file() or _read_json(chunks_path) != chunks
            or original.get("chunks_sha256") != _sha(chunks_path.read_bytes())):
        raise ReconstruccionError("El archivo puente de chunks no coincide con su manifiesto.")
    return version


def _validar_vectores(vectors, count):
    if hasattr(vectors, "tolist"):
        vectors = vectors.tolist()
    if not isinstance(vectors, list) or len(vectors) != count:
        raise ReconstruccionError("La cantidad de embeddings no coincide con los fragmentos.")
    clean = []
    for vector in vectors:
        if (not isinstance(vector, (list, tuple)) or len(vector) != DIMENSION
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector)):
            raise ReconstruccionError("Un embedding no tiene 384 valores numéricos finitos.")
        norm = math.sqrt(sum(v * v for v in vector))
        if not math.isclose(norm, 1.0, abs_tol=1e-5):
            raise ReconstruccionError("Los embeddings deben estar normalizados a norma L2 igual a uno.")
        clean.append([float(v) for v in vector])
    return clean


def _leer_preparacion(folder):
    folder = Path(folder)
    if folder.is_symlink():
        raise ReconstruccionError("La carpeta canónica no puede ser un enlace simbólico a otro directorio.")
    folder = folder.resolve()
    manifest = _read_json(folder / MANIFEST_FILE)
    if manifest.get("schema_version") != SCHEMA_VERSION or manifest.get("artefactos") != _tree_hashes(folder):
        raise ReconstruccionError("La carpeta canónica presenta cambios o archivos divergentes; no se sobrescribió ni reparó.")
    sources = manifest.get("fuentes", {})
    if type(manifest.get("fixture")) is not bool:
        raise ReconstruccionError("La preparación debe identificar explícitamente si es una fixture.")
    if not manifest["fixture"] and sources != {"corpus_sha256": CORPUS_SHA256_ACA1,
                                               "pipeline_sha256": PIPELINE_SHA256_ACA1,
                                               "dataset_zip_sha256": DATASET_SHA256_ACA1}:
        raise ReconstruccionError("Las fuentes canónicas no pertenecen a la versión auditada del ACA 1.")
    source_map = {"corpus_sha256": "corpus_fuente.json", "pipeline_sha256": "aca1_pipeline.py",
                  "dataset_zip_sha256": "dataset_original.zip"}
    if any(sources.get(k) != _sha((folder / "fuentes" / name).read_bytes()) for k, name in source_map.items()):
        raise ReconstruccionError("Las fuentes preservadas no coinciden con las huellas de la reconstrucción.")
    corpus = _read_json(folder / "fuentes" / "corpus_fuente.json")
    chunks = _read_json(folder / "salidas" / "chunks_corpus.json")
    original = _read_json(folder / "salidas" / "manifiesto_corpus.json")
    version = _validar_chunks(folder, corpus, chunks, original)
    if (manifest.get("corpus_version") != version or manifest.get("modelo_embeddings") != MODEL_ID
            or manifest.get("dimension") != DIMENSION or manifest.get("distancia") != "Cosine"
            or manifest.get("coleccion_destino") != COLECCION_PROPIA
            or manifest.get("chunk_count") != len(chunks) or manifest.get("doc_count") != 3
            or manifest.get("section_count") != 16 or manifest.get("chunk_size") != CHUNK_SIZE
            or manifest.get("chunk_overlap") != CHUNK_OVERLAP or manifest.get("normalizar_embeddings") is not True):
        raise ReconstruccionError("El contrato de la preparación no coincide con el destino y espacio vectorial autorizados.")
    vectors = None
    if manifest.get("estado") == "embeddings_verificados":
        vectors = _validar_vectores(_read_json(folder / "vectores" / "verificados.json"), len(chunks))
        audit = manifest.get("tokenizacion", {})
        if (audit.get("truncados") != 0 or not isinstance(audit.get("limite"), int)
                or not isinstance(audit.get("max_tokens"), int) or audit["max_tokens"] > audit["limite"]):
            raise ReconstruccionError("No existe una auditoría válida de tokenización sin truncamiento.")
    elif manifest.get("estado") != "corpus_preparado":
        raise ReconstruccionError("Estado local de reconstrucción no reconocido.")
    return Preparacion(folder, manifest, chunks, vectors, manifest.get("fixture") is True)


def _pipeline(path, injected, allow_fixture):
    if injected is not None:
        if allow_fixture is not True:
            raise ReconstruccionError("Un pipeline inyectado requiere modo fixture explícito; no es evidencia de reconstrucción real.")
        result = injected
    else:
        try:
            content = Path(path).read_bytes()
            if _sha(content) != PIPELINE_SHA256_ACA1:
                raise ReconstruccionError("La copia del pipeline ACA 1 difiere de la fuente auditada.")
            # Importar la copia exacta sin generar archivos de bytecode junto a ella.
            result = types.ModuleType("aca1_pipeline_reconstruccion")
            result.__file__ = str(path)
            exec(compile(content, str(path), "exec"), result.__dict__)
        except ReconstruccionError:
            raise
        except Exception:
            raise ReconstruccionError("No se pudo cargar la copia del pipeline ACA 1. Instala sus dependencias declaradas; no se inició conexión cloud.") from None
    for key, expected in (("MODEL_ID", MODEL_ID), ("DIMENSION", DIMENSION),
                          ("CHUNK_SIZE", CHUNK_SIZE), ("CHUNK_OVERLAP", CHUNK_OVERLAP)):
        if getattr(result, key, expected) != expected:
            raise ReconstruccionError("El pipeline cambió el modelo, dimensión o fragmentación acordados.")
    return result


def preparar_corpus(carpeta_base, *, corpus_path=None, pipeline_path=None, dataset_zip=None,
                    pipeline=None, permitir_fixtures=False):
    """Reconstruye fuentes/chunks locales; no descarga modelos ni consulta nube.

    Reejecutar verifica archivos existentes. Una divergencia bloquea y preserva
    todo. El directorio canónico no se comparte con el generador de materiales.
    """
    fixture = pipeline is not None
    if fixture and permitir_fixtures is not True:
        raise ReconstruccionError("Confirma el modo fixture para inyectar un pipeline de prueba.")
    paths = {
        "corpus_fuente.json": Path(corpus_path or ROOT / "corpus_fuente.json"),
        "aca1_pipeline.py": Path(pipeline_path or ROOT / "referencia/recursos_aca1/aca1_pipeline.py"),
        "dataset_original.zip": Path(dataset_zip or ROOT / "referencia/recursos_aca1/dataset_original.zip"),
    }
    try:
        source_bytes = {name: p.read_bytes() for name, p in paths.items()}
    except Exception:
        raise ReconstruccionError("Falta una fuente local de reconstrucción. No se accedió a la nube.") from None
    sources = {"corpus_sha256": _sha(source_bytes["corpus_fuente.json"]),
               "pipeline_sha256": _sha(source_bytes["aca1_pipeline.py"]),
               "dataset_zip_sha256": _sha(source_bytes["dataset_original.zip"])}
    if not fixture and sources != {"corpus_sha256": CORPUS_SHA256_ACA1,
                                    "pipeline_sha256": PIPELINE_SHA256_ACA1,
                                    "dataset_zip_sha256": DATASET_SHA256_ACA1}:
        raise ReconstruccionError("Las fuentes no coinciden con la versión auditada del ACA 1; no se reconstruye silenciosamente otra versión.")
    try:
        corpus = json.loads(source_bytes["corpus_fuente.json"])
    except Exception:
        raise ReconstruccionError("La fuente documental no es un JSON válido.") from None
    identity = _sha(_json_bytes({"fuentes": sources, "fixture": fixture, "schema_version": SCHEMA_VERSION}))[:16]
    base = Path(carpeta_base).resolve()
    destination = base / ("aca1_canonico_" + identity + "_fuentes")
    if destination.exists():
        return _leer_preparacion(destination)
    module = _pipeline(paths["aca1_pipeline.py"], pipeline, permitir_fixtures)
    base.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="aca1_preparando_fuentes_", dir=base))
    for dirname in ("fuentes", "data", "corpus", "salidas", "materiales", "entrega", "integracion"):
        (stage / dirname).mkdir(exist_ok=True)
    for name, content in source_bytes.items():
        (stage / "fuentes" / name).write_bytes(content)
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            _, audit = module.preparar_dataset(stage, stage / "fuentes/dataset_original.zip")
            module.construir_documentos(stage, corpus["DOCS"], corpus["QUERIES"])
            chunks, original = module.fragmentar(stage, audit)
        version = _validar_chunks(stage, corpus, chunks, original)
        manifest = {"schema_version": SCHEMA_VERSION, "estado": "corpus_preparado",
            "naturaleza": "reconstruccion_desde_fuentes_locales_no_copia_remota", "fuentes": sources,
            "modelo_embeddings": MODEL_ID, "dimension": DIMENSION, "distancia": "Cosine",
            "normalizar_embeddings": True, "chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP,
            "corpus_version": version, "chunk_count": len(chunks), "doc_count": 3, "section_count": 16,
            "coleccion_destino": COLECCION_PROPIA, "coleccion_referencia_aca1": "superstore_rag_docs",
            "fixture": fixture, "artefactos": _tree_hashes(stage)}
        _new_json(stage / MANIFEST_FILE, manifest)
        if destination.exists():
            raise ReconstruccionError("La carpeta canónica apareció durante la preparación. Se preservaron ambas carpetas sin reemplazar.")
        stage.rename(destination)
        return _leer_preparacion(destination)
    except ReconstruccionError:
        raise
    except Exception:
        raise ReconstruccionError("La preparación local no se completó. Se preservó su carpeta de trabajo y no se modificó ninguna base remota.") from None


def preparar_embeddings(preparacion, *, pipeline=None, permitir_fixtures=False):
    """Carga el modelo real solo al invocarse y genera otra carpeta canónica.

    El corpus previamente preparado permanece intacto. El pipeline original
    audita tokens y rechaza sobrelongitud; no se acorta texto ni cambia chunking.
    """
    current = _leer_preparacion(preparacion.ruta)
    if current.huella != preparacion.huella or current.chunks != preparacion.chunks:
        raise ReconstruccionError("La preparación recibida difiere de los artefactos canónicos preservados.")
    if current.fixture and permitir_fixtures is not True:
        raise ReconstruccionError("Una preparación fixture no puede tratarse como evidencia real.")
    if pipeline is not None and permitir_fixtures is not True:
        raise ReconstruccionError("El modelo/pipeline inyectado requiere modo fixture explícito.")
    if current.manifiesto["estado"] == "embeddings_verificados":
        return current
    fixture = current.fixture or pipeline is not None
    destination = current.ruta.parent / (current.ruta.name.removesuffix("_fuentes") + ("_vectores_fixture" if fixture else "_vectores"))
    if destination.exists():
        existing = _leer_preparacion(destination)
        if existing.manifiesto.get("corpus_preparado_sha256") != current.huella:
            raise ReconstruccionError("Los vectores existentes pertenecen a otra preparación; no se reemplazaron.")
        return existing
    module = _pipeline(current.ruta / "fuentes/aca1_pipeline.py", pipeline, permitir_fixtures)
    stage = Path(tempfile.mkdtemp(prefix="aca1_preparando_vectores_", dir=current.ruta.parent))
    # La carpeta temporal acaba de crearse; no se copia sobre archivos ajenos.
    for child in current.ruta.iterdir():
        if child.name == MANIFEST_FILE:
            continue
        target = stage / child.name
        if child.is_dir():
            shutil.copytree(child, target)
        else:
            shutil.copyfile(child, target)
    try:
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                model, raw_vectors, _ = module.cargar_modelo(stage, current.chunks)
        except Exception as error:
            if "exceden el límite del modelo" in str(error):
                raise ReconstruccionError("Hay fragmentos que exceden el límite del tokenizer. Se bloqueó la reconstrucción: requiere una adaptación explícita y versionada; no hubo truncamiento silencioso.") from None
            raise ReconstruccionError("No se pudo cargar o ejecutar el modelo de embeddings original. No se publicaron puntos ni se mostraron detalles privados.") from None
        if model.get_sentence_embedding_dimension() != DIMENSION:
            raise ReconstruccionError("El modelo no devuelve 384 dimensiones; no se publicarán vectores incompatibles.")
        limit = model.max_seq_length
        if not isinstance(limit, int) or limit <= 2:
            raise ReconstruccionError("El modelo no informa un límite de tokens verificable.")
        lengths = [len(model.tokenizer(c["text"], add_special_tokens=True, truncation=False)["input_ids"])
                   for c in current.chunks]
        if any(n > limit for n in lengths):
            raise ReconstruccionError("Hay fragmentos que exceden el límite del tokenizer. Se requiere adaptación explícita; no se recortó texto ni se autorizó publicación.")
        vectors = _validar_vectores(raw_vectors, len(current.chunks))
        _new_json(stage / "vectores/verificados.json", vectors)
        environment = _read_json(stage / "salidas/entorno_ejecucion.json")
        packages = {k: v for k, v in environment.get("packages", {}).items()
                    if k in ("sentence-transformers", "transformers", "torch", "langchain-text-splitters", "qdrant-client", "pandas", "numpy")
                    and isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9+_.-]{1,100}", v)}
        revision = environment.get("model_commit")
        revision = revision if isinstance(revision, str) and re.fullmatch(r"[a-fA-F0-9]{7,64}", revision) else None
        manifest = {**current.manifiesto, "estado": "embeddings_verificados", "fixture": fixture,
                    "corpus_preparado_sha256": current.huella,
                    "tokenizacion": {"min_tokens": min(lengths), "max_tokens": max(lengths),
                                     "limite": limit, "truncados": 0},
                    "modelo_revision": revision, "entorno": packages,
                    "artefactos": _tree_hashes(stage)}
        _new_json(stage / MANIFEST_FILE, manifest)
        if destination.exists():
            raise ReconstruccionError("La carpeta de vectores apareció durante el cálculo. No se reemplazaron archivos.")
        stage.rename(destination)
        return _leer_preparacion(destination)
    except ReconstruccionError:
        raise
    except Exception:
        raise ReconstruccionError("La verificación local de embeddings no se completó. Se preservó el trabajo sin publicar ni mostrar detalles privados.") from None


completar_embeddings = preparar_embeddings


def preparar_reconstruccion(carpeta_base, *, incluir_embeddings=False, **kwargs):
    prepared = preparar_corpus(carpeta_base, **kwargs)
    if incluir_embeddings:
        prepared = preparar_embeddings(prepared, pipeline=kwargs.get("pipeline"),
                                       permitir_fixtures=kwargs.get("permitir_fixtures", False))
    return prepared


def _get(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


def _payload(chunk, manifest_sha):
    return {"text": chunk["text"], "metadata": copy.deepcopy(chunk["metadata"]),
            "_reconstruction": {"manifest_sha256": manifest_sha, "schema_version": SCHEMA_VERSION}}


def _verificar_cloud(client, destination, prepared):
    info = client.get_collection(destination.coleccion)
    vectors = _get(_get(_get(info, "config", {}), "params", {}), "vectors")
    distance = _get(vectors, "distance")
    distance = _get(distance, "value", distance)
    if _get(vectors, "size") != DIMENSION or str(distance).lower() != "cosine":
        raise ReconstruccionError("La colección propia existente no coincide con 384 dimensiones/Cosine. No se recreó ni modificó.")
    schema = _get(info, "payload_schema", {})
    for key in KEYWORD_FIELDS:
        kind = _get(schema.get(key, {}), "data_type")
        kind = _get(kind, "value", kind)
        if str(kind).lower() != "keyword":
            raise ReconstruccionError("Falta o difiere un índice keyword requerido. La colección existente no fue reparada ni modificada.")
    expected_count = len(prepared.chunks)
    total = _get(client.count(destination.coleccion, exact=True), "count")
    if total != expected_count:
        raise ReconstruccionError("La colección tiene puntos faltantes o adicionales. No se sobrescribió ni completó automáticamente.")
    records, offset, cursors = [], None, set()
    for _ in range(expected_count + 1):
        result = client.scroll(destination.coleccion, limit=128, offset=offset,
                               with_payload=True, with_vectors=True)
        batch, next_offset = result
        records.extend(batch)
        if next_offset is None:
            break
        if str(next_offset) in cursors:
            raise ReconstruccionError("La paginación remota repitió un cursor; no se pudo verificar el contenido.")
        cursors.add(str(next_offset))
        offset = next_offset
    else:
        raise ReconstruccionError("La verificación remota excedió su límite de páginas.")
    by_id = {}
    for record in records:
        point_id = _get(record, "id")
        if type(point_id) is not int or point_id in by_id:
            raise ReconstruccionError("Hay IDs remotos duplicados o incompatibles; no se alteraron.")
        by_id[point_id] = record
    if set(by_id) != {c["id"] for c in prepared.chunks}:
        raise ReconstruccionError("Los IDs remotos no coinciden con el manifiesto; no se alteraron.")
    for chunk, expected_vector in zip(prepared.chunks, prepared.embeddings):
        record = by_id[chunk["id"]]
        if _get(record, "payload") != _payload(chunk, prepared.huella):
            raise ReconstruccionError("Hay payloads o manifiestos remotos divergentes; no se sobrescribieron.")
        vector = _get(record, "vector")
        if (not isinstance(vector, (list, tuple)) or len(vector) != DIMENSION
                or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in vector)):
            raise ReconstruccionError("Hay vectores remotos incompatibles o no verificables; no se sobrescribieron.")
        norm = math.sqrt(sum(v * v for v in vector))
        if norm <= 0:
            raise ReconstruccionError("Un vector remoto tiene norma cero.")
        normal = [v / norm for v in vector]
        agreement = sum(a * b for a, b in zip(normal, expected_vector))
        if agreement < 0.999 or max(abs(a - b) for a, b in zip(normal, expected_vector)) > 1e-4:
            raise ReconstruccionError("Los vectores remotos difieren de la referencia reconstruida; no se sobrescribieron.")
    return expected_count


def publicar_reconstruccion(preparacion, destino=None, *, confirmar_creacion=False,
                            client=None, permitir_fixtures=False):
    """Crea solo la colección propia ausente, o verifica una existente sin writes.

    No intenta reparar una publicación interrumpida. Si una colección existe con
    diferencias, aborta preservándola. Un cliente inyectado es exclusivamente de
    prueba y requiere permitir_fixtures=True; no produce evidencia cloud real.
    """
    if confirmar_creacion is not True:
        raise ReconstruccionError("La creación remota requiere confirmar_creacion=True explícito.")
    prepared = _leer_preparacion(preparacion.ruta)
    if (prepared.huella != preparacion.huella or prepared.chunks != preparacion.chunks
            or prepared.embeddings != preparacion.embeddings):
        raise ReconstruccionError("La preparación en memoria difiere de sus artefactos. No se contactó ningún destino.")
    if prepared.manifiesto.get("estado") != "embeddings_verificados" or prepared.embeddings is None:
        raise ReconstruccionError("Faltan embeddings reales auditados; el corpus preparado por sí solo no puede publicarse.")
    if prepared.fixture and (client is None or permitir_fixtures is not True):
        raise ReconstruccionError("Una fixture nunca se publica mediante un cliente cloud real.")
    if client is not None and permitir_fixtures is not True:
        raise ReconstruccionError("Un cliente inyectado requiere modo fixture explícito.")
    destination = destino or DestinoPropio.from_env()
    # Revalidar incluso una instancia alterada fuera del constructor.
    destination = DestinoPropio(destination.url, destination.api_key, destination.coleccion)
    test_mode = client is not None
    own_client, models = False, None
    try:
        if client is None:
            from qdrant_client import QdrantClient, models
            client = QdrantClient(url=destination.url, api_key=destination.api_key, timeout=60)
            own_client = True
        exists = True
        try:
            client.get_collection(destination.coleccion)
        except Exception as error:
            status = getattr(error, "status_code", None)
            if status is None:
                status = getattr(getattr(error, "response", None), "status_code", None)
            if status != 404:
                raise ReconstruccionError("No se pudo comprobar el destino propio. No se asumió que la colección estuviera ausente.") from None
            exists = False
        if not exists:
            config = {"size": DIMENSION, "distance": "Cosine"} if test_mode else models.VectorParams(size=DIMENSION, distance=models.Distance.COSINE)
            created = client.create_collection(collection_name=destination.coleccion, vectors_config=config)
            if created is not True:
                raise ReconstruccionError("La creación no fue confirmada por Qdrant. No se iniciaron índices ni carga de puntos.")
            for key in KEYWORD_FIELDS:
                client.create_payload_index(collection_name=destination.coleccion, field_name=key,
                                            field_schema="keyword" if test_mode else models.PayloadSchemaType.KEYWORD,
                                            wait=True)
            # Si otro actor modificó la colección recién creada, no escribir.
            if _get(client.count(destination.coleccion, exact=True), "count") != 0:
                raise ReconstruccionError("La colección recién creada ya contiene puntos inesperados. No se insertaron ni sobrescribieron.")
            for start in range(0, len(prepared.chunks), 64):
                points = []
                for c, v in zip(prepared.chunks[start:start + 64], prepared.embeddings[start:start + 64]):
                    values = {"id": c["id"], "vector": v, "payload": _payload(c, prepared.huella)}
                    points.append(values if test_mode else models.PointStruct(**values))
                existing_ids = client.retrieve(destination.coleccion,
                    ids=[c["id"] for c in prepared.chunks[start:start + 64]],
                    with_payload=False, with_vectors=False)
                if existing_ids:
                    raise ReconstruccionError("Aparecieron IDs existentes antes de insertar el lote. No se sobrescribieron puntos; detener otros escritores en esta colección dedicada.")
                client.upsert(collection_name=destination.coleccion, points=points, wait=True)
        verified = _verificar_cloud(client, destination, prepared)
        return {"modo": "prueba_unitaria_sin_evidencia_cloud" if test_mode else "reconstruccion_cloud_real",
                "accion": "verificada_sin_cambios" if exists else "creada",
                "coleccion": destination.coleccion, "puntos_verificados": verified,
                "corpus_version": prepared.manifiesto["corpus_version"],
                "manifiesto_sha256": prepared.huella, "sin_original_tocado": True,
                "indices_keyword": list(KEYWORD_FIELDS),
                "nota": "Reconstrucción de fuentes locales verificada en destino propio; no se consultó ni clonó el índice heredado."}
    except ReconstruccionError:
        raise
    except Exception:
        raise ReconstruccionError("La publicación/verificación no se completó. No se borró ni recreó nada; una colección propia parcialmente creada debe revisarse, no repararse automáticamente. Los detalles privados no se mostraron.") from None
    finally:
        if own_client and client is not None:
            try:
                client.close()
            except Exception:
                pass
