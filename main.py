"""Ponto de entrada do ZenoAgent."""

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pygame")

import logging
import queue
import sys
import threading

import pygame

from src.api import fila_comandos, rodar_servidor
from src.config import COMANDOS_SAIDA, GATILHOS_PESQUISA
from src.database import buscar_memoria_relevante, inicializar_banco
from src.llm import criar_sessao_chat
from src.search import buscar_na_internet
from src.speech import falar, ouvir
from src.state import estado
from src.tags import limpar_texto_para_fala, processar_tags_ocultas
from src.utils import obter_caminho_desktop
from src.wakeword import DetectorWakeWord

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("zeno_audit.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def iniciar_servidor_api() -> None:
    """Inicia o servidor FastAPI em uma thread daemon."""
    thread = threading.Thread(target=rodar_servidor, daemon=True)
    thread.start()


def aguardar_entrada() -> str | None:
    """Aguarda um comando da fila com timeout de 1 segundo."""
    try:
        return fila_comandos.get(timeout=1.0)
    except queue.Empty:
        return None


def resolver_entrada(entrada: str) -> str | None:
    """Resolve a entrada: comando de voz ou texto direto."""
    if entrada == "[VOZ]":
        pergunta = ouvir()
        return pergunta if pergunta else None
    return entrada


def enriquecer_pergunta(pergunta: str) -> str:
    """Adiciona contexto web e memória à pergunta do usuário."""
    dados_web = ""
    if any(g in pergunta.lower() for g in GATILHOS_PESQUISA):
        estado.atualizar(status="BUSCANDO NA REDE...")
        dados_web = buscar_na_internet(pergunta)

    estado.atualizar(status="RECUPERANDO DADOS...")
    contexto_memoria = buscar_memoria_relevante(pergunta)

    pergunta_formatada = pergunta

    if dados_web:
        pergunta_formatada = (
            f"Resultados da web:\n{dados_web}\n\n"
            f"Pergunta: {pergunta_formatada}\n"
            f"Instrução: Responda de forma direta usando APENAS os dados da web. "
            f"NUNCA invente valores."
        )

    if contexto_memoria:
        pergunta_formatada = (
            f"Contexto salvo no banco de dados (use apenas se for relevante):\n"
            f"{contexto_memoria}\n\n{pergunta_formatada}"
        )

    return pergunta_formatada


def processar_resposta_streaming(chat, pergunta_formatada: str) -> str:
    """Envia pergunta ao LLM e imprime a resposta em streaming."""
    estado.atualizar(status="PENSANDO...")

    texto_completo = ""
    print("Zeno: ", end="")
    for texto_chunk in chat.enviar_mensagem_stream(pergunta_formatada):
        print(texto_chunk, end="", flush=True)
        texto_completo += texto_chunk
    print()

    return texto_completo


detector_ww: DetectorWakeWord | None = None


def loop_principal(chat) -> None:
    """Loop principal de interação com o usuário."""
    global detector_ww
    usuario_db = "Sistema"

    while True:
        try:
            estado.atualizar(status="ONLINE")
            if detector_ww:
                detector_ww.retomar()

            entrada = aguardar_entrada()
            if not entrada:
                continue

            if detector_ww:
                detector_ww.pausar()

            if entrada.lower() in COMANDOS_SAIDA:
                estado.atualizar(status="DESLIGANDO...")
                falar("Encerrando protocolos. Ate a proxima, senhor.")
                break

            pergunta = resolver_entrada(entrada)
            if not pergunta:
                continue

            estado.atualizar(usuario=pergunta)
            estado.adicionar_mensagem("usuario", pergunta)

            pergunta_formatada = enriquecer_pergunta(pergunta)
            texto_resposta = processar_resposta_streaming(chat, pergunta_formatada)

            texto_limpo = limpar_texto_para_fala(texto_resposta)
            estado.atualizar(zeno=texto_limpo)
            estado.adicionar_mensagem("zeno", texto_limpo)

            processar_tags_ocultas(texto_resposta, usuario_db, callback_falar=falar)
            falar(texto_resposta)

        except KeyboardInterrupt:
            sys.exit()
        except Exception as e:
            logger.error("Ocorreu um erro: %s", e)


def iniciar_zeno_core() -> None:
    """Inicializa todos os subsistemas e inicia o loop principal."""
    global detector_ww
    pygame.mixer.init()

    print("==================================================")
    print("Zeno System Iniciado. Conectado ao Ollama (local).")
    print("==================================================")

    inicializar_banco()
    iniciar_servidor_api()

    try:
        detector_ww = DetectorWakeWord(fila_comandos)
        detector_ww.iniciar()
    except Exception as e:
        logger.warning("Wake word indisponível: %s", e)

    caminho_desktop = obter_caminho_desktop()
    chat = criar_sessao_chat(caminho_desktop, usuario="Sistema")

    loop_principal(chat)


if __name__ == "__main__":
    iniciar_zeno_core()