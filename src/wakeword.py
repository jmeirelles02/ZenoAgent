"""Detecção de wake word offline usando Vosk (Apache 2.0)."""

import json
import logging
import queue
import threading
import time

import pyaudio
from vosk import Model, KaldiRecognizer, SetLogLevel

logger = logging.getLogger(__name__)

WAKE_WORDS: list[str] = ["zeno", "zero", "xeno", "zen", "zena", "zino"]
CAMINHO_MODELO: str = "vosk-model-small-pt-0.3"
TAXA_AMOSTRAGEM: int = 16000
TAMANHO_BLOCO: int = 8000


def _contem_wake_word(texto: str) -> bool:
    """Verifica se o texto contém alguma variação da wake word."""
    texto_lower = texto.lower().strip()
    return any(w in texto_lower for w in WAKE_WORDS)


class DetectorWakeWord:
    """Escuta continuamente o microfone em busca da wake word via Vosk."""

    def __init__(self, fila_comandos: queue.Queue[str]):
        self.fila = fila_comandos
        self.ativo = True
        self.pausado = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        SetLogLevel(-1)
        self.modelo = Model(CAMINHO_MODELO)

    def iniciar(self) -> None:
        """Inicia a escuta da wake word em uma thread daemon."""
        self._thread = threading.Thread(target=self._loop_escuta, daemon=True)
        self._thread.start()
        logger.info("Wake word ativada (Vosk offline). Variações: %s", WAKE_WORDS)

    def pausar(self) -> None:
        """Pausa a escuta e libera o microfone."""
        with self._lock:
            self.pausado = True

    def retomar(self) -> None:
        """Retoma a escuta."""
        with self._lock:
            self.pausado = False

    def parar(self) -> None:
        """Para a escuta permanentemente."""
        self.ativo = False

    def _loop_escuta(self) -> None:
        """Loop principal de escuta contínua com Vosk."""
        while self.ativo:
            if self.pausado:
                time.sleep(0.3)
                continue

            try:
                self._escutar_ciclo()
            except Exception as e:
                logger.warning("Erro na wake word: %s", e)
                time.sleep(2)

    def _escutar_ciclo(self) -> None:
        """Abre o microfone, escuta até detectar a wake word ou ser pausado."""
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=TAXA_AMOSTRAGEM,
            input=True,
            frames_per_buffer=TAMANHO_BLOCO,
        )
        reconhecedor = KaldiRecognizer(self.modelo, TAXA_AMOSTRAGEM)

        try:
            while self.ativo and not self.pausado:
                dados = stream.read(TAMANHO_BLOCO, exception_on_overflow=False)

                if reconhecedor.AcceptWaveform(dados):
                    resultado = json.loads(reconhecedor.Result())
                    texto = resultado.get("text", "")
                    if texto:
                        logger.debug("Vosk ouviu: '%s'", texto)
                    if _contem_wake_word(texto):
                        logger.info("Wake word detectada: '%s'", texto)
                        print(f"\n[Wake word detectada: '{texto}']")
                        self.fila.put("[VOZ]")
                        break
                else:
                    parcial = json.loads(reconhecedor.PartialResult())
                    texto_parcial = parcial.get("partial", "")
                    if _contem_wake_word(texto_parcial):
                        logger.info("Wake word detectada (parcial): '%s'", texto_parcial)
                        print(f"\n[Wake word detectada: '{texto_parcial}']")
                        self.fila.put("[VOZ]")
                        break
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()
