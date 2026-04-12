"""Observador proativo do A.R.I.S — Background Observer.

Roda uma thread em segundo plano que, a cada intervalo configurável,
coleta contexto do sistema (CPU, RAM, hora, agenda) e analisa se
há algo que justifique uma notificação proativa ao usuário.
"""

import logging
import threading
from datetime import datetime

import ollama

from src.config import MODELO_CHAT, OBSERVER_INTERVALO_MINUTOS
from src.state import estado
from src.system_monitor import obter_metricas_sistema

logger = logging.getLogger(__name__)

_PROMPT_OBSERVADOR = """Você é o módulo proativo do A.R.I.S. Sua tarefa é analisar o contexto do sistema do usuário e decidir se há algo relevante para notificá-lo.

REGRAS:
- Se NÃO houver nada relevante, responda EXATAMENTE: [NADA]
- Se houver algo relevante, responda com uma frase curta e direta (máx 2 linhas).
- Você NÃO pode executar ferramentas. Apenas sugerir ações ao usuário.
- Seja breve. Sem saudações. Sem floreios.
- Responda SEMPRE em português do Brasil.

Exemplos de notificações válidas:
- "Atenção: seu uso de RAM está em 92%. Considere fechar alguns programas."
- "Lembrete: você tem um compromisso em 30 minutos."
- "Dica: são 23h45, talvez seja hora de encerrar o trabalho."

Contexto atual do sistema:
{contexto}
"""


class Observador:
    """Thread de observação proativa em segundo plano."""

    def __init__(
        self,
        callback_notificacao: callable,
        intervalo_minutos: float = OBSERVER_INTERVALO_MINUTOS,
    ):
        """Inicializa o observador.

        Args:
            callback_notificacao: Função chamada quando há notificação
                                  (recebe str com o texto).
            intervalo_minutos: Intervalo entre análises.
        """
        self._callback = callback_notificacao
        self._intervalo = intervalo_minutos * 60  # Converter para segundos
        self._timer: threading.Timer | None = None
        self._ativo = False
        self._pausado = False
        self._lock = threading.Lock()

    def iniciar(self) -> None:
        """Inicia o loop de observação."""
        self._ativo = True
        self._pausado = False
        logger.info(
            "Observador proativo iniciado (intervalo: %.1f min).",
            self._intervalo / 60,
        )
        self._agendar_proxima()

    def pausar(self) -> None:
        """Pausa temporariamente (ex: enquanto o LLM está respondendo)."""
        with self._lock:
            self._pausado = True

    def retomar(self) -> None:
        """Retoma após pausa."""
        with self._lock:
            self._pausado = False

    def parar(self) -> None:
        """Encerra o observador permanentemente."""
        self._ativo = False
        if self._timer:
            self._timer.cancel()
            self._timer = None
        logger.info("Observador proativo encerrado.")

    def _agendar_proxima(self) -> None:
        """Agenda a próxima execução do ciclo de observação."""
        if not self._ativo:
            return
        self._timer = threading.Timer(self._intervalo, self._ciclo)
        self._timer.daemon = True
        self._timer.start()

    def _coletar_contexto(self) -> str:
        """Coleta contexto atual para análise."""
        agora = datetime.now()
        metricas = obter_metricas_sistema()

        linhas = [
            f"Data/Hora: {agora.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Dia da semana: {agora.strftime('%A')}",
            f"CPU: {metricas.get('cpu', '?')}%",
            f"RAM: {metricas.get('ram_usada', '?')}% "
            f"(de {metricas.get('ram_total_gb', '?')} GB)",
            f"Disco: {metricas.get('disco_usado', '?')}%",
        ]

        bat = metricas.get("bateria")
        if bat is not None:
            linhas.append(
                f"Bateria: {bat}% ({'carregando' if metricas.get('carregando') else 'na bateria'})"
            )

        # Status atual do ARIS
        linhas.append(f"Status do A.R.I.S: {estado.status}")

        return "\n".join(linhas)

    def _ciclo(self) -> None:
        """Executa um ciclo de observação."""
        try:
            with self._lock:
                if self._pausado:
                    logger.debug("Observador pausado — pulando ciclo.")
                    self._agendar_proxima()
                    return

            contexto = self._coletar_contexto()
            prompt = _PROMPT_OBSERVADOR.format(contexto=contexto)

            logger.debug("Observador analisando contexto...")

            resposta = ollama.chat(
                model=MODELO_CHAT,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.3, "num_predict": 150},
            )

            texto = resposta.message.content.strip()

            if texto and "[NADA]" not in texto.upper():
                logger.info("Observador proativo: %s", texto)
                estado.atualizar(aris=f"🔔 {texto}")
                estado.adicionar_mensagem("aris", f"[Proativo] {texto}")
                self._callback(texto)
            else:
                logger.debug("Observador: nada relevante no momento.")

        except Exception as e:
            logger.warning("Erro no ciclo do observador: %s", e)
        finally:
            self._agendar_proxima()
