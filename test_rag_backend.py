"""Pruebas UNITARIAS sintéticas, sin red ni LLM. No son resultados del proyecto."""
import copy
import json
import sys
import types
import unittest
from unittest.mock import patch

from rag_backend import Config, RagError, RagService, EMBEDDING_DIM, generador_colab_ai, _clean_fragment


class Response:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return copy.deepcopy(self.data)


def point(number=1, section="ENV_STANDARD", text="El plazo simulado es de cuatro a seis días hábiles desde el despacho."):
    return {"id": number, "score": .8, "payload": {"text": text, "metadata": {
        "doc_source": "Manual_SLA_Logistica_Envios.md", "section_id": section,
        "category": "General", "ship_mode": "Standard Class", "corpus_version": "test-no-real",
        "source_type": "academico_simulado"}}}


class FakeSession:
    def __init__(self):
        self.calls = []
        self.points = [point(), point(2, "ENV_DELAY", "El sistema no consulta pedidos en vivo.")]
        self.dimension = EMBEDDING_DIM
        self.answer = {"respuesta": "El plazo simulado es de cuatro a seis días hábiles desde el despacho [F1].",
                       "citas": ["F1"], "estado": "fundamentada"}
        self.finish = "STOP"
        self.status = 200
        self.next_offset = None
        self.raise_message = None
        self.raw_text = None

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **copy.deepcopy(kwargs)})
        if self.raise_message:
            raise RuntimeError(self.raise_message)
        if self.status != 200:
            return Response({"error": "private-body-must-not-display"}, self.status)
        if "generativelanguage.googleapis.com" in url:
            text = self.raw_text if self.raw_text is not None else json.dumps(self.answer)
            return Response({"modelVersion": "gemini-test-unitario", "candidates": [{"finishReason": self.finish,
                "content": {"parts": [{"text": text}]}}], "usageMetadata": {"totalTokenCount": 99}})
        if url.endswith("/points/query"):
            return Response({"result": {"points": self.points}})
        if url.endswith("/points/count"):
            return Response({"result": {"count": len(self.points)}})
        if url.endswith("/points/scroll"):
            return Response({"result": {"points": self.points[:kwargs["json"]["limit"]], "next_page_offset": self.next_offset}})
        return Response({"result": {"status": "green", "points_count": len(self.points), "indexed_vectors_count": 0,
            "config": {"params": {"vectors": {"size": self.dimension, "distance": "Cosine"}}},
            "payload_schema": {"metadata.category": {}, "metadata.ship_mode": {}}}})


class FakeEncoder:
    def __init__(self):
        self.queries = []
        self.vector = [1.] + [0.] * (EMBEDDING_DIM - 1)

    def encode(self, texts, **kwargs):
        self.queries.extend(texts)
        return [self.vector]


class RagBackendTests(unittest.TestCase):
    def setUp(self):
        self.env = {"QDRANT_URL": "https://cluster-test.qdrant.io", "QDRANT_API_KEY": "TEST_QDRANT",
                    "GEMINI_API_KEY": "TEST_GEMINI", "GEMINI_MODEL": "gemini-test-unitario"}
        self.config = Config.from_env(self.env)
        self.session = FakeSession()
        self.encoder = FakeEncoder()
        self.service = RagService(self.config, session=self.session, encoder=self.encoder, transporte_real=False)

    def test_constructor_no_red(self):
        self.assertEqual(self.session.calls, [])
        self.assertEqual(self.encoder.queries, [])

    def test_destino_propio_no_reutiliza_secretos_heredados(self):
        config = Config.from_env({**self.env, "RAG_QDRANT_DESTINO": "propio"})
        self.assertEqual(config.qdrant_url, "")
        self.assertEqual(config.qdrant_api_key, "")
        self.assertEqual(config.coleccion, "superstore_rag_docs_aca2_propio")
        self.assertFalse(config.public_dict()["claves_configuradas"]["QDRANT_PROPIO_API_KEY"])

    def test_destino_propio_usa_solo_par_de_credenciales_propio(self):
        config = Config.from_env({**self.env, "RAG_QDRANT_DESTINO": "propio",
            "QDRANT_PROPIO_URL": "https://propio-test.cloud.qdrant.io",
            "QDRANT_PROPIO_API_KEY": "TEST_PROPIO",
            "QDRANT_COLLECTION": "coleccion_ajena"})
        self.assertEqual(config.qdrant_url, "https://propio-test.cloud.qdrant.io")
        self.assertEqual(config.qdrant_api_key, "TEST_PROPIO")
        self.assertEqual(config.destino_qdrant, "propio")
        self.assertEqual(config.coleccion, "superstore_rag_docs_aca2_propio")
        self.assertNotIn("TEST_PROPIO", repr(config) + json.dumps(config.public_dict()))

    def test_destino_desconocido_falla_cerrado(self):
        with self.assertRaises(RagError):
            Config.from_env({**self.env, "RAG_QDRANT_DESTINO": "otro"})

    def test_revision_embeddings_debe_ser_commit_verificado(self):
        config = Config.from_env({**self.env, "RAG_EMBEDDING_REVISION": "a" * 40})
        self.assertEqual(config.public_dict()["modelo_embeddings_revision"], "a" * 40)
        for invalido in ("main", "v1", "https://otra-url", "a" * 39):
            with self.subTest(revision=invalido), self.assertRaises(RagError):
                Config.from_env({**self.env, "RAG_EMBEDDING_REVISION": invalido})

    def test_public_config_and_repr_omit_credentials(self):
        exposed = repr(self.config) + json.dumps(self.config.public_dict())
        for key in ("QDRANT_URL", "QDRANT_API_KEY", "GEMINI_API_KEY"):
            self.assertNotIn(self.env[key], exposed)
        self.assertTrue(self.config.public_dict()["claves_configuradas"]["GEMINI_API_KEY"])

    def test_config_rejects_untrusted_urls_and_paths(self):
        for url in ("http://cluster.qdrant.io", "https://example.org", "https://u:p@cluster.qdrant.io", "https://cluster.qdrant.io?key=secret"):
            with self.subTest(url=url), self.assertRaises(RagError):
                Config.from_env({**self.env, "QDRANT_URL": url})

    def test_config_numeric_error_safe(self):
        with self.assertRaises(RagError) as error:
            Config.from_env({**self.env, "RAG_TEMPERATURE": "private-non-number"})
        self.assertNotIn("private-non-number", str(error.exception))

    def test_missing_gemini_no_network(self):
        s = RagService(Config.from_env({}), session=self.session)
        with self.assertRaises(RagError):
            s.responder("pregunta")
        self.assertEqual(self.session.calls, [])

    def test_read_only_operation_guard(self):
        with self.assertRaises(RagError):
            self.service._request("qdrant", "DELETE", self.service._collection_path())
        self.assertEqual(self.session.calls, [])

    def test_real_transport_not_claimed_by_tests(self):
        result = self.service.responder("¿Cuánto demora Standard Class?")
        self.assertEqual(result["modo"], "prueba_unitaria_simulada")
        self.assertEqual(result["modelo"], self.config.modelo_llm)
        self.assertEqual(result["fuentes"], [{"etiqueta": "F1", "fuente": "Manual_SLA_Logistica_Envios.md", "seccion": "ENV_STANDARD"}])
        self.assertEqual(len(result["fragmentos"]), 2)
        self.assertTrue(result["llm_llamado"])
        self.assertEqual(result["tokens"], {"totalTokenCount": 99})

    def test_keys_headers_only_never_url_or_prompt(self):
        self.service.responder("Plazo estándar")
        for call in self.session.calls:
            serialized = call["url"] + json.dumps(call["json"])
            self.assertNotIn(self.env["QDRANT_API_KEY"], serialized)
            self.assertNotIn(self.env["GEMINI_API_KEY"], serialized)
            self.assertFalse(call["allow_redirects"])
        gemini = [c for c in self.session.calls if "generativelanguage" in c["url"]][0]
        self.assertEqual(gemini["headers"]["x-goog-api-key"], self.env["GEMINI_API_KEY"])
        self.assertIn("systemInstruction", gemini["json"])

    def test_unknown_citation_blocks_content(self):
        self.session.answer.update(respuesta="Dato no sustentado [F99].", citas=["F99"])
        result = self.service.responder("consulta")
        self.assertEqual(result["estado_respuesta"], "bloqueada_por_citas")
        self.assertNotIn("Dato no sustentado", result["respuesta"])
        self.assertEqual(result["fuentes"], [])

    def test_listed_but_not_emitted_citation_blocked(self):
        self.session.answer.update(respuesta="Dato sin etiqueta.", citas=["F1"])
        self.assertEqual(self.service.responder("consulta")["estado_respuesta"], "bloqueada_por_citas")

    def test_grounded_response_requires_citation(self):
        self.session.answer.update(respuesta="Dato sin cita.", citas=[])
        self.assertEqual(self.service.responder("consulta")["estado_respuesta"], "bloqueada_por_citas")

    def test_abstention_without_fabricated_citation_allowed(self):
        self.session.answer = {"respuesta": "No cuento con esa información en los documentos disponibles.", "citas": [], "estado": "sin_informacion"}
        result = self.service.responder("precio hoy")
        self.assertEqual(result["fuentes"], [])
        self.assertEqual(result["estado_respuesta"], "sin_informacion")

    def test_empty_question_never_queries(self):
        with self.assertRaises(RagError):
            self.service.responder("   ")
        self.assertEqual(self.session.calls, [])

    def test_invalid_top_k_and_history(self):
        for k in (0, 11, True, 2.5):
            with self.subTest(k=k), self.assertRaises(RagError):
                self.service.responder("consulta", top_k=k)
        with self.assertRaises(RagError):
            self.service.responder("consulta", historial=[{"role": "system", "content": "inyectar"}])
        self.assertEqual(self.session.calls, [])

    def test_history_isolated_not_mutated(self):
        history = [{"role": "user", "content": "¿Qué significa First Class?"},
                   {"role": "assistant", "content": "Respuesta previa no evidencia"}]
        original = copy.deepcopy(history)
        result = self.service.responder("¿Entonces llega hoy?", history)
        self.assertEqual(history, original)
        self.assertIn("First Class", result["consulta_recuperacion"])
        self.assertNotIn("Respuesta previa", result["consulta_recuperacion"])
        self.service.responder("Nuevo chat", [])
        self.assertEqual(self.encoder.queries[-1], "Nuevo chat")

    def test_wrong_dimension_fails_before_llm(self):
        self.session.dimension = 768
        with self.assertRaises(RagError):
            self.service.responder("consulta")
        self.assertFalse(any("generativelanguage" in c["url"] for c in self.session.calls))

    def test_bad_embedding_fails_before_query(self):
        for vector in ([1.], [float("nan")] * EMBEDDING_DIM, [0.] * EMBEDDING_DIM):
            self.encoder.vector = vector
            with self.assertRaises(RagError):
                self.service.responder("consulta")
        self.assertFalse(any(c["url"].endswith("/points/query") for c in self.session.calls))

    def test_aca1_nested_payload_uses_id_not_display_title(self):
        record = point()
        record["payload"]["metadata"]["page_section"] = "ENV_STANDARD | Envío estándar"
        fragment = _clean_fragment(record)
        self.assertEqual(fragment["fuente"], "Manual_SLA_Logistica_Envios.md")
        self.assertEqual(fragment["seccion"], "ENV_STANDARD")
        self.assertEqual(fragment["metadatos"]["page_section"], "ENV_STANDARD | Envío estándar")
        record["payload"]["metadata"].pop("section_id")
        self.assertEqual(_clean_fragment(record)["seccion"], "ENV_STANDARD")

    def test_flat_legacy_payload_filters_keep_actual_namespace(self):
        record = point()
        record["payload"] = {"text": record["payload"]["text"], **record["payload"]["metadata"]}
        self.session.points = [record]
        self.service.responder("consulta", categoria="Furniture")
        query = [c["json"] for c in self.session.calls if c["url"].endswith("/points/query")][0]
        self.assertEqual(query["filter"]["must"][0]["key"], "category")

    def test_corpus_version_filter_not_guessed_from_document_version(self):
        cfg = Config.from_env({**self.env, "RAG_CORPUS_VERSION": "superstore-academico-testhash"})
        service = RagService(cfg, session=self.session, encoder=self.encoder, transporte_real=False)
        service.responder("consulta")
        query = [c["json"] for c in self.session.calls if c["url"].endswith("/points/query")][0]
        self.assertEqual(query["filter"]["must"][0], {"key": "metadata.corpus_version", "match": {"value": "superstore-academico-testhash"}})

    def test_aca1_token_limit_preserved_without_silent_truncation(self):
        self.encoder.max_seq_length = 128
        self.encoder.tokenizer = lambda text, truncation: {"input_ids": list(range(129))}
        with self.assertRaises(RagError) as err:
            self.service.responder("consulta")
        self.assertIn("no se truncó", str(err.exception))
        self.assertFalse(any(c["url"].endswith("/points/query") for c in self.session.calls))

    def test_filters_include_general_scope(self):
        self.service.responder("consulta", categoria="Technology", envio="Same Day")
        query = [c["json"] for c in self.session.calls if c["url"].endswith("/points/query")][0]
        self.assertEqual(query["filter"]["must"], [
            {"key": "metadata.category", "match": {"any": ["Technology", "General"]}},
            {"key": "metadata.ship_mode", "match": {"any": ["Same Day", "All"]}}])

    def test_pagination_and_document_count_not_confused(self):
        self.session.next_offset = 3
        result = self.service.explorar_documentos(limit=2)
        self.assertTrue(result["parcial"])
        self.assertEqual(result["next_page_offset"], 3)
        self.assertEqual(len(result["documentos"]), 1)
        self.assertEqual(result["documentos"][0]["fragmentos_en_pagina"], 2)

    def test_http_and_connection_errors_do_not_expose_private_data(self):
        self.session.status = 403
        with self.assertRaises(RagError) as error:
            self.service.estado_indice()
        self.assertNotIn("private-body", str(error.exception))
        self.session.raise_message = self.env["GEMINI_API_KEY"]
        with self.assertRaises(RagError) as error:
            self.service.estado_indice()
        self.assertNotIn(self.env["GEMINI_API_KEY"], str(error.exception))

    def test_invalid_json_and_incomplete_answer_rejected(self):
        self.session.raw_text = "{contenido sin cerrar"
        with self.assertRaises(RagError):
            self.service.responder("consulta")
        self.session.raw_text = None
        self.session.finish = "MAX_TOKENS"
        with self.assertRaises(RagError):
            self.service.responder("consulta")

    def test_credential_in_payload_blocked_before_llm_and_panel(self):
        self.session.points = [point(text="No publicar " + self.env["GEMINI_API_KEY"])]
        with self.assertRaises(RagError):
            self.service.responder("consulta")
        self.assertFalse(any("generativelanguage" in c["url"] for c in self.session.calls))
        with self.assertRaises(RagError):
            self.service.explorar_documentos()

    def test_credential_in_user_question_blocked_before_network(self):
        with self.assertRaises(RagError):
            self.service.responder(self.env["QDRANT_API_KEY"])
        self.assertEqual(self.session.calls, [])

    def test_missing_source_or_text_never_becomes_fake_evidence(self):
        self.session.points = [{"id": 1, "payload": {"text": "sin fuente"}}]
        with self.assertRaises(RagError):
            self.service.responder("consulta")

    def test_colab_generator_can_operate_without_gemini_key(self):
        cfg = Config.from_env({**self.env, "GEMINI_API_KEY": "", "RAG_LLM_BACKEND": "colab_ai", "GEMINI_MODEL": "google/gemini-test-unitario"})
        calls = []
        def generator(**kwargs):
            calls.append(kwargs)
            return {"text": json.dumps(self.session.answer), "model": cfg.modelo_llm}
        service = RagService(cfg, session=self.session, encoder=self.encoder, generador=generator, transporte_real=False)
        result = service.responder("consulta")
        self.assertEqual(result["estado_respuesta"], "fundamentada")
        self.assertFalse(cfg.public_dict()["requiere_gemini_key"])
        self.assertEqual(len(calls), 1)
        self.assertIn("CONTEXTO_DOCUMENTAL", calls[0]["user_prompt"])
        self.assertIsNone(calls[0]["temperature"])
        self.assertIsNone(calls[0]["max_output_tokens"])
        self.assertIsNone(result["modelo_version_reportada"])
        self.assertIsNone(result["parametros_generacion"]["temperatura"])
        self.assertFalse(any("generativelanguage" in c["url"] for c in self.session.calls))

    def test_colab_default_generator_lazy_no_call_in_constructor(self):
        cfg = Config.from_env({"RAG_LLM_BACKEND": "colab_ai"})
        service = RagService(cfg, session=self.session, encoder=self.encoder, transporte_real=False)
        self.assertIs(service._generador, generador_colab_ai)
        self.assertEqual(cfg.modelo_llm, "google/gemini-3.8-flash")
        self.assertTrue(cfg.public_dict()["parametros_gestionados_por_proveedor"])
        self.assertIsNone(cfg.public_dict()["temperatura"])
        self.assertIsNone(cfg.public_dict()["max_output_tokens"])
        self.assertIsNone(cfg.public_dict()["timeout_llm_s"])
        self.assertEqual(self.session.calls, [])

    def test_colab_model_mismatch_rejected(self):
        cfg = Config.from_env({**self.env, "RAG_LLM_BACKEND": "colab_ai", "GEMINI_MODEL": "google/gemini-test-unitario"})
        service = RagService(cfg, session=self.session, encoder=self.encoder,
            generador=lambda **kw: {"text": "{}", "model": "different"}, transporte_real=False)
        with self.assertRaises(RagError):
            service.responder("consulta")

    def test_colab_prefix_is_limited_to_google_and_backend(self):
        for backend, model in (("gemini_api", "google/gemini-test"), ("colab_ai", "gemini-test"),
                               ("colab_ai", "other/gemini-test"), ("colab_ai", "google/../secret")):
            with self.subTest(backend=backend, model=model), self.assertRaises(RagError):
                Config.from_env({"RAG_LLM_BACKEND": backend, "GEMINI_MODEL": model})

    def test_colab_official_wrapper_uses_only_public_sdk(self):
        calls = []
        sdk = types.ModuleType("google.colab.ai")
        def generate_text(prompt, *, model_name, stream):
            calls.append({"prompt": prompt, "model_name": model_name, "stream": stream})
            return "{\"respuesta\":\"salida sintética unitaria\",\"citas\":[],\"estado\":\"aclaracion\"}"
        sdk.generate_text = generate_text
        google = types.ModuleType("google")
        colab = types.ModuleType("google.colab")
        colab.ai = sdk
        google.colab = colab
        with patch.dict(sys.modules, {"google": google, "google.colab": colab, "google.colab.ai": sdk}):
            result = generador_colab_ai(system_prompt="sistema", user_prompt="datos", model="google/gemini-test-unitario",
                                        temperature=0.9, max_output_tokens=512)
        self.assertEqual(len(calls), 1)
        self.assertIn("sistema", calls[0]["prompt"])
        self.assertIn("datos", calls[0]["prompt"])
        self.assertEqual(calls[0]["model_name"], "google/gemini-test-unitario")
        self.assertFalse(calls[0]["stream"])
        self.assertFalse(result["usage"]["parametros_expuestos"])
        self.assertFalse(result["usage"]["conteo_tokens_expuesto"])

    def test_colab_sdk_failure_remains_safe(self):
        sdk = types.ModuleType("google.colab.ai")
        def generate_text(*args, **kwargs):
            raise RuntimeError("secret-value-must-never-be-displayed")
        sdk.generate_text = generate_text
        google = types.ModuleType("google")
        colab = types.ModuleType("google.colab")
        colab.ai = sdk
        google.colab = colab
        with patch.dict(sys.modules, {"google": google, "google.colab": colab, "google.colab.ai": sdk}):
            with self.assertRaises(RagError) as err:
                generador_colab_ai(system_prompt="sistema", user_prompt="datos", model="google/gemini-test-unitario")
        self.assertNotIn("secret-value", str(err.exception))

    def test_markdown_wrapped_json_format_only(self):
        self.session.raw_text = "```json\n" + json.dumps(self.session.answer) + "\n```"
        self.assertEqual(self.service.responder("consulta")["estado_respuesta"], "fundamentada")


if __name__ == "__main__":
    unittest.main(verbosity=2)
