"""Pruebas unitarias del evaluador, NO evaluación académica del chatbot.

No se realizan llamadas de red ni inferencia. Los adaptadores devuelven fixtures
en memoria con el modo que requiere la API para ejercitar sus validaciones.
Cualquier archivo de prueba se crea exclusivamente en TemporaryDirectory y se
elimina al terminar. No se guardan respuestas ficticias junto al paquete.

Ejecutar: python -B test_evaluacion_aca2.py
La salida del ejecutable solo comunica cantidad y resultado de las pruebas.
"""

import copy
import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import evaluacion_aca2 as ev
from banco_pruebas import CASOS, FUNCIONALES


class EvaluacionACA2Tests(unittest.TestCase):
    """Fixtures internas: nunca constituyen evidencia de calidad de la app."""

    @classmethod
    def setUpClass(cls):
        paquete = Path(__file__).resolve().parent
        candidatos = [paquete / "corpus_fuente.json", paquete.parent / "corpus_fuente.json"]
        cls.corpus_ruta = next((p for p in candidatos if p.is_file()), None)
        if cls.corpus_ruta is None:
            raise FileNotFoundError("Falta corpus_fuente.json para comprobar el banco.")
        contenido = cls.corpus_ruta.read_bytes()
        cls.corpus = json.loads(contenido)
        cls.corpus_sha256 = hashlib.sha256(contenido).hexdigest()
        cls.catalogo = ev.catalogar_corpus(cls.corpus)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="aca2_unittest_")
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)
        self.registro = ev.registro_vacio(CASOS, FUNCIONALES)
        self.config = {
            "version_app": "vfixture",
            "modelo_llm": "modelo_fixture",
            "version_prompt": "pfixture",
            "corpus_sha256": self.corpus_sha256,
            "top_k": 3,
            "usar_top_k_por_caso": True,
        }
        self.llamadas = []

    def respuesta_fixture(self, texto="fixture"):
        fuente = self.catalogo[0]
        return {
            "modo": ev.MODO_REAL,
            "modelo": "modelo_fixture",
            "respuesta": texto,
            "fuentes": [{"fuente": fuente["fuente"], "seccion": fuente["seccion"]}],
            "fragmentos": [{
                "fuente": fuente["fuente"],
                "seccion": fuente["seccion"],
                "texto": fuente["texto"],
            }],
        }

    def adaptador_fixture(self, **kwargs):
        self.llamadas.append(copy.deepcopy(kwargs))
        return self.respuesta_fixture()

    def ejecutar_fixture(self, ids=("C01",), registro=None, config=None, responder=None):
        return ev.ejecutar_bateria(
            responder or self.adaptador_fixture,
            CASOS,
            self.registro if registro is None else registro,
            self.catalogo,
            self.config if config is None else config,
            confirmar_real=True,
            ids=list(ids),
        )

    @staticmethod
    def fila(registro, caso_id="C01"):
        return next(r for r in registro["casos"] if r["id"] == caso_id)

    @staticmethod
    def kwargs_revision(**cambios):
        datos = {
            "revisor": "revisor_fixture",
            "evidencia": "evidencia_fixture",
            "afirmaciones_totales": 1,
            "afirmaciones_respaldadas": 1,
            "citas_totales": 1,
            "citas_correctas": 1,
            "cumple": True,
        }
        datos.update(cambios)
        return datos

    def test_01_integridad_banco_y_corpus(self):
        info = ev.validar_banco(CASOS, FUNCIONALES, self.corpus)
        self.assertEqual(info["casos_conversacionales"], 12)
        self.assertEqual(info["turnos_previstos"], 13)
        self.assertEqual(info["pruebas_funcionales"], 4)
        self.assertEqual(info["documentos_locales"], 3)
        self.assertEqual(info["secciones_documentales"], 16)
        self.assertEqual([c["id"] for c in CASOS], [f"C{i:02d}" for i in range(1, 13)])
        self.assertEqual([f["id"] for f in FUNCIONALES], [f"F{i:02d}" for i in range(1, 5)])

    def test_cambio_destino_vectorial_exige_corrida_nueva(self):
        inicial = {**self.config, "destino_qdrant": "heredado", "coleccion_activa": "original"}
        registro = self.ejecutar_fixture(config=inicial)
        with self.assertRaises(ValueError):
            self.ejecutar_fixture(ids=("C02",), registro=registro,
                config={**inicial, "destino_qdrant": "propio", "coleccion_activa": "propia"})

    def test_cambio_manifest_reconstruccion_exige_corrida_nueva(self):
        inicial = {**self.config, "reconstruccion_manifest_sha256": "a" * 64}
        registro = self.ejecutar_fixture(config=inicial)
        with self.assertRaises(ValueError):
            self.ejecutar_fixture(ids=("C02",), registro=registro,
                config={**inicial, "reconstruccion_manifest_sha256": "b" * 64})

    def test_secreto_qdrant_propio_no_se_serializa(self):
        with self.assertRaises(ValueError):
            ev._sin_secretos({"QDRANT_PROPIO_API_KEY": "F" * 24})
        for fuente in self.catalogo:
            self.assertEqual(fuente["metadatos"]["source_type"], "academico_simulado")
        banco_malo = copy.deepcopy(CASOS)
        banco_malo[0]["secciones_esperadas"] = ["SECCION_INEXISTENTE_FIXTURE"]
        with self.assertRaises(AssertionError):
            ev.validar_banco(banco_malo, FUNCIONALES, self.corpus)

    def test_02_pendientes_no_se_convierten_en_metricas_cero(self):
        metricas = ev.calcular_metricas(self.registro, CASOS)
        self.assertEqual(metricas["casos_ejecutados_completos"], 0)
        self.assertEqual(metricas["casos_revisados"], 0)
        for campo in (
            "fidelidad_pct", "citas_correctas_pct", "abstencion_correcta_pct",
            "cumplimiento_casos_pct", "latencia_media_s", "latencia_mediana_s", "latencia_p95_s",
        ):
            with self.subTest(campo=campo):
                self.assertIsNone(metricas[campo])

    def test_03_sin_confirmacion_no_invoca_adaptador(self):
        with self.assertRaises(ValueError):
            ev.ejecutar_bateria(
                self.adaptador_fixture, CASOS, self.registro, self.catalogo, self.config,
                confirmar_real=False, ids=["C01"],
            )
        self.assertEqual(self.llamadas, [])

    def test_04_sin_configuracion_no_invoca_adaptador(self):
        for campo in ("version_app", "modelo_llm", "version_prompt", "corpus_sha256"):
            with self.subTest(campo=campo):
                config = dict(self.config)
                config.pop(campo)
                with self.assertRaises(ValueError):
                    self.ejecutar_fixture(config=config)
        self.assertEqual(self.llamadas, [])

    def test_05_rechaza_top_k_sin_llm_y_modo_no_generativo(self):
        for respuesta in (
            [{"texto": "fixture", "score": 0.1}],
            {**self.respuesta_fixture(), "modo": "solo_recuperacion_fixture"},
            {**self.respuesta_fixture(), "respuesta": ""},
        ):
            with self.subTest(tipo=type(respuesta).__name__):
                with self.assertRaises(ValueError):
                    ev.validar_respuesta(respuesta, self.catalogo)
        resultado = self.ejecutar_fixture(responder=lambda **_: [])
        self.assertEqual(self.fila(resultado)["estado"], "error")
        self.assertEqual(self.fila(resultado)["turnos"], [])

    def test_06_fuentes_malformadas_y_desconocidas_no_se_aprueban(self):
        for fuente in ("fuente_fixture", {"fuente": "fixture", "seccion": 123}, {"fuente": "fixture"}):
            respuesta = self.respuesta_fixture()
            respuesta["fuentes"] = [fuente]
            with self.subTest(tipo=type(fuente).__name__):
                with self.assertRaises(ValueError):
                    ev.validar_respuesta(respuesta, self.catalogo)
        desconocida = self.respuesta_fixture()
        desconocida["fuentes"] = [{"fuente": "fuente_inexistente_fixture.md", "seccion": "NO_EXISTE_FIXTURE"}]
        resultado = self.ejecutar_fixture(responder=lambda **_: desconocida)
        self.assertTrue(self.fila(resultado)["turnos"][0]["avisos_estructura"])
        with self.assertRaises(ValueError):
            ev.revisar_caso(resultado, CASOS, "C01", **self.kwargs_revision())

    def test_07_no_filtra_tokens_de_respuestas_ni_excepciones(self):
        # Se construye en memoria: no es una credencial y no queda en este archivo.
        token = "s" + "k" + "-" + "F" * 24
        respuesta = self.respuesta_fixture("fixture " + token)
        with self.assertRaises(ValueError) as error:
            ev.validar_respuesta(respuesta, self.catalogo)
        self.assertFalse(token in str(error.exception), "El mensaje incluyó el token de prueba.")

        def fallar(**_):
            raise RuntimeError("error_fixture " + token)

        for adaptador in (lambda **_: respuesta, fallar):
            resultado = self.ejecutar_fixture(responder=adaptador)
            self.assertEqual(self.fila(resultado)["estado"], "error")
            self.assertFalse(token in json.dumps(resultado), "El registro incluyó el token de prueba.")
            self.assertEqual(self.fila(resultado)["turnos"], [])

    def test_08_historial_dos_turnos_aislado_por_caso(self):
        resultado = self.ejecutar_fixture(ids=("C06", "C07", "C08"))
        self.assertEqual(len(self.llamadas), 4)
        self.assertEqual([len(x["historial"]) for x in self.llamadas], [0, 0, 2, 0])
        historial = self.llamadas[2]["historial"]
        self.assertEqual([m["role"] for m in historial], ["user", "assistant"])
        self.assertEqual(historial[0]["content"], CASOS[6]["turnos"][0])
        self.assertEqual(historial[1]["content"], "fixture")
        self.assertEqual(len(self.fila(resultado, "C07")["turnos"]), 2)
        self.assertEqual(self.fila(self.registro, "C07")["turnos"], [])

    def test_09_preflight_impide_llamadas_si_un_caso_ya_fue_ejecutado(self):
        anterior = self.ejecutar_fixture(ids=("C02",))
        sin_cambios = copy.deepcopy(anterior)
        self.llamadas.clear()
        with self.assertRaises(ValueError):
            self.ejecutar_fixture(ids=("C01", "C02"), registro=anterior)
        self.assertEqual(self.llamadas, [])
        self.assertEqual(anterior, sin_cambios)

    def test_10_otra_version_o_configuracion_no_se_mezcla(self):
        anterior = self.ejecutar_fixture()
        for campo, valor in (
            ("version_app", "otra_version_fixture"),
            ("version_prompt", "otro_prompt_fixture"),
            ("modelo_llm", "otro_modelo_fixture"),
            ("corpus_sha256", "otro_hash_fixture"),
            ("top_k", 4),
        ):
            with self.subTest(campo=campo):
                config = {**self.config, campo: valor}
                self.llamadas.clear()
                with self.assertRaises(ValueError):
                    self.ejecutar_fixture(ids=("C02",), registro=anterior, config=config)
                self.assertEqual(self.llamadas, [])

    def test_11_revision_contradictoria_se_rechaza(self):
        ejecutado = self.ejecutar_fixture()
        for cambios in (
            {"afirmaciones_respaldadas": 0},
            {"citas_correctas": 0},
            {"afirmaciones_respaldadas": 2},
            {"afirmaciones_totales": 0, "afirmaciones_respaldadas": 0},
            {"citas_totales": 0, "citas_correctas": 0},
            {"afirmaciones_totales": True},
            {"abstencion_correcta": True},
        ):
            with self.subTest(campos=tuple(cambios)):
                with self.assertRaises(ValueError):
                    ev.revisar_caso(ejecutado, CASOS, "C01", **self.kwargs_revision(**cambios))
        abstencion = self.ejecutar_fixture(ids=("C08",))
        with self.assertRaises(ValueError):
            ev.revisar_caso(abstencion, CASOS, "C08", **self.kwargs_revision(abstencion_correcta=False))

    def test_12_origen_unitario_y_proposito_fixture_quedan_excluidos(self):
        ejecutado = self.ejecutar_fixture()
        variantes = []
        origen_unitario = copy.deepcopy(ejecutado)
        self.fila(origen_unitario)["origen"] = "prueba_unitaria"
        variantes.append(origen_unitario)
        proposito_unitario = copy.deepcopy(ejecutado)
        proposito_unitario["proposito"] = "prueba_unitaria"
        variantes.append(proposito_unitario)
        for registro in variantes:
            metricas = ev.calcular_metricas(registro, CASOS)
            self.assertEqual(metricas["casos_ejecutados_completos"], 0)
            self.assertEqual(metricas["turnos_con_latencia"], 0)
            self.assertIsNone(metricas["latencia_media_s"])
            self.assertIsNone(metricas["fidelidad_pct"])

    def test_13_no_se_revisa_antes_de_ejecutar(self):
        with self.assertRaises(ValueError):
            ev.revisar_caso(self.registro, CASOS, "C01", **self.kwargs_revision())
        self.assertIsNone(self.fila(self.registro)["revision"])

    def test_14_exportacion_de_fixtures_unitarias_prohibida(self):
        ejecutado = self.ejecutar_fixture()
        for criterio in ("proposito", "origen"):
            registro = copy.deepcopy(ejecutado)
            if criterio == "proposito":
                registro["proposito"] = "prueba_unitaria"
            else:
                self.fila(registro)["origen"] = "prueba_unitaria"
            destino = self.raiz / ("exportacion_bloqueada_" + criterio)
            with self.assertRaises(ValueError):
                ev.exportar_registros(registro, CASOS, destino)
            self.assertFalse(destino.exists())

    def test_15_importacion_manual_rechaza_pregunta_distinta(self):
        turno = {**self.respuesta_fixture(), "pregunta": "pregunta_fixture_no_pertenece_al_banco", "latencia_s": 1.0}
        with self.assertRaises(ValueError):
            ev.registrar_manual(
                self.registro, CASOS, self.catalogo, "C01", [turno], self.config,
                "evidencia_fixture", confirmar_real=True,
            )
        self.assertEqual(self.fila(self.registro)["estado"], "no_ejecutado")

    def test_16_csv_escapa_formulas_en_directorio_temporal(self):
        # Esta exportación solo ejercita el escritor CSV con una fixture controlada.
        # TemporaryDirectory evita dejar supuestos resultados académicos en disco.
        for i, prefijo in enumerate(("=", "+", "-", "@", " \t=")):
            texto = prefijo + "fixture"
            registro = self.ejecutar_fixture(responder=lambda **_: self.respuesta_fixture(texto))
            destino = self.raiz / f"csv_fixture_{i}"
            ev.exportar_registros(registro, CASOS, destino)
            with (destino / "registro_evaluacion.csv").open(encoding="utf-8-sig", newline="") as archivo:
                fila = next(csv.DictReader(archivo))
            self.assertEqual(fila["respuesta_final"], "'" + texto)
            self.assertEqual(self.fila(registro)["turnos"][0]["respuesta"], texto)

    def test_17_manual_rechaza_latencia_invalida_y_modelo_distinto(self):
        for latencia in (0, -1, True, float("nan"), float("inf"), None):
            turno = {**self.respuesta_fixture(), "pregunta": CASOS[0]["turnos"][0], "latencia_s": latencia}
            with self.subTest(latencia=repr(latencia)):
                with self.assertRaises(ValueError):
                    ev.registrar_manual(
                        self.registro, CASOS, self.catalogo, "C01", [turno], self.config,
                        "evidencia_fixture", confirmar_real=True,
                    )
        turno = {**self.respuesta_fixture(), "pregunta": CASOS[0]["turnos"][0], "latencia_s": 1.0, "modelo": "otro_modelo_fixture"}
        with self.assertRaises(ValueError):
            ev.registrar_manual(
                self.registro, CASOS, self.catalogo, "C01", [turno], self.config,
                "evidencia_fixture", confirmar_real=True,
            )

    def test_18_inicializacion_preserva_registro_y_detecta_banco_distinto(self):
        ruta = self.raiz / "registro_pendiente_fixture.json"
        primero = ev.inicializar_registro(ruta, CASOS, FUNCIONALES)
        segundo = ev.inicializar_registro(ruta, CASOS, FUNCIONALES)
        self.assertEqual(primero, segundo)
        contenido_anterior = ruta.read_bytes()
        casos = copy.deepcopy(CASOS)
        casos[0]["turnos"][0] += " pregunta_modificada_fixture"
        with self.assertRaises(AssertionError):
            ev.inicializar_registro(ruta, casos, FUNCIONALES)
        self.assertEqual(ruta.read_bytes(), contenido_anterior)

    def test_19_top_k_por_caso_y_configuracion_global(self):
        self.ejecutar_fixture(ids=("C01", "C05"))
        self.assertEqual([c["top_k"] for c in self.llamadas], [3, 5])
        self.llamadas.clear()
        self.ejecutar_fixture(ids=("C01", "C05"), config={**self.config, "usar_top_k_por_caso": False, "top_k": 4})
        self.assertEqual([c["top_k"] for c in self.llamadas], [4, 4])

    def test_20_escaneo_no_devuelve_valores_de_secretos(self):
        token = "s" + "k" + "-" + "F" * 24
        (self.raiz / "fixture.json").write_text(json.dumps({"valor": token}), encoding="utf-8")
        (self.raiz / ".env").write_text("FIXTURE=contenido_no_sensible", encoding="utf-8")
        hallazgos = ev.escanear_paquete(self.raiz)
        self.assertEqual({x["archivo"] for x in hallazgos}, {"fixture.json", ".env"})
        self.assertFalse(token in json.dumps(hallazgos), "El escaneo devolvió el token de prueba.")
        with self.assertRaises(ValueError) as error:
            ev._sin_secretos({"OPENAI_API_KEY": "F" * 24})
        self.assertFalse("F" * 24 in str(error.exception), "El error incluyó el valor de prueba.")

    def test_21_funcionales_unitarias_excluidas_por_proposito_y_origen(self):
        observado = ev.registrar_funcional(
            self.registro, "F01", cumple=True,
            evidencia="evidencia_fixture", revisor="revisor_fixture",
        )
        control = ev.calcular_metricas(observado, CASOS)
        self.assertEqual(control["funcionales_revisadas"], 1)
        self.assertEqual(control["funcionales_aprobadas"], 1)
        for criterio in ("proposito", "origen"):
            registro = copy.deepcopy(observado)
            if criterio == "proposito":
                registro["proposito"] = "prueba_unitaria"
            else:
                registro["funcionales"][0]["origen"] = "prueba_unitaria"
            with self.subTest(criterio=criterio):
                metricas = ev.calcular_metricas(registro, CASOS)
                self.assertEqual(metricas["funcionales_revisadas"], 0)
                self.assertEqual(metricas["funcionales_aprobadas"], 0)
        self.assertEqual(self.registro["funcionales"][0]["estado"], "no_ejecutado")

    def test_22_modelo_distinto_es_error_sin_metricas_de_calidad_ni_latencia(self):
        respuesta = {**self.respuesta_fixture(), "modelo": "modelo_distinto_fixture"}
        registro = self.ejecutar_fixture(responder=lambda **_: respuesta)
        fila = self.fila(registro)
        self.assertEqual(fila["estado"], "error")
        self.assertEqual(fila["turnos"], [])
        self.assertIsNone(fila["latencia_total_s"])
        self.assertIsNone(fila["revision"])
        metricas = ev.calcular_metricas(registro, CASOS)
        self.assertEqual(metricas["casos_con_error"], 1)
        self.assertEqual(metricas["casos_ejecutados_completos"], 0)
        self.assertEqual(metricas["casos_revisados"], 0)
        self.assertEqual(metricas["turnos_con_latencia"], 0)
        for campo in ("latencia_media_s", "latencia_p95_s", "fidelidad_pct", "citas_correctas_pct"):
            self.assertIsNone(metricas[campo])
        self.assertEqual(self.fila(self.registro)["estado"], "no_ejecutado")

    def test_23_no_mezcla_mediciones_manuales_y_adaptador(self):
        desde_adaptador = self.ejecutar_fixture(ids=("C01",))
        turno_c02 = {
            **self.respuesta_fixture(),
            "pregunta": CASOS[1]["turnos"][0],
            "latencia_s": 1.0,
        }
        anterior = copy.deepcopy(desde_adaptador)
        with self.assertRaises(ValueError):
            ev.registrar_manual(
                desde_adaptador, CASOS, self.catalogo, "C02", [turno_c02],
                self.config, "evidencia_fixture", confirmar_real=True,
            )
        self.assertEqual(desde_adaptador, anterior)

        turno_c01 = {
            **self.respuesta_fixture(),
            "pregunta": CASOS[0]["turnos"][0],
            "latencia_s": 1.0,
        }
        desde_manual = ev.registrar_manual(
            self.registro, CASOS, self.catalogo, "C01", [turno_c01],
            self.config, "evidencia_fixture", confirmar_real=True,
        )
        self.llamadas.clear()
        anterior = copy.deepcopy(desde_manual)
        with self.assertRaises(ValueError):
            self.ejecutar_fixture(ids=("C02",), registro=desde_manual)
        self.assertEqual(self.llamadas, [])
        self.assertEqual(desde_manual, anterior)
        self.assertNotEqual(
            desde_adaptador["config_ejecucion"]["metodo_medicion"],
            desde_manual["config_ejecucion"]["metodo_medicion"],
        )

    def test_24_cierre_bloquea_conexiones_ausentes_o_falsas(self):
        for campos in (
            {},
            {"qdrant_conexion_real_verificada": False, "llm_conexion_real_verificada": False},
        ):
            with self.subTest(campos=campos):
                pendientes = ev.pendientes_cierre(self.registro, {**self.config, **campos}, CASOS)
                self.assertEqual(sum(p.startswith("Conectividad Qdrant:") for p in pendientes), 1)
                self.assertEqual(sum(p.startswith("Conectividad LLM:") for p in pendientes), 1)

    def test_25_conexion_verificada_no_acredita_la_otra(self):
        for campo, prefijo_ok, prefijo_pendiente in (
            ("qdrant_conexion_real_verificada", "Conectividad Qdrant:", "Conectividad LLM:"),
            ("llm_conexion_real_verificada", "Conectividad LLM:", "Conectividad Qdrant:"),
        ):
            with self.subTest(campo=campo):
                pendientes = ev.pendientes_cierre(self.registro, {**self.config, campo: True}, CASOS)
                self.assertFalse(any(p.startswith(prefijo_ok) for p in pendientes))
                self.assertTrue(any(p.startswith(prefijo_pendiente) for p in pendientes))

    def test_26_conectividad_requiere_booleano_true_explicito(self):
        for valor in (None, "true", "False", 1, [], {}):
            with self.subTest(valor=repr(valor)):
                config = {**self.config, "qdrant_conexion_real_verificada": valor,
                          "llm_conexion_real_verificada": valor}
                pendientes = ev.pendientes_cierre(self.registro, config, CASOS)
                self.assertTrue(any(p.startswith("Conectividad Qdrant:") for p in pendientes))
                self.assertTrue(any(p.startswith("Conectividad LLM:") for p in pendientes))

    def test_27_conexiones_ok_preservan_pendientes_y_no_mutan_evidencia(self):
        antes = ev.pendientes_cierre(self.registro, self.config, CASOS)
        config = {**self.config, "qdrant_conexion_real_verificada": True,
                  "llm_conexion_real_verificada": True}
        registro_original, config_original = copy.deepcopy(self.registro), copy.deepcopy(config)
        despues = ev.pendientes_cierre(self.registro, config, CASOS)
        self.assertEqual(despues, [p for p in antes if not p.startswith("Conectividad ")])
        self.assertTrue(any(p.startswith("Evaluación:") for p in despues))
        self.assertEqual(self.registro, registro_original)
        self.assertEqual(config, config_original)
        self.assertEqual(self.llamadas, [])

    def test_28_destino_propio_exige_publicacion_y_corpus_cloud(self):
        config = {**self.config, "destino_qdrant": "propio",
                  "qdrant_conexion_real_verificada": True}
        registro_antes, config_antes = copy.deepcopy(self.registro), copy.deepcopy(config)
        pendientes = ev.pendientes_cierre(self.registro, config, CASOS)
        qdrant = [p for p in pendientes if p.startswith("Conectividad Qdrant:")]
        self.assertEqual(len(qdrant), 2)
        self.assertTrue(any("preparación local" in p for p in qdrant))
        self.assertTrue(any("correspondencia del corpus" in p for p in qdrant))
        self.assertEqual(self.registro, registro_antes)
        self.assertEqual(config, config_antes)

    def test_29_publicacion_y_corpus_propios_son_independientes_y_booleanos(self):
        base = {**self.config, "destino_qdrant": "propio",
                "qdrant_conexion_real_verificada": True,
                "base_propia_publicada": True, "corpus_cloud_verificado": True}
        for campo, texto in (("base_propia_publicada", "publicar y verificar"),
                             ("corpus_cloud_verificado", "correspondencia del corpus")):
            for valor in (None, False, "true", 1, [], {}):
                with self.subTest(campo=campo, valor=repr(valor)):
                    pendientes = ev.pendientes_cierre(self.registro, {**base, campo: valor}, CASOS)
                    qdrant = [p for p in pendientes if p.startswith("Conectividad Qdrant:")]
                    self.assertEqual(len(qdrant), 1)
                    self.assertIn(texto, qdrant[0])

    def test_30_cloud_propio_completo_no_suprime_evaluacion_pendiente(self):
        config = {**self.config, "destino_qdrant": "propio",
                  "qdrant_conexion_real_verificada": True,
                  "base_propia_publicada": True, "corpus_cloud_verificado": True}
        pendientes = ev.pendientes_cierre(self.registro, config, CASOS)
        self.assertFalse(any(p.startswith("Conectividad Qdrant:") for p in pendientes))
        self.assertTrue(any(p.startswith("Evaluación:") for p in pendientes))

    def test_31_heredado_no_exige_banderas_de_reconstruccion_propia(self):
        for destino in (None, "heredado"):
            with self.subTest(destino=destino):
                config = {**self.config, "destino_qdrant": destino,
                          "qdrant_conexion_real_verificada": True}
                pendientes = ev.pendientes_cierre(self.registro, config, CASOS)
                self.assertFalse(any(p.startswith("Conectividad Qdrant:") for p in pendientes))

    def test_32_exportacion_borrador_sin_ejecuciones_no_requiere_snapshot(self):
        antes = copy.deepcopy(self.registro)
        self.assertTrue(ev.validar_coherencia_exportacion(self.registro, {}))
        self.assertEqual(self.registro, antes)
        self.assertEqual(self.llamadas, [])

    def test_33_exportacion_config_identica_o_solo_editorial_no_muta(self):
        registro = self.ejecutar_fixture()
        config = {**self.config, "autores_confirmados": True,
                  "captura_chat": "captura_fixture.png", "base_propia_publicada": True}
        registro_antes, config_antes = copy.deepcopy(registro), copy.deepcopy(config)
        self.assertTrue(ev.validar_coherencia_exportacion(registro, config))
        self.assertEqual(registro, registro_antes)
        self.assertEqual(config, config_antes)

    def test_34_exportacion_rechaza_todos_los_cambios_de_snapshot(self):
        registro = self.ejecutar_fixture()
        original = copy.deepcopy(registro)
        # Todas las claves técnicas congeladas se comprueban, aunque la
        # corrida ya tenga casos que el bucle de ejecución vaya a conservar.
        for campo in ev._config_congelada(self.config):
            with self.subTest(campo=campo):
                config = {**self.config, campo: "valor_distinto_fixture"}
                with self.assertRaises(ValueError):
                    ev.validar_coherencia_exportacion(registro, config)
                self.assertEqual(registro, original)

    def test_35_exportacion_rechaza_actividad_sin_snapshot(self):
        con_caso = self.ejecutar_fixture()
        con_caso["config_ejecucion"] = None
        con_control = ev.registrar_funcional(
            self.registro, "F01", cumple=True,
            evidencia="evidencia_fixture", revisor="revisor_fixture")
        for registro in (con_caso, con_control):
            with self.subTest(tipo="caso" if registro["casos"][0]["turnos"] else "control"):
                original = copy.deepcopy(registro)
                with self.assertRaises(ValueError):
                    ev.validar_coherencia_exportacion(registro, self.config)
                self.assertEqual(registro, original)

    def test_36_exportacion_rechaza_snapshot_malformado_o_fila_ajena(self):
        for cambio in ("snapshot_malformado", "fila_config_ajena"):
            registro = self.ejecutar_fixture()
            if cambio == "snapshot_malformado":
                registro["config_ejecucion"] = ["fixture"]
            else:
                self.fila(registro)["config_ejecucion"]["modelo_llm"] = "otro_fixture"
            original = copy.deepcopy(registro)
            with self.subTest(cambio=cambio), self.assertRaises(ValueError):
                ev.validar_coherencia_exportacion(registro, self.config)
            self.assertEqual(registro, original)

    def test_37_exportacion_error_seguro_sin_imprimir_valores(self):
        registro = self.ejecutar_fixture()
        valor = "valor_privado_sintetico_que_no_debe_aparecer"
        with self.assertRaises(ValueError) as error:
            ev.validar_coherencia_exportacion(registro, {**self.config, "modelo_llm": valor})
        self.assertNotIn(valor, str(error.exception))

    def test_38_exportacion_acepta_claves_opcionales_historicas_ausentes(self):
        registro = self.ejecutar_fixture()
        for snapshot in (registro["config_ejecucion"], self.fila(registro)["config_ejecucion"]):
            for campo in list(snapshot):
                if snapshot[campo] is None:
                    del snapshot[campo]
        self.assertTrue(ev.validar_coherencia_exportacion(registro, self.config))
        with self.assertRaises(ValueError):
            ev.validar_coherencia_exportacion(registro, {**self.config, "destino_qdrant": "propio"})

    def test_39_revision_embeddings_distinta_exige_corrida_nueva(self):
        config = {**self.config, "modelo_embeddings_revision": "a" * 40}
        registro = self.ejecutar_fixture(config=config)
        diferente = {**config, "modelo_embeddings_revision": "b" * 40}
        original = copy.deepcopy(registro)
        self.assertTrue(ev.validar_coherencia_exportacion(registro, config))
        with self.assertRaises(ValueError):
            self.ejecutar_fixture(ids=("C02",), registro=registro, config=diferente)
        with self.assertRaises(ValueError):
            ev.validar_coherencia_exportacion(registro, diferente)
        self.assertEqual(registro, original)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EvaluacionACA2Tests)
    resultado = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    print(
        f"Pruebas unitarias: {resultado.testsRun}; "
        f"resultado: {'OK' if resultado.wasSuccessful() else 'FALLO'}; "
        f"fallos: {len(resultado.failures)}; errores: {len(resultado.errors)}."
    )
    raise SystemExit(0 if resultado.wasSuccessful() else 1)
