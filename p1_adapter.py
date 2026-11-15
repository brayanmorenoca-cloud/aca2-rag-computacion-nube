"""Adaptador del pipeline REAL para la batería académica de evaluación.

No incluye respuestas prefabricadas. El singleton solo contiene clientes/modelo
de embeddings; el historial siempre lo aporta el llamante, aislado por sesión.
Importar no conecta servicios. Configurar secretos antes de la primera llamada.
"""
from rag_backend import Config, RagService

_servicio = None


def configurar(servicio=None):
    """Inyectar el servicio de la UI/notebook o volver a leer el entorno."""
    global _servicio
    _servicio = servicio or RagService(Config.from_env())
    return _servicio


def responder(pregunta, historial=None, top_k=3):
    """Contrato P2: llamada real al modelo + citas emitidas + contexto entregado."""
    global _servicio
    if _servicio is None:
        _servicio = RagService(Config.from_env())
    return _servicio.responder(pregunta=pregunta, historial=historial, top_k=top_k)
