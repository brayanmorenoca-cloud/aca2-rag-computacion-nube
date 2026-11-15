"""Pruebas locales de presentación y privacidad; NO son evidencias del LLM."""
from __future__ import annotations

import json
import importlib.util
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from app import (
    accesos_configurados, claves_qdrant_requeridas, exportar_conversacion,
    exportar_diagnostico, historial_llm, inicializar_secretos_streamlit,
    metadatos_publicos, numero_finito, resultado_publico, secretos_pendientes,
    texto_seguro_markdown,
)


def fixture_result():
    # Fixture explícito de interfaz: nunca se guarda en resultados de evaluación.
    return {
        "modo": "prueba_unitaria_simulada", "modelo": "fixture-model-ui-only",
        "respuesta": "Texto de prueba [F1].",
        "fuentes": [{"etiqueta": "F1", "fuente": "fixture.md", "seccion": "PRUEBA"}],
        "fragmentos": [{"etiqueta": "F1", "fuente": "fixture.md", "seccion": "PRUEBA",
                        "texto": "Contenido ficticio del test", "score": 0.51,
                        "metadatos": {"category": "General", "api_key": "NO_EXPORTAR"}}],
        "tiempos_s": {"total": 0.2}, "estado_respuesta": "test_fixture",
        "api_key": "NO_EXPORTAR", "debug": {"authorization": "NO_EXPORTAR"},
    }


class InterfaceContractTests(unittest.TestCase):
    def test_metadata_allowlist(self):
        metadata = metadatos_publicos({"category": "Technology", "region": "All", "token": "secret", "nested": {"secret": 1}})
        self.assertEqual(metadata, {"category": "Technology", "region": "All"})

    def test_metadata_non_dict(self):
        self.assertEqual(metadatos_publicos("secret"), {})

    def test_markdown_drops_remote_images_and_links(self):
        value = texto_seguro_markdown("[F1] ![alt](https://example.test/pixel) [sitio](https://example.test) <script>x</script>")
        self.assertIn("[F1]", value)
        self.assertNotIn("https://", value)
        self.assertNotIn("<script", value)

    def test_markdown_drops_reference_images(self):
        value = texto_seguro_markdown("![alt][a]\n[a]: https://example.test/pixel")
        self.assertNotIn("https://", value)
        self.assertNotIn("![", value)

    def test_history_never_contains_technical_payload(self):
        history = historial_llm([
            {"role": "user", "content": "Consulta"},
            {"role": "assistant", "content": "Respuesta", "api_key": "NO_EXPORTAR"},
            {"role": "system", "content": "NO_EXPORTAR"},
        ])
        self.assertEqual(history, [{"role": "user", "content": "Consulta"}, {"role": "assistant", "content": "Respuesta"}])

    def test_non_finite_numbers(self):
        for value in (None, "nan", float("inf"), "texto", True):
            self.assertIsNone(numero_finito(value))
        self.assertEqual(numero_finito("0.25"), 0.25)

    def test_result_removes_private_unexpected_fields(self):
        result = resultado_publico(fixture_result(), permitir_prueba=True)
        self.assertNotIn("NO_EXPORTAR", json.dumps(result))
        self.assertEqual(result["fuentes"][0]["etiqueta"], "F1")
        self.assertEqual(result["fragmentos"][0]["metadatos"], {"category": "General"})
        self.assertEqual(result["modo"], "prueba_unitaria_simulada")

    def test_rejects_mock_mode(self):
        result = fixture_result()
        result["modo"] = "fixture"
        with self.assertRaises(ValueError):
            resultado_publico(result, permitir_prueba=True)

    def test_rejects_empty_response(self):
        result = fixture_result()
        result["respuesta"] = " "
        with self.assertRaises(ValueError):
            resultado_publico(result, permitir_prueba=True)

    def test_rejects_unidentified_model(self):
        result = fixture_result()
        result["modelo"] = None
        with self.assertRaises(ValueError):
            resultado_publico(result, permitir_prueba=True)

    def test_export_does_not_include_unexpected_fields(self):
        value = exportar_conversacion([
            {"role": "user", "content": "Pregunta", "config": {"key": "NO_EXPORTAR"}},
            {"role": "assistant", "content": "Respuesta", "resultado": fixture_result()},
        ], permitir_prueba=True)
        self.assertNotIn("NO_EXPORTAR", value)
        parsed = json.loads(value)
        self.assertEqual(len(parsed["mensajes"]), 2)
        self.assertIn("no equivale", parsed["nota"])

    def test_export_ignores_system_state(self):
        value = json.loads(exportar_conversacion([{"role": "system", "content": "secret"}]))
        self.assertEqual(value["mensajes"], [])

    def test_missing_credentials_not_ready(self):
        self.assertEqual(accesos_configurados({}), {
            "QDRANT_URL": False, "QDRANT_API_KEY": False, "GEMINI_API_KEY": False,
        })

    def test_credentials_boolean_only(self):
        self.assertEqual(accesos_configurados({"claves_configuradas": {
            "qdrant_url": True, "QDRANT_API_KEY": True, "GEMINI_API_KEY": False,
        }}), {"QDRANT_URL": True, "QDRANT_API_KEY": True, "GEMINI_API_KEY": False})

    def test_colab_ai_does_not_require_gemini_key(self):
        self.assertEqual(secretos_pendientes({
            "requiere_gemini_key": False,
            "claves_configuradas": {"QDRANT_URL": True, "QDRANT_API_KEY": True},
        }), [])

    def test_api_requires_gemini_key(self):
        self.assertEqual(secretos_pendientes({
            "requiere_gemini_key": True,
            "claves_configuradas": {"QDRANT_URL": True, "QDRANT_API_KEY": True},
        }), ["GEMINI_API_KEY"])

    def test_owned_credentials_selected_without_legacy_requirement(self):
        config = {
            "destino_qdrant": "propio", "requiere_gemini_key": False,
            "claves_configuradas": {"QDRANT_PROPIO_URL": True, "QDRANT_PROPIO_API_KEY": True},
        }
        self.assertEqual(accesos_configurados(config), {
            "QDRANT_PROPIO_URL": True, "QDRANT_PROPIO_API_KEY": True, "GEMINI_API_KEY": False,
        })
        self.assertEqual(secretos_pendientes(config), [])

    def test_owned_missing_keys_never_fall_back_to_legacy(self):
        self.assertEqual(secretos_pendientes({
            "destino_qdrant": "propio", "requiere_gemini_key": False,
            "claves_configuradas": {"QDRANT_URL": True, "QDRANT_API_KEY": True},
        }), ["QDRANT_PROPIO_URL", "QDRANT_PROPIO_API_KEY"])

    def test_owned_partial_keys_never_mix_with_legacy(self):
        self.assertEqual(secretos_pendientes({
            "destino_qdrant": "propio", "requiere_gemini_key": False,
            "claves_configuradas": {"QDRANT_PROPIO_URL": True, "QDRANT_API_KEY": True},
        }), ["QDRANT_PROPIO_API_KEY"])

    def test_legacy_selection_never_uses_owned_keys(self):
        self.assertEqual(secretos_pendientes({
            "destino_qdrant": "heredado", "requiere_gemini_key": False,
            "claves_configuradas": {"QDRANT_PROPIO_URL": True, "QDRANT_PROPIO_API_KEY": True},
        }), ["QDRANT_URL", "QDRANT_API_KEY"])

    def test_owned_api_still_requires_gemini_key(self):
        self.assertEqual(secretos_pendientes({
            "destino_qdrant": "propio", "requiere_gemini_key": True,
            "claves_configuradas": {"QDRANT_PROPIO_URL": True, "QDRANT_PROPIO_API_KEY": True},
        }), ["GEMINI_API_KEY"])

    def test_invalid_destination_rejected(self):
        for destination in ("otro", "", None, ["propio"]):
            with self.subTest(destination=destination), self.assertRaises(ValueError):
                claves_qdrant_requeridas({"destino_qdrant": destination})

    def test_truthy_strings_are_not_configuration_booleans(self):
        self.assertEqual(accesos_configurados({
            "destino_qdrant": "propio",
            "claves_configuradas": {
                "QDRANT_PROPIO_URL": "true", "QDRANT_PROPIO_API_KEY": 'fixtur' + 'e-not-' + 'a-key', "GEMINI_API_KEY": 1,
            },
        }), {"QDRANT_PROPIO_URL": False, "QDRANT_PROPIO_API_KEY": False, "GEMINI_API_KEY": False})

    def test_diagnostic_records_destination_without_owned_credentials(self):
        diagnostic = exportar_diagnostico({
            "destino_qdrant": "propio", "coleccion": "fixture_owned",
            "QDRANT_PROPIO_URL": "NO_EXPORTAR", "QDRANT_PROPIO_API_KEY": "NO_EXPORTAR",
            "claves_configuradas": {"QDRANT_PROPIO_URL": True, "QDRANT_PROPIO_API_KEY": True},
        }, None)
        self.assertNotIn("NO_EXPORTAR", diagnostic)
        self.assertNotIn("QDRANT_PROPIO_API_KEY", diagnostic)
        self.assertEqual(json.loads(diagnostic)["configuracion_publica"]["destino_qdrant"], "propio")

    def test_ui_rejects_simulated_response_by_default(self):
        with self.assertRaises(ValueError):
            resultado_publico(fixture_result())

    def test_diagnostic_never_exports_credentials(self):
        diagnostic = exportar_diagnostico(
            {"modelo_llm": "fixture", "temperatura": None, "max_output_tokens": None,
             "parametros_gestionados_por_proveedor": True, "QDRANT_URL": "NO_EXPORTAR",
             "GEMINI_API_KEY": "NO_EXPORTAR", "claves_configuradas": {"NO_EXPORTAR": True}},
            {"puntos": 1, "compatible": True, "secret": "NO_EXPORTAR"}, 0,
        )
        self.assertNotIn("NO_EXPORTAR", diagnostic)
        self.assertIsNone(json.loads(diagnostic)["configuracion_publica"]["temperatura"])

    def test_empty_diagnostic_does_not_claim_cloud_verification(self):
        diagnostic = json.loads(exportar_diagnostico({}, None))
        self.assertIsNone(diagnostic["estado_indice_observado"])
        self.assertEqual(diagnostic["turnos_completados_sesion"], 0)


def fake_backend_module(ready=True, provider_managed=False, destino="heredado", access_override=None):
    """Sustitución exclusiva de tests: ni usa ni busca credenciales o internet."""
    module = types.ModuleType("rag_backend")

    class Config:
        @classmethod
        def from_env(cls):
            return "CONFIG_UI_FIXTURE_READY" if ready else "CONFIG_UI_FIXTURE_MISSING"

    class FakeConfig:
        def public_dict(self):
            prefix = "QDRANT_PROPIO" if destino == "propio" else "QDRANT"
            access = {prefix + "_URL": ready, prefix + "_API_KEY": ready,
                      "GEMINI_API_KEY": ready and not provider_managed}
            return {
                "coleccion": "fixture_ui_only", "modelo_llm": "fixture-model-ui-only",
                "destino_qdrant": destino,
                "modelo_embeddings": "fixture-encoder-ui-only", "dimension": 384,
                "temperatura": None if provider_managed else 0,
                "max_output_tokens": None if provider_managed else 200,
                "parametros_gestionados_por_proveedor": provider_managed,
                "version_app": "test", "version_prompt": "test",
                "requiere_gemini_key": not provider_managed,
                "claves_configuradas": access if access_override is None else dict(access_override),
            }

    # Instancia estable para no reiniciar el estado en cada rerun del test.
    config = FakeConfig()
    Config.from_env = classmethod(lambda cls: config)

    class RagError(Exception):
        pass

    class Service:
        def __init__(self, config):
            self.calls = []

        def responder(self, pregunta, historial=None, top_k=3, categoria="Todas", envio="Todos"):
            self.calls.append({"operation": "chat", "question": pregunta, "history": historial})
            if pregunta == "error-interno":
                raise RuntimeError("NO_EXPORTAR_EXCEPTION_SECRET")
            return fixture_result()

        def estado_indice(self):
            self.calls.append({"operation": "index"})
            return {"coleccion": "fixture_ui_only", "estado": "green", "puntos": 1,
                    "indexados": 0, "dimension": 384, "distancia": "Cosine", "compatible": True,
                    "solo_lectura": True, "version_corpus": "fixture", "metadatos_indexados": []}

        def explorar_documentos(self, **kwargs):
            self.calls.append({"operation": "docs"})
            return {"documentos": [{"fuente": "fixture.md", "secciones": ["PRUEBA"], "fragmentos_en_pagina": 1}],
                    "fragmentos": fixture_result()["fragmentos"], "next_page_offset": None, "parcial": False}

    module.Config = Config
    module.RagError = RagError
    module.RagService = Service
    return module


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit no instalado; ejecutar estas pruebas después de instalar requirements.txt")
class StreamlitSmokeTests(unittest.TestCase):
    """AppTest simulado. No certifica conectividad, fidelidad ni latencia real."""

    def make_app(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=15)
        app.secrets["GEMINI_MODEL"] = "fixture-model-ui-only"
        return app.run()

    def test_no_credentials_has_disabled_chat_no_external_calls(self):
        with patch.dict("sys.modules", {"rag_backend": fake_backend_module(False)}):
            app = self.make_app()
            self.assertFalse(app.exception)
            self.assertTrue(app.chat_input[0].disabled)
            self.assertEqual(app.session_state["_aca2_service"].calls, [])

    def test_colab_managed_parameters_with_no_gemini_key(self):
        with patch.dict("sys.modules", {"rag_backend": fake_backend_module(True, True)}):
            app = self.make_app()
            self.assertFalse(app.exception)
            self.assertFalse(app.chat_input[0].disabled)
            captions = " ".join(x.value for x in app.caption)
            self.assertIn("Colab AI administra", captions)
            self.assertNotIn("None tokens", captions)

    def test_owned_credentials_enable_chat_and_qdrant_panels(self):
        with patch.dict("sys.modules", {"rag_backend": fake_backend_module(True, True, "propio")}):
            app = self.make_app()
            self.assertFalse(app.exception)
            self.assertFalse(app.chat_input[0].disabled)
            self.assertFalse(app.button(key="aca2_docs_refresh").disabled)
            self.assertFalse(app.button(key="aca2_index_refresh").disabled)
            self.assertEqual(app.session_state["_aca2_service"].calls, [])
            app.button(key="aca2_docs_refresh").click().run()
            app.button(key="aca2_index_refresh").click().run()
            self.assertFalse(app.exception)
            self.assertEqual([call["operation"] for call in app.session_state["_aca2_service"].calls], ["docs", "index"])

    def test_owned_destination_with_legacy_only_stays_disabled(self):
        legacy = {"QDRANT_URL": True, "QDRANT_API_KEY": True, "GEMINI_API_KEY": True}
        with patch.dict("sys.modules", {"rag_backend": fake_backend_module(True, True, "propio", legacy)}):
            app = self.make_app()
            self.assertFalse(app.exception)
            self.assertTrue(app.chat_input[0].disabled)
            self.assertTrue(app.button(key="aca2_docs_refresh").disabled)
            self.assertTrue(app.button(key="aca2_index_refresh").disabled)
            self.assertEqual(app.session_state["_aca2_service"].calls, [])
            captions = " ".join(x.value for x in app.caption)
            self.assertIn("Faltan: QDRANT_PROPIO_URL, QDRANT_PROPIO_API_KEY", captions)

    def test_streamlit_root_named_secrets_reach_selected_config(self):
        # Parser real de Streamlit con datos/archivos sustituidos: no se leen
        # secretos reales ni se inicia RagService, Qdrant o un generador.
        from streamlit.runtime.secrets import Secrets
        from rag_backend import Config
        fixture = {
            "RAG_QDRANT_DESTINO": "propio", "RAG_LLM_BACKEND": "colab_ai",
            "GEMINI_MODEL": "google/fixture-colab-model",
            "QDRANT_PROPIO_URL": "https://fixture-owned.qdrant.io",
            "QDRANT_PROPIO_API_KEY": 'UI_FIX' + 'TURE_O' + 'WNED_N' + 'OT_A_R' + 'EAL_KE' + 'Y',
            "QDRANT_URL": "https://fixture-legacy.qdrant.io",
            "QDRANT_API_KEY": 'UI_FIX' + 'TURE_L' + 'EGACY_' + 'NOT_A_' + 'REAL_K' + 'EY',
        }
        secrets = Secrets()
        with patch.dict("os.environ", {}, clear=True), \
                patch("streamlit.runtime.secrets.config.get_option", return_value=["fixture-only.toml"]), \
                patch.object(Secrets, "_parse_file_path", return_value=(fixture, True)), \
                patch.object(Secrets, "_maybe_install_file_watchers"):
            inicializar_secretos_streamlit(types.SimpleNamespace(secrets=secrets))
            config = Config.from_env()
            self.assertEqual(config.destino_qdrant, "propio")
            self.assertEqual(config.qdrant_url, fixture["QDRANT_PROPIO_URL"])
            self.assertEqual(config.qdrant_api_key, fixture["QDRANT_PROPIO_API_KEY"])
            self.assertEqual(config.coleccion, "superstore_rag_docs_aca2_propio")
            self.assertEqual(secretos_pendientes(config.public_dict()), [])

    def test_chat_history_reset_and_session_isolation(self):
        with patch.dict("sys.modules", {"rag_backend": fake_backend_module(True)}):
            app = self.make_app()
            # Estado de usuario simulado, sin presentar una respuesta LLM ficticia.
            app.session_state["_aca2_messages"] = [{"role": "user", "content": "Pregunta primera"}]
            app.run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.chat_message), 1)
            app.chat_input[0].set_value("Pregunta siguiente").run()
            self.assertTrue(app.error)  # La UI rechaza la respuesta simulada.
            self.assertEqual(len(app.session_state["_aca2_service"].calls[0]["history"]), 1)
            other_session = self.make_app()
            self.assertEqual(len(other_session.chat_message), 0)
            app.button(key="aca2_reset").click().run()
            self.assertEqual(len(app.chat_message), 0)

    def test_document_and_index_panels(self):
        with patch.dict("sys.modules", {"rag_backend": fake_backend_module(True)}):
            app = self.make_app()
            app.button(key="aca2_docs_refresh").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.dataframe), 1)
            app.button(key="aca2_index_refresh").click().run()
            self.assertFalse(app.exception)
            self.assertTrue(app.session_state["_aca2_index"]["compatible"])

    def test_blank_question_does_not_call_service(self):
        with patch.dict("sys.modules", {"rag_backend": fake_backend_module(True)}):
            app = self.make_app()
            app.chat_input[0].set_value("   ").run()
            self.assertFalse(app.exception)
            self.assertEqual(app.session_state["_aca2_service"].calls, [])

    def test_unexpected_error_not_exposed(self):
        with patch.dict("sys.modules", {"rag_backend": fake_backend_module(True)}):
            app = self.make_app()
            app.chat_input[0].set_value("error-interno").run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertNotIn("NO_EXPORTAR", app.error[0].value)


if __name__ == "__main__":
    unittest.main()
