"""Generación local segura; sin llamadas a LLM ni servicios remotos."""
from pathlib import Path
from banco_pruebas import CASOS, FUNCIONALES
from evaluacion_aca2 import cargar_json, inicializar_registro, validar_banco
from materiales_aca2 import generar_todo

if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    config = cargar_json(base / "config_proyecto.json")
    corpus = cargar_json(base / "corpus_fuente.json")
    print(validar_banco(CASOS, FUNCIONALES, corpus))
    registro = inicializar_registro(base / "datos" / "corrida_01.json", CASOS, FUNCIONALES)
    resultado = generar_todo(base, config, registro, corpus)
    print("Materiales generados. Póster:", resultado["poster"])
    print("Casos reales completos:", resultado["metricas"]["casos_ejecutados_completos"])
    print("Pendientes verificables:", len(resultado["pendientes"]))
