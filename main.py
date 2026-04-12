"""Ponto de entrada do A.R.I.S Agent — v2.0 (Native Tool Calling).

Fluxo unificado:
  Entrada (Voz/Texto) → Enriquecimento (Web/RAG) → LLM (Tools) → Resultado → Saída (Voz/UI)
"""

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pygame")

import logging
import queue
import sys
import threading

import pygame

from src.api import fila_comandos, fila_multimodal, rodar_servidor
from src.config import GATILHOS_PESQUISA, GATILHOS_VISAO
from src.database import buscar_memoria_relevante, inicializar_banco
from src.llm import criar_sessao_chat, processar_requisicao_multimodal
from src.observer import Observador
from src.search import buscar_na_internet
from src.speech import falar, limpar_texto_para_fala, ouvir
from src.state import estado
from src.utils import obter_caminho_desktop
from src.vision import capturar_tela_base64
from src.wakeword import DetectorWakeWord

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("aris_audit.log", encoding="utf-8"),
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


def verificar_fila_multimodal() -> dict | None:
    """Verifica se há requisições multimodais pendentes (non-blocking)."""
    try:
        return fila_multimodal.get_nowait()
    except queue.Empty:
        return None


def resolver_entrada(entrada: str) -> str | None:
    """Resolve a entrada: comando de voz ou texto direto."""
    if entrada == "[VOZ]":
        pergunta = ouvir()
        return pergunta if pergunta else None
    return entrada


def detectar_intencao_visao(texto: str) -> bool:
    """Verifica se o texto do usuário indica intenção de análise visual."""
    texto_lower = texto.lower()
    return any(gatilho in texto_lower for gatilho in GATILHOS_VISAO)


def processar_com_visao(pergunta: str) -> None:
    """Captura a tela e processa pelo pipeline multimodal (Moondream → Qwen).

    Args:
        pergunta: Texto original do usuário.
    """
    estado.atualizar(usuario=pergunta)
    estado.adicionar_mensagem("usuario", pergunta)

    estado.atualizar(status="CAPTURANDO TELA...")
    logger.info("Intenção de visão detectada. Capturando tela...")
    imagem_b64 = capturar_tela_base64()

    if imagem_b64 is None:
        msg_erro = (
            "Não consegui capturar a tela. "
            "Verifique se scrot ou gnome-screenshot está instalado."
        )
        logger.error(msg_erro)
        estado.atualizar(status="ONLINE", aris=msg_erro)
        estado.adicionar_mensagem("aris", msg_erro)
        falar(msg_erro)
        return

    logger.info(
        "Tela capturada (%d chars B64). Enviando para pipeline multimodal...",
        len(imagem_b64),
    )

    dados_multimodal = {"comando": pergunta, "imagem": imagem_b64}
    processar_requisicao_visual(dados_multimodal)


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
    """Envia pergunta ao LLM com Tool Calling e imprime a resposta em streaming."""
    estado.atualizar(status="PENSANDO...")

    texto_completo = ""
    print("A.R.I.S: ", end="")
    for texto_chunk in chat.enviar_mensagem_stream(pergunta_formatada):
        print(texto_chunk, end="", flush=True)
        texto_completo += texto_chunk
    print()

    return texto_completo


def processar_requisicao_visual(dados_multimodal: dict) -> None:
    """Processa uma requisição multimodal (com imagem) pelo pipeline dual-model."""
    comando = dados_multimodal["comando"]
    imagem = dados_multimodal.get("imagem")

    estado.atualizar(usuario=comando)
    estado.adicionar_mensagem("usuario", comando)

    modo = "ANALISANDO TELA..." if imagem else "PROCESSANDO..."
    estado.atualizar(status=modo)
    logger.info(
        "Pipeline multimodal iniciado (imagem: %s).",
        "SIM" if imagem else "NÃO",
    )

    resultado = processar_requisicao_multimodal(
        texto_usuario=comando,
        imagem_base64=imagem,
    )

    texto_resposta = resultado.get("response", "Sem resposta do modelo.")
    acao = resultado.get("action", {})

    print(f"\nA.R.I.S [MULTIMODAL]: {texto_resposta}")
    logger.info(
        "Resposta multimodal — Ação: %s | Confiança: %.2f",
        acao.get("type", "NONE"),
        acao.get("confidence", 0.0),
    )

    estado.atualizar(status="ONLINE", aris=texto_resposta)
    estado.adicionar_mensagem("aris", texto_resposta)
    falar(texto_resposta)


detector_ww: DetectorWakeWord | None = None
observador: Observador | None = None


def loop_principal(chat) -> None:
    """Loop principal de interação com o usuário.

    Fluxo unificado:
      1. Verificar filas (multimodal → convencional)
      2. Resolver entrada (voz ou texto)
      3. Detectar intenção de visão
      4. Enriquecer pergunta (web + RAG)
      5. LLM com Tool Calling (ferramentas executadas automaticamente)
      6. Saída (voz + UI)
    """
    global detector_ww, observador

    while True:
        try:
            estado.atualizar(status="ONLINE")
            if detector_ww:
                detector_ww.retomar()
            if observador:
                observador.retomar()

            # ── Prioridade 1: Requisições multimodais (com imagem) ──
            dados_multimodal = verificar_fila_multimodal()
            if dados_multimodal:
                if detector_ww:
                    detector_ww.pausar()
                if observador:
                    observador.pausar()
                processar_requisicao_visual(dados_multimodal)
                continue

            # ── Prioridade 2: Comandos convencionais (texto/voz) ──
            entrada = aguardar_entrada()
            if not entrada:
                continue

            if detector_ww:
                detector_ww.pausar()
            if observador:
                observador.pausar()

            pergunta = resolver_entrada(entrada)
            if not pergunta:
                continue

            # ── Verificar intenção de visão (tela/screenshot) ──
            if detectar_intencao_visao(pergunta):
                logger.info("Gatilho de visão detectado em: '%s'", pergunta)
                processar_com_visao(pergunta)
                continue

            # ── Fluxo convencional: Texto → LLM (Tools) → Resposta ──
            estado.atualizar(usuario=pergunta)
            estado.adicionar_mensagem("usuario", pergunta)

            pergunta_formatada = enriquecer_pergunta(pergunta)
            texto_resposta = processar_resposta_streaming(chat, pergunta_formatada)

            texto_limpo = limpar_texto_para_fala(texto_resposta)
            estado.atualizar(aris=texto_limpo)
            estado.adicionar_mensagem("aris", texto_limpo)

            # Tool calling já executou as ações automaticamente.
            # Agora apenas falamos a resposta final do modelo.
            falar(texto_resposta)

        except KeyboardInterrupt:
            logger.info("Recebido KeyboardInterrupt. Encerrando...")
            break
        except Exception as e:
            logger.error("Ocorreu um erro: %s", e)

    if detector_ww:
        detector_ww.parar()
    if observador:
        observador.parar()


def iniciar_aris_core() -> None:
    """Inicializa todos os subsistemas e inicia o loop principal."""
    global detector_ww, observador
    pygame.mixer.init()

    # Importar todos os módulos com @aris_tool para popular o registro
    import src.commands  # noqa: F401
    import src.calendar_service  # noqa: F401
    import src.database  # noqa: F401
    import src.email_service  # noqa: F401
    import src.finance  # noqa: F401
    import src.media  # noqa: F401
    import src.search  # noqa: F401
    import src.weather  # noqa: F401

    from src.plugins import listar_ferramentas

    ferramentas = listar_ferramentas()

    print("══════════════════════════════════════════════════")
    print("  A.R.I.S v2.0 — Native Tool Calling")
    print("  Pipeline: Ollama + Faster-Whisper + Observer")
    print(f"  Ferramentas: {len(ferramentas)} registradas")
    print(f"  → {', '.join(ferramentas)}")
    print("  VRAM: keep_alive=0 (descarregamento dinâmico)")
    print("══════════════════════════════════════════════════")

    inicializar_banco()
    iniciar_servidor_api()

    import signal

    def lidar_com_sinal(sig, frame):
        logger.info("Sinal de encerramento recebido. Encerrando de forma graciosa...")
        if detector_ww:
            detector_ww.parar()
        if observador:
            observador.parar()
        sys.exit(0)

    signal.signal(signal.SIGINT, lidar_com_sinal)
    signal.signal(signal.SIGTERM, lidar_com_sinal)

    try:
        detector_ww = DetectorWakeWord(fila_comandos)
        detector_ww.iniciar()
    except Exception as e:
        logger.warning("Wake word indisponível: %s", e)

    # ── Iniciar Observador Proativo ──
    try:
        observador = Observador(callback_notificacao=falar)
        observador.iniciar()
    except Exception as e:
        logger.warning("Observador proativo indisponível: %s", e)

    caminho_desktop = obter_caminho_desktop()
    chat = criar_sessao_chat(caminho_desktop, usuario="Sistema")

    loop_principal(chat)


if __name__ == "__main__":
    iniciar_aris_core()