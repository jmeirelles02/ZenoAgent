"""Síntese e reconhecimento de voz (TTS via edge-tts, STT via Faster-Whisper).

O Faster-Whisper processa localmente com pontuação automática e
precisão superior ao Vosk, usando o modelo 'base' (~150MB, int8).
Fallback para Google Speech Recognition se Faster-Whisper não estiver disponível.
"""

import logging
import os
import re
import subprocess
import tempfile
import wave

try:
    import keyboard
    HAS_KEYBOARD = True
except ImportError:
    HAS_KEYBOARD = False
except Exception:
    HAS_KEYBOARD = False

import pygame

from src.config import (
    ARQUIVO_AUDIO_TEMP,
    DURACAO_AJUSTE_RUIDO,
    FASTER_WHISPER_MODELO,
    PAUSA_RECONHECIMENTO,
    TIMEOUT_ESCUTA,
    VOZ_PADRAO,
)
from src.state import estado

logger = logging.getLogger(__name__)

# ── Inicialização do Faster-Whisper (lazy) ──
_whisper_model = None
_whisper_disponivel = False


def _inicializar_whisper():
    """Carrega o modelo Faster-Whisper sob demanda."""
    global _whisper_model, _whisper_disponivel
    if _whisper_model is not None:
        return _whisper_disponivel

    try:
        from faster_whisper import WhisperModel

        logger.info(
            "Carregando Faster-Whisper (modelo: %s, compute: int8)...",
            FASTER_WHISPER_MODELO,
        )
        _whisper_model = WhisperModel(
            FASTER_WHISPER_MODELO,
            device="cpu",
            compute_type="int8",
        )
        _whisper_disponivel = True
        logger.info("Faster-Whisper carregado com sucesso.")
    except ImportError:
        logger.warning(
            "faster-whisper não instalado. Usando Google Speech como fallback."
        )
        _whisper_disponivel = False
    except Exception as e:
        logger.warning("Falha ao carregar Faster-Whisper: %s. Usando fallback.", e)
        _whisper_disponivel = False

    return _whisper_disponivel


def limpar_texto_para_fala(texto: str) -> str:
    """Remove formatação markdown e artefatos de tool calling do texto."""
    # Remove blocos de código
    texto_limpo = re.sub(r"```.*?```", "", texto, flags=re.DOTALL)
    # Remove formatação markdown inline
    texto_limpo = re.sub(r"[*#_`]", "", texto_limpo)
    # Remove emojis comuns de ferramenta
    texto_limpo = re.sub(r"[⚡🔔🚫⚠️├└─]", "", texto_limpo)
    # Remove linhas vazias excessivas
    texto_limpo = re.sub(r"\n{3,}", "\n\n", texto_limpo)
    return texto_limpo.strip()


def falar(texto: str) -> None:
    """Converte texto em fala usando edge-tts e reproduz via pygame."""
    texto_limpo = limpar_texto_para_fala(texto)
    if not texto_limpo.strip():
        return

    estado.atualizar(status="FALANDO...")

    try:
        subprocess.run(
            [
                "edge-tts",
                "--voice", VOZ_PADRAO,
                "--text", texto_limpo,
                "--write-media", ARQUIVO_AUDIO_TEMP,
            ],
            check=True,
        )
        pygame.mixer.music.load(ARQUIVO_AUDIO_TEMP)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            if HAS_KEYBOARD:
                try:
                    if keyboard.is_pressed("space"):
                        pygame.mixer.music.stop()
                        print("\n[A.R.I.S interrompido]")
                        break
                except Exception:
                    pass
            pygame.time.Clock().tick(10)

        pygame.mixer.music.unload()
        if os.path.exists(ARQUIVO_AUDIO_TEMP):
            os.remove(ARQUIVO_AUDIO_TEMP)
    except FileNotFoundError:
        logger.error("edge-tts não encontrado. Verifique a instalação.")
    except pygame.error as e:
        logger.error("Erro do pygame ao reproduzir áudio: %s", e)
    except Exception as e:
        logger.error("Erro de áudio: %s", e)


def _gravar_audio_microfone(duracao_max: int = 10) -> str | None:
    """Grava áudio do microfone via PyAudio e salva como WAV temporário.

    Returns:
        Caminho do arquivo WAV ou None se falhar.
    """
    try:
        import pyaudio

        RATE = 16000
        CHANNELS = 1
        FORMAT = pyaudio.paInt16
        CHUNK = 1024

        pa = pyaudio.PyAudio()
        stream = pa.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
        )

        estado.atualizar(status="OUVINDO...")
        print("\n[A.R.I.S ouvindo (Faster-Whisper)...]")

        frames = []
        # Gravar por duracao_max segundos ou até silêncio
        for _ in range(0, int(RATE / CHUNK * duracao_max)):
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)

        stream.stop_stream()
        stream.close()
        pa.terminate()

        # Salvar como WAV temporário
        temp_path = os.path.join(tempfile.gettempdir(), "aris_mic.wav")
        with wave.open(temp_path, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(pa.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b"".join(frames))

        return temp_path
    except Exception as e:
        logger.error("Erro ao gravar áudio do microfone: %s", e)
        return None


def _transcrever_whisper(caminho_audio: str) -> str:
    """Transcreve áudio usando Faster-Whisper com pontuação automática."""
    if _whisper_model is None:
        return ""

    try:
        segmentos, info = _whisper_model.transcribe(
            caminho_audio,
            language="pt",
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        texto = " ".join(seg.text.strip() for seg in segmentos)
        logger.info(
            "Whisper transcreveu: '%s' (idioma: %s, prob: %.2f)",
            texto,
            info.language,
            info.language_probability,
        )
        return texto.strip()
    except Exception as e:
        logger.error("Erro na transcrição Faster-Whisper: %s", e)
        return ""
    finally:
        # Limpar arquivo temporário
        if os.path.exists(caminho_audio):
            try:
                os.remove(caminho_audio)
            except OSError:
                pass


def _ouvir_google_fallback() -> str:
    """Fallback: captura áudio via SpeechRecognition + Google Speech API."""
    try:
        import speech_recognition as sr

        reconhecedor = sr.Recognizer()
        reconhecedor.pause_threshold = PAUSA_RECONHECIMENTO
        with sr.Microphone() as fonte:
            estado.atualizar(status="OUVINDO...")
            print("\n[A.R.I.S ouvindo (Google Speech)...]")
            reconhecedor.adjust_for_ambient_noise(
                fonte, duration=DURACAO_AJUSTE_RUIDO
            )
            audio = reconhecedor.listen(fonte, timeout=TIMEOUT_ESCUTA)
            texto = reconhecedor.recognize_google(audio, language="pt-BR")
            return texto
    except Exception as e:
        logger.warning("Erro no reconhecimento Google Speech: %s", e)
        return ""


def ouvir() -> str:
    """Captura áudio do microfone e transcreve para texto.

    Prioridade:
    1. Faster-Whisper (local, com pontuação)
    2. Google Speech Recognition (fallback online)
    """
    # Tentar Faster-Whisper primeiro
    if _inicializar_whisper():
        caminho = _gravar_audio_microfone(duracao_max=TIMEOUT_ESCUTA)
        if caminho:
            texto = _transcrever_whisper(caminho)
            if texto:
                print(f"Você (Voz/Whisper): {texto}")
                return texto

        # Se Whisper falhou, tentar fallback
        logger.warning("Faster-Whisper sem resultado. Tentando Google Speech...")

    # Fallback Google Speech
    texto = _ouvir_google_fallback()
    if texto:
        print(f"Você (Voz/Google): {texto}")
    return texto
