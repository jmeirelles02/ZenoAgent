"""Estado global thread-safe do Zeno."""

from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from src.config import MAX_HISTORICO


@dataclass
class EstadoZeno:
    """Armazena o estado atual do assistente com acesso thread-safe."""

    _lock: Lock = field(default_factory=Lock, repr=False)
    status: str = "ONLINE"
    usuario: str = "Aguardando comando..."
    zeno: str = "Sistemas iniciados."
    historico: list[dict[str, str]] = field(default_factory=list)

    def atualizar(self, **kwargs: Any) -> None:
        with self._lock:
            for chave, valor in kwargs.items():
                if hasattr(self, chave) and chave != "_lock":
                    setattr(self, chave, valor)

    def adicionar_mensagem(self, papel: str, texto: str) -> None:
        """Adiciona uma mensagem ao histórico de conversa."""
        with self._lock:
            self.historico.append({"papel": papel, "texto": texto})
            if len(self.historico) > MAX_HISTORICO:
                self.historico = self.historico[-MAX_HISTORICO:]

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.status,
                "usuario": self.usuario,
                "zeno": self.zeno,
                "historico": list(self.historico),
            }


estado = EstadoZeno()
