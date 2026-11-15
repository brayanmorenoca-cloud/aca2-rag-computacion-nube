"""Regresiones OFFLINE de reconstrucción; nunca son evidencia cloud o RAG.

Todos los clientes, embeddings y pipelines sustitutos son fixtures explícitas.
Los archivos se crean exclusivamente en TemporaryDirectory y no se contacta
ningún servicio. Los tests no leen secretos reales ni escriben resultados reales.
"""
from __future__ import annotations

import copy
import builtins
import contextlib
import hashlib
import importlib.util
import json
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


def _json_file(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


class FakeNotFound(RuntimeError):
    status_code = 404


class FakeQdrantClient:
    """API mínima del cliente Qdrant en memoria. No contiene transporte HTTP."""

    def __init__(self, *, exists=False):
        self.exists = exists
        self.calls = []
        self.records = {}
        self.dimension = 384
        self.distance = "Cosine"
        self.indexes = {}
        self.error = None

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, copy.deepcopy(args), copy.deepcopy(kwargs)))
        if self.error:
            raise RuntimeError(self.error)

    def collection_exists(self, collection_name):
        self._record("collection_exists", collection_name=collection_name)
        return self.exists

    def get_collection(self, collection_name):
        self._record("get_collection", collection_name=collection_name)
        if not self.exists:
            raise FakeNotFound("Colección ficticia ausente")
        vectors = types.SimpleNamespace(size=self.dimension, distance=self.distance)
        return types.SimpleNamespace(
            config=types.SimpleNamespace(params=types.SimpleNamespace(vectors=vectors)),
            points_count=len(self.records), indexed_vectors_count=len(self.records),
            status="green", payload_schema=copy.deepcopy(self.indexes),
        )

    def create_collection(self, collection_name, vectors_config, **kwargs):
        self._record("create_collection", collection_name=collection_name,
                     vectors_config=vectors_config, **kwargs)
        if self.exists:
            raise AssertionError("La prueba intentó recrear una colección existente")
        self.exists = True
        get = vectors_config.get if isinstance(vectors_config, dict) else lambda key: getattr(vectors_config, key)
        self.dimension, self.distance = get("size"), get("distance")
        return True

    def create_payload_index(self, collection_name, field_name, field_schema, **kwargs):
        self._record("create_payload_index", collection_name=collection_name,
                     field_name=field_name, field_schema=field_schema, **kwargs)
        self.indexes[field_name] = types.SimpleNamespace(data_type="keyword")
        return True

    def upsert(self, collection_name, points, **kwargs):
        self._record("upsert", collection_name=collection_name, points=points, **kwargs)
        for point in points:
            data = point if isinstance(point, dict) else vars(point)
            point_id = data["id"]
            if point_id in self.records:
                raise AssertionError("No se permite sobreescribir puntos ni siquiera en el cliente ficticio")
            self.records[point_id] = types.SimpleNamespace(
                id=point_id, payload=copy.deepcopy(data["payload"]),
                vector=copy.deepcopy(data["vector"]),
            )
        return types.SimpleNamespace(status="completed", operation_id=1)

    def retrieve(self, collection_name, ids, **kwargs):
        self._record("retrieve", collection_name=collection_name, ids=ids, **kwargs)
        return [copy.deepcopy(self.records[key]) for key in ids if key in self.records]

    def scroll(self, collection_name, *, limit=100, offset=None, **kwargs):
        self._record("scroll", collection_name=collection_name, limit=limit, offset=offset, **kwargs)
        ids = sorted(self.records)
        if offset is not None:
            ids = [key for key in ids if key >= offset]
        selected = ids[:limit]
        next_offset = ids[limit] if len(ids) > limit else None
        return [copy.deepcopy(self.records[key]) for key in selected], next_offset

    def count(self, collection_name, **kwargs):
        self._record("count", collection_name=collection_name, **kwargs)
        return types.SimpleNamespace(count=len(self.records))

    def close(self):
        self._record("close")

    def delete_collection(self, *args, **kwargs):
        raise AssertionError("DELETE está prohibido")

    def recreate_collection(self, *args, **kwargs):
        raise AssertionError("RECREATE está prohibido")

    def delete(self, *args, **kwargs):
        raise AssertionError("Borrar puntos está prohibido")


class FakeArray(list):
    @property
    def shape(self):
        return len(self), len(self[0]) if self else 0

    def tolist(self):
        return copy.deepcopy(list(self))


class FakeModel:
    """Doble con dimensiones válidas; NO reproduce el modelo de embeddings."""

    max_seq_length = 128

    def __init__(self, tokens=12):
        self.tokens = tokens
        self.queries = []

    def tokenizer(self, text, **kwargs):
        self.queries.append((text, kwargs))
        return {"input_ids": [1] * self.tokens}

    def get_sentence_embedding_dimension(self):
        return 384

    def __getitem__(self, index):
        return types.SimpleNamespace(auto_model=types.SimpleNamespace(
            config=types.SimpleNamespace(_commit_hash="fixture-no-modelo-real")))


class FakePipeline:
    """Escritor y fragmentador determinista SINTÉTICO, solo para contratos."""

    MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    COLLECTION = "superstore_rag_docs"
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 80
    DIMENSION = 384
    SOURCE_TYPE = "academico_simulado"

    def __init__(self, *, tokens=12):
        self.calls = []
        self.tokens = tokens

    def preparar_dataset(self, root, zip_path):
        root = Path(root)
        self.calls.append("preparar_dataset")
        for name in ("data", "corpus", "salidas", "materiales", "entrega", "integracion"):
            (root / name).mkdir(parents=True, exist_ok=True)
        audit = {"csv_sha256": "fixture-csv", "categories": ["Furniture", "Office Supplies", "Technology"],
                 "ship_modes": ["First Class", "Same Day", "Second Class", "Standard Class"],
                 "segments": ["Consumer", "Corporate", "Home Office"],
                 "regions": ["Central", "East", "South", "West"],
                 "sub_categories": []}
        _json_file(root / "salidas/auditoria_dataset.json", audit)
        return None, audit

    def construir_documentos(self, root, docs, queries):
        root = Path(root)
        self.calls.append("construir_documentos")
        self.docs = copy.deepcopy(docs)
        registry = []
        for doc in sorted(docs, key=lambda x: x["filename"]):
            text = "# " + doc["title"] + "\n\n"
            for section in doc["sections"]:
                text += "## " + section["id"] + " | " + section["title"] + "\n\n" + section["text"].strip() + "\n\n"
                registry.append({**section["metadata"], "doc_source": doc["filename"],
                                 "section_id": section["id"],
                                 "page_section": section["id"] + " | " + section["title"],
                                 "source_type": self.SOURCE_TYPE})
            (root / "corpus" / doc["filename"]).write_text(text, encoding="utf-8")
        _json_file(root / "corpus/registro_secciones.json", registry)
        _json_file(root / "data/consultas_evaluacion.json", queries)
        return registry

    def fragmentar(self, root, audit):
        root = Path(root)
        self.calls.append("fragmentar")
        chunks = []
        for doc in sorted(self.docs, key=lambda x: x["filename"]):
            source_sha = _sha((root / "corpus" / doc["filename"]).read_bytes())
            for section in doc["sections"]:
                text = section["text"].strip()
                for ordinal, start in enumerate(range(0, len(text), 420), 1):
                    fragment = text[start:start + 500]
                    metadata = {**section["metadata"], "doc_source": doc["filename"],
                        "section_id": section["id"], "page_section": section["id"] + " | " + section["title"],
                        "source_type": self.SOURCE_TYPE, "source_sha256": source_sha,
                        "chunk_in_section": ordinal, "content_sha256": _sha(fragment)}
                    chunks.append({"id": len(chunks) + 1, "text": fragment, "metadata": metadata})
        version = "superstore-academico-" + _sha(json.dumps(chunks, ensure_ascii=False, sort_keys=True) +
            "|500|80|" + self.MODEL_ID)[:12]
        for chunk in chunks:
            chunk["metadata"]["corpus_version"] = version
        _json_file(root / "salidas/chunks_corpus.json", chunks)
        manifest = {"schema_version": "1.0", "corpus_version": version, "doc_count": 3,
            "section_count": 16, "chunk_count": len(chunks), "chunk_size": 500, "chunk_overlap": 80,
            "length_unit": "caracteres", "model_id": self.MODEL_ID, "dimension": 384,
            "distance": "Cosine", "collection": self.COLLECTION, "source_type": self.SOURCE_TYPE,
            "csv_sha256": audit["csv_sha256"],
            "sources": [{"file": p.name, "sha256": _sha(p.read_bytes())} for p in sorted((root / "corpus").glob("*.md"))],
            "chunks_sha256": _sha((root / "salidas/chunks_corpus.json").read_bytes())}
        _json_file(root / "salidas/manifiesto_corpus.json", manifest)
        return chunks, manifest

    def comprobar_reproducibilidad(self, root, audit, chunks, manifest):
        self.calls.append("comprobar_reproducibilidad")
        return {"regeneracion_identica": True, "fixture": True}

    def cargar_modelo(self, root, chunks):
        self.calls.append("cargar_modelo")
        model = FakeModel(self.tokens)
        if self.tokens > model.max_seq_length:
            raise ValueError("Fixture: fragmentos exceden límite, no se permite truncar")
        vectors = FakeArray([[1.0] + [0.0] * 383 for _ in chunks])
        _json_file(Path(root) / "salidas/entorno_ejecucion.json", {
            "model_id": self.MODEL_ID, "device": "cpu", "max_seq_length": 128,
            "max_observed_tokens": self.tokens, "truncated_chunks": 0,
            "model_commit": "fixture-no-modelo-real", "packages": {"fixture": "1"}})
        return model, vectors, []


class ReconstruccionQdrantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import reconstruir_qdrant
        cls.rq = reconstruir_qdrant

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aca2_reconstruccion_fixture_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = {"QDRANT_PROPIO_URL": "https://fixture-propio.cloud.qdrant.io",
                    "QDRANT_PROPIO_API_KEY": "TEST_PROPIO"}

    def _preparar(self, *, embeddings=False, tokens=12):
        self.pipeline = FakePipeline(tokens=tokens)
        preparacion = self.rq.preparar_corpus(
            self.root / "trabajo", pipeline=self.pipeline, permitir_fixtures=True)
        if embeddings:
            preparacion = self.rq.completar_embeddings(
                preparacion, pipeline=self.pipeline, permitir_fixtures=True)
        return preparacion

    def test_importar_no_carga_modelos_sdk_ni_red(self):
        original_import = builtins.__import__
        prohibidos = {"qdrant_client", "sentence_transformers", "transformers", "torch", "pandas", "numpy"}
        def control_import(nombre, *args, **kwargs):
            if nombre.split(".", 1)[0] in prohibidos:
                raise AssertionError("Importación no lazy: " + nombre)
            return original_import(nombre, *args, **kwargs)
        nombre = "reconstruir_qdrant_import_fixture"
        spec = importlib.util.spec_from_file_location(nombre, Path(self.rq.__file__))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {nombre: module}), patch("builtins.__import__", side_effect=control_import), \
             patch("socket.socket", side_effect=AssertionError("No se permite red al importar")):
            spec.loader.exec_module(module)
        self.assertTrue(callable(module.preparar_corpus))

    def test_destino_usa_variables_propias_y_omite_secretos_en_repr(self):
        destino = self.rq.DestinoPropio.from_env({**self.env,
            "QDRANT_URL": "https://fixture-anterior.cloud.qdrant.io", "QDRANT_API_KEY": "TEST_ANTERIOR"})
        self.assertEqual(destino.url, self.env["QDRANT_PROPIO_URL"])
        self.assertEqual(destino.api_key, self.env["QDRANT_PROPIO_API_KEY"])
        self.assertEqual(destino.coleccion, "superstore_rag_docs_aca2_propio")
        for value in (self.env["QDRANT_PROPIO_URL"], self.env["QDRANT_PROPIO_API_KEY"], "TEST_ANTERIOR"):
            self.assertNotIn(value, repr(destino))

    def test_destino_no_reutiliza_credenciales_heredadas(self):
        with self.assertRaises(self.rq.ReconstruccionError):
            self.rq.DestinoPropio.from_env({"QDRANT_URL": "https://fixture-anterior.cloud.qdrant.io",
                                           "QDRANT_API_KEY": "TEST_ANTERIOR"})

    def test_destino_rechaza_url_no_oficial_o_credenciales_en_url(self):
        for url in ("https://fixture.qdrant.io", "http://fixture.cloud.qdrant.io", "https://example.org",
                    "https://fixture.cloud.qdrant.io.evil.test", "https://u:TEST_PRIVATE@fixture.cloud.qdrant.io",
                    "https://fixture.cloud.qdrant.io/path", "https://fixture.cloud.qdrant.io?key=TEST_PRIVATE",
                    "https://fixture.cloud.qdrant.io#fragment"):
            with self.subTest(url=url), self.assertRaises(self.rq.ReconstruccionError) as error:
                self.rq.DestinoPropio.from_env({**self.env, "QDRANT_PROPIO_URL": url})
            self.assertNotIn(url, str(error.exception))
            self.assertNotIn("TEST_PRIVATE", str(error.exception))

    def test_destino_coleccion_fija_no_admite_heredada(self):
        with self.assertRaises(self.rq.ReconstruccionError):
            self.rq.DestinoPropio(url=self.env["QDRANT_PROPIO_URL"],
                api_key=self.env["QDRANT_PROPIO_API_KEY"], coleccion="superstore_rag_docs")

    def test_host_heredado_se_bloquea_aunque_se_pase_como_destino_propio(self):
        huella = _sha("fixture-propio.cloud.qdrant.io")
        with patch.object(self.rq, "LEGACY_HOST_SHA256", huella):
            for url in ("https://fixture-propio.cloud.qdrant.io", "https://FIXTURE-PROPIO.cloud.qdrant.io:6333"):
                with self.subTest(url=url), self.assertRaises(self.rq.ReconstruccionError) as error:
                    self.rq.DestinoPropio.from_env({**self.env, "QDRANT_PROPIO_URL": url})
                self.assertNotIn(url, str(error.exception))
                self.assertNotIn(self.env["QDRANT_PROPIO_API_KEY"], str(error.exception))

    def test_preparar_corpus_es_local_separado_y_sin_embeddings(self):
        visible = self.root / "trabajo" / "corpus" / "conservar.md"
        visible.parent.mkdir(parents=True)
        visible.write_text("NO_MODIFICAR", encoding="utf-8")
        preparacion = self._preparar()
        self.assertIsNone(preparacion.embeddings)
        self.assertTrue(preparacion.fixture)
        self.assertNotEqual(preparacion.ruta, visible.parent)
        self.assertEqual(visible.read_text(encoding="utf-8"), "NO_MODIFICAR")
        self.assertNotIn("cargar_modelo", self.pipeline.calls)
        self.assertIn("construir_documentos", self.pipeline.calls)
        self.assertIn("fragmentar", self.pipeline.calls)
        self.assertEqual(len({c["metadata"]["doc_source"] for c in preparacion.chunks}), 3)
        self.assertEqual(len({c["metadata"]["section_id"] for c in preparacion.chunks}), 16)
        self.assertEqual([c["id"] for c in preparacion.chunks], list(range(1, len(preparacion.chunks) + 1)))

    def test_pipeline_inyectado_requiere_identificar_fixture(self):
        pipeline = FakePipeline()
        with self.assertRaises(self.rq.ReconstruccionError):
            self.rq.preparar_corpus(self.root / "trabajo", pipeline=pipeline)
        self.assertEqual(pipeline.calls, [])

    def test_preparacion_repetida_no_regenera_ni_modifica_canonico(self):
        primero = self._preparar()
        anteriores = {str(p.relative_to(primero.ruta)): p.read_bytes()
                      for p in primero.ruta.rglob("*") if p.is_file()}
        segundo_pipeline = FakePipeline()
        segundo = self.rq.preparar_corpus(self.root / "trabajo", pipeline=segundo_pipeline, permitir_fixtures=True)
        self.assertEqual(primero.ruta, segundo.ruta)
        self.assertEqual(primero.chunks, segundo.chunks)
        self.assertEqual(anteriores, {str(p.relative_to(segundo.ruta)): p.read_bytes()
                                    for p in segundo.ruta.rglob("*") if p.is_file()})
        self.assertEqual(segundo_pipeline.calls, [])

    def test_divergencia_canonica_no_se_repara_sobrescribiendo(self):
        primero = self._preparar()
        documento = next((primero.ruta / "corpus").glob("*.md"))
        documento.write_text("CAMBIO_MANUAL_CONSERVADO", encoding="utf-8")
        pipeline = FakePipeline()
        with self.assertRaises(self.rq.ReconstruccionError):
            self.rq.preparar_corpus(self.root / "trabajo", pipeline=pipeline, permitir_fixtures=True)
        self.assertEqual(documento.read_text(encoding="utf-8"), "CAMBIO_MANUAL_CONSERVADO")
        self.assertEqual(pipeline.calls, [])

    def test_embedding_fixture_respeta_dimensiones_y_conserva_corpus(self):
        corpus = self._preparar()
        antes = copy.deepcopy(corpus.chunks)
        completo = self.rq.completar_embeddings(corpus, pipeline=self.pipeline, permitir_fixtures=True)
        self.assertTrue(completo.fixture)
        self.assertEqual(completo.chunks, antes)
        self.assertEqual(len(completo.embeddings), len(antes))
        self.assertTrue(all(len(v) == 384 for v in completo.embeddings))
        self.assertIn("cargar_modelo", self.pipeline.calls)

    def test_limite_tokenizer_no_se_convierte_en_truncamiento_o_exito(self):
        corpus = self._preparar(tokens=129)
        antes = copy.deepcopy(corpus.chunks)
        with self.assertRaises(self.rq.ReconstruccionError):
            self.rq.completar_embeddings(corpus, pipeline=self.pipeline, permitir_fixtures=True)
        self.assertIsNone(corpus.embeddings)
        self.assertEqual(corpus.chunks, antes)

    def test_wrapper_no_carga_modelo_por_defecto(self):
        pipeline = FakePipeline()
        preparacion = self.rq.preparar_reconstruccion(
            self.root / "trabajo", pipeline=pipeline, permitir_fixtures=True)
        self.assertIsNone(preparacion.embeddings)
        self.assertNotIn("cargar_modelo", pipeline.calls)

    def _publicar(self, preparacion, client, **kwargs):
        return self.rq.publicar_reconstruccion(
            preparacion, self.rq.DestinoPropio.from_env(self.env),
            client=client, permitir_fixtures=True, **kwargs)

    @staticmethod
    def _escrituras(client):
        return [c for c in client.calls if c[0] in {"create_collection", "create_payload_index", "upsert"}]

    def test_publicacion_requiere_confirmacion_explicita_antes_de_conectar(self):
        preparacion = self._preparar(embeddings=True)
        for confirmar in (False, None, "true", 1):
            client = FakeQdrantClient()
            with self.subTest(confirmar=confirmar), self.assertRaises(self.rq.ReconstruccionError):
                self._publicar(preparacion, client, confirmar_creacion=confirmar)
            self.assertEqual(client.calls, [])

    def test_corpus_sin_embeddings_no_es_publicable(self):
        preparacion = self._preparar()
        client = FakeQdrantClient()
        with self.assertRaises(self.rq.ReconstruccionError):
            self._publicar(preparacion, client, confirmar_creacion=True)
        self.assertEqual(client.calls, [])

    def test_fixture_no_puede_crear_cliente_remoto_ni_inyectado_sin_optin(self):
        preparacion = self._preparar(embeddings=True)
        destino = self.rq.DestinoPropio.from_env(self.env)
        client = FakeQdrantClient()
        with self.assertRaises(self.rq.ReconstruccionError):
            self.rq.publicar_reconstruccion(preparacion, destino,
                confirmar_creacion=True, client=client)
        self.assertEqual(client.calls, [])
        with patch("socket.socket", side_effect=AssertionError("Una fixture no debe crear transporte real")):
            with self.assertRaises(self.rq.ReconstruccionError):
                self.rq.publicar_reconstruccion(preparacion, destino,
                    confirmar_creacion=True, permitir_fixtures=True)

    def test_coleccion_nueva_crea_indices_y_payloads_completos_sin_recrear(self):
        preparacion = self._preparar(embeddings=True)
        client = FakeQdrantClient()
        resultado = self._publicar(preparacion, client, confirmar_creacion=True)
        self.assertIsInstance(resultado, dict)
        self.assertEqual(resultado["modo"], "prueba_unitaria_sin_evidencia_cloud")
        self.assertEqual(resultado["accion"], "creada")
        self.assertEqual(sum(c[0] == "create_collection" for c in client.calls), 1)
        campos = {c[2]["field_name"] for c in client.calls if c[0] == "create_payload_index"}
        self.assertTrue({"metadata.corpus_version", "metadata.category", "metadata.ship_mode", "metadata.segment",
                         "metadata.region", "metadata.doc_source", "metadata.section_id"} <= campos)
        self.assertEqual(set(client.records), {c["id"] for c in preparacion.chunks})
        for chunk, vector in zip(preparacion.chunks, preparacion.embeddings):
            point = client.records[chunk["id"]]
            self.assertEqual(point.payload, {"text": chunk["text"], "metadata": chunk["metadata"],
                "_reconstruction": {"manifest_sha256": preparacion.huella, "schema_version": self.rq.SCHEMA_VERSION}})
            self.assertEqual(point.vector, vector)
        upserts = [c for c in client.calls if c[0] == "upsert"]
        self.assertTrue(upserts)
        self.assertTrue(all(c[2].get("wait") is True for c in upserts))
        self.assertTrue(all("superstore_rag_docs_aca2_propio" == c[2].get("collection_name")
                            for c in client.calls if "collection_name" in c[2]))

    def test_coleccion_existente_identica_solo_se_verifica(self):
        preparacion = self._preparar(embeddings=True)
        client = FakeQdrantClient()
        self._publicar(preparacion, client, confirmar_creacion=True)
        antes = copy.deepcopy(client.records)
        client.calls.clear()
        resultado = self._publicar(preparacion, client, confirmar_creacion=True)
        self.assertIsInstance(resultado, dict)
        self.assertEqual(resultado["modo"], "prueba_unitaria_sin_evidencia_cloud")
        self.assertEqual(resultado["accion"], "verificada_sin_cambios")
        self.assertFalse(self._escrituras(client))
        self.assertEqual(client.records, antes)

    def test_id_aparecido_antes_de_lote_impide_upsert_y_se_conserva(self):
        preparacion = self._preparar(embeddings=True)
        client = FakeQdrantClient()
        insertado = {}

        def retrieve_con_escritura_concurrente(collection_name, ids, **kwargs):
            if not insertado:
                point_id = ids[0]
                ajeno = types.SimpleNamespace(
                    id=point_id,
                    payload={"text": "PUNTO_CONCURRENTE_NO_SOBRESCRIBIR", "metadata": {}},
                    vector=[1.0] + [0.0] * 383,
                )
                client.records[point_id] = ajeno
                insertado[point_id] = copy.deepcopy(ajeno)
            return FakeQdrantClient.retrieve(client, collection_name, ids, **kwargs)

        client.retrieve = retrieve_con_escritura_concurrente
        with self.assertRaises(self.rq.ReconstruccionError):
            self._publicar(preparacion, client, confirmar_creacion=True)
        self.assertTrue(insertado, "La publicación debe verificar IDs justo antes del lote")
        self.assertFalse(any(c[0] == "upsert" for c in client.calls))
        self.assertEqual(client.records, insertado)

    def test_existente_con_puntos_faltantes_no_se_completa_por_upsert(self):
        preparacion = self._preparar(embeddings=True)
        client = FakeQdrantClient()
        self._publicar(preparacion, client, confirmar_creacion=True)
        client.records.pop(next(iter(client.records)))
        antes = copy.deepcopy(client.records)
        client.calls.clear()
        with self.assertRaises(self.rq.ReconstruccionError):
            self._publicar(preparacion, client, confirmar_creacion=True)
        self.assertFalse(self._escrituras(client))
        self.assertEqual(client.records, antes)

    def test_existente_con_puntos_extra_no_se_limpia(self):
        preparacion = self._preparar(embeddings=True)
        client = FakeQdrantClient()
        self._publicar(preparacion, client, confirmar_creacion=True)
        extra = copy.deepcopy(next(iter(client.records.values())))
        extra.id = max(client.records) + 1
        client.records[extra.id] = extra
        antes = copy.deepcopy(client.records)
        client.calls.clear()
        with self.assertRaises(self.rq.ReconstruccionError):
            self._publicar(preparacion, client, confirmar_creacion=True)
        self.assertFalse(self._escrituras(client))
        self.assertEqual(client.records, antes)

    def test_payload_divergente_no_se_sobrescribe(self):
        preparacion = self._preparar(embeddings=True)
        client = FakeQdrantClient()
        self._publicar(preparacion, client, confirmar_creacion=True)
        point = next(iter(client.records.values()))
        point.payload["text"] = "TEXTO_DISTINTO_QUE_NO_SE_DEBE_BORRAR"
        antes = copy.deepcopy(client.records)
        client.calls.clear()
        with self.assertRaises(self.rq.ReconstruccionError):
            self._publicar(preparacion, client, confirmar_creacion=True)
        self.assertFalse(self._escrituras(client))
        self.assertEqual(client.records, antes)

    def test_vector_divergente_no_se_sobrescribe(self):
        preparacion = self._preparar(embeddings=True)
        client = FakeQdrantClient()
        self._publicar(preparacion, client, confirmar_creacion=True)
        point = next(iter(client.records.values()))
        point.vector = [0.0, 1.0] + [0.0] * 382
        antes = copy.deepcopy(client.records)
        client.calls.clear()
        with self.assertRaises(self.rq.ReconstruccionError):
            self._publicar(preparacion, client, confirmar_creacion=True)
        self.assertFalse(self._escrituras(client))
        self.assertEqual(client.records, antes)

    def test_manifiesto_remoto_divergente_no_se_reemplaza(self):
        preparacion = self._preparar(embeddings=True)
        client = FakeQdrantClient()
        self._publicar(preparacion, client, confirmar_creacion=True)
        point = next(iter(client.records.values()))
        point.payload["_reconstruction"]["manifest_sha256"] = "OTRA_RECONSTRUCCION_FIXTURE"
        antes = copy.deepcopy(client.records)
        client.calls.clear()
        with self.assertRaises(self.rq.ReconstruccionError):
            self._publicar(preparacion, client, confirmar_creacion=True)
        self.assertFalse(self._escrituras(client))
        self.assertEqual(client.records, antes)

    def test_indice_payload_faltante_en_existente_no_se_repara(self):
        preparacion = self._preparar(embeddings=True)
        client = FakeQdrantClient()
        self._publicar(preparacion, client, confirmar_creacion=True)
        client.indexes.pop("metadata.corpus_version")
        antes = copy.deepcopy(client.records)
        client.calls.clear()
        with self.assertRaises(self.rq.ReconstruccionError):
            self._publicar(preparacion, client, confirmar_creacion=True)
        self.assertFalse(self._escrituras(client))
        self.assertEqual(client.records, antes)

    def test_embeddings_invalidos_no_llegan_al_cliente(self):
        for vector in ([1.0] * 383, [float("nan")] + [0.0] * 383, [0.0] * 384):
            preparacion = self._preparar(embeddings=True)
            preparacion.embeddings[0] = vector
            client = FakeQdrantClient()
            with self.subTest(tipo=len(vector), valor_inicial=str(vector[0])), self.assertRaises(self.rq.ReconstruccionError):
                self._publicar(preparacion, client, confirmar_creacion=True)
            self.assertEqual(client.calls, [])

    def test_coleccion_incompatible_no_se_recrea(self):
        preparacion = self._preparar(embeddings=True)
        for dimension, distance in ((768, "Cosine"), (384, "Dot")):
            client = FakeQdrantClient(exists=True)
            client.dimension, client.distance = dimension, distance
            with self.subTest(dimension=dimension, distance=distance), self.assertRaises(self.rq.ReconstruccionError):
                self._publicar(preparacion, client, confirmar_creacion=True)
            self.assertFalse(self._escrituras(client))

    def test_error_cliente_no_divulga_clave_endpoint_ni_log(self):
        preparacion = self._preparar(embeddings=True)
        client = FakeQdrantClient()
        client.error = "fallo privado " + self.env["QDRANT_PROPIO_API_KEY"] + " " + self.env["QDRANT_PROPIO_URL"]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            with self.assertRaises(self.rq.ReconstruccionError) as error:
                self._publicar(preparacion, client, confirmar_creacion=True)
        texto = str(error.exception) + buffer.getvalue()
        self.assertNotIn(self.env["QDRANT_PROPIO_API_KEY"], texto)
        self.assertNotIn(self.env["QDRANT_PROPIO_URL"], texto)


if __name__ == "__main__":
    unittest.main()
