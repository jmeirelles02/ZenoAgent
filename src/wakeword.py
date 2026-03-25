"""Detecção de wake word offline usando Vosk (Apache 2.0)."""

import json
import logging
import queue
import threading
import time

import pyaudio
from vosk import Model, KaldiRecognizer, SetLogLevel

logger = logging.getLogger(__name__)

WAKE_WORD: str = "zeno"
CAMINHO_MODELO: str = "vosk-model-small-pt-0.3"
TAXA_AMOSTRAGEM: int = 16000
TAMANHO_BLOCO: int = 4000


class DetectorWakeWord:
    """Escuta continuamente o microfone em busca da wake word via Vosk."""

    def __init__(self, fila_comandos: queue.Queue[str]):
        self.fila = fila_comandos
        self.ativo = True
        self.pausado = False
        self._thread: threading.Thread | None = None

        SetLogLevel(-1)
        self.modelo = Model(CAMINHO_MODELO)

    def iniciar(self) -> None:
        """Inicia a escuta da wake word em uma thread daemon."""
        self._thread = threading.Thread(target=self._loop_escuta, daemon=True)
        self._thread.start()
        logger.info("Wake word '%s' ativada (Vosk offline).", WAKE_WORD)

    def pausar(self) -> None:
        """Pausa a escuta (enquanto Zeno processa ou fala)."""
        self.pausado = True

    def retomar(self) -> None:
        """Retoma a escuta."""
        self.pausado = False

    def parar(self) -> None:
        """Para a escuta permanentemente."""
        self.ativo = False

    def _loop_escuta(self) -> None:
        """Loop principal de escuta contínua com Vosk."""
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
            while self.ativo:
                if self.pausado:
                    time.sleep(0.1)
                    continue

                dados = stream.read(TAMANHO_BLOCO, exception_on_overflow=False)

                if reconhecedor.AcceptWaveform(dados):
                    resultado = json.loads(reconhecedor.Result())
                    texto = resultado.get("text", "")
                    if WAKE_WORD in texto.lower():
                        logger.info("Wake word detectada: '%s'", texto)
                        print(f"\n[Wake word detectada: '{texto}']")
                        self.fila.put("[VOZ]")
                        time.sleep(1.5)
                        reconhecedor.Reset()
                else:
                    parcial = json.loads(reconhecedor.PartialResult())
                    texto_parcial = parcial.get("partial", "")
                    if WAKE_WORD in texto_parcial.lower():
                        logger.info("Wake word detectada (parcial): '%s'", texto_parcial)
                        print(f"\n[Wake word detectada: '{texto_parcial}']")
                        self.fila.put("[VOZ]")
                        time.sleep(1.5)
                        reconhecedor.Reset()
        except Exception as e:
            logger.error("Erro na wake word: %s", e)
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()
