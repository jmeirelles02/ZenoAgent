"""Cliente Ollama com gestão dinâmica de VRAM para pipeline dual-model.

REGRA CRÍTICA: Os modelos de visão (Moondream ~2GB) e lógica (Qwen ~5GB)
estão PROIBIDOS de ocupar a VRAM simultaneamente. Este módulo garante o
descarregamento forçado via `keep_alive=0` antes de trocar de modelo.
"""

import json
import logging
from typing import Any

import requests

from src.config import (
    MODELO_CHAT,
    MODELO_VISAO,
    OLLAMA_BASE_URL,
    OLLAMA_TIMEOUT,
)

logger = logging.getLogger(__name__)


class OllamaClientError(Exception):
    """Erro genérico de comunicação com o Ollama."""


def _post_ollama(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Faz POST para a API do Ollama com tratamento de erro robusto.

    Args:
        endpoint: Caminho do endpoint (ex: "/api/generate").
        payload: Corpo JSON da requisição.

    Returns:
        Resposta JSON parseada do Ollama.

    Raises:
        OllamaClientError: Em qualquer falha de comunicação.
    """
    url = f"{OLLAMA_BASE_URL}{endpoint}"
    try:
        resposta = requests.post(
            url,
            json=payload,
            timeout=OLLAMA_TIMEOUT,
        )
        resposta.raise_for_status()
        return resposta.json()
    except requests.exceptions.Timeout:
        msg = f"Timeout ao chamar Ollama ({url}, {OLLAMA_TIMEOUT}s)."
        logger.error(msg)
        raise OllamaClientError(msg)
    except requests.exceptions.ConnectionError:
        msg = f"Ollama indisponível em {OLLAMA_BASE_URL}. Verifique se está rodando."
        logger.error(msg)
        raise OllamaClientError(msg)
    except requests.exceptions.HTTPError as e:
        msg = f"Erro HTTP do Ollama: {e.response.status_code} — {e.response.text[:200]}"
        logger.error(msg)
        raise OllamaClientError(msg)
    except Exception as e:
        msg = f"Erro inesperado ao chamar Ollama: {e}"
        logger.error(msg)
        raise OllamaClientError(msg)


def descarregar_modelo(modelo: str) -> None:
    """Descarrega um modelo da VRAM forçando keep_alive=0.

    Envia uma requisição com prompt vazio e keep_alive="0" para
    forçar o Ollama a liberar a VRAM imediatamente.

    Args:
        modelo: Nome do modelo a descarregar.
    """
    logger.info("Descarregando modelo '%s' da VRAM (keep_alive=0)...", modelo)
    try:
        _post_ollama("/api/generate", {
            "model": modelo,
            "prompt": "",
            "keep_alive": 0,
        })
        logger.info("Modelo '%s' descarregado com sucesso.", modelo)
    except OllamaClientError as e:
        logger.warning("Falha ao descarregar modelo '%s': %s", modelo, e)


def analisar_imagem_com_visao(imagem_base64: str) -> str:
    """Envia imagem ao modelo de visão (Moondream) e retorna descrição textual.

    Fluxo:
    1. Chama Moondream com a imagem e prompt curto e direto.
    2. Após receber a resposta, descarrega o Moondream da VRAM.

    Nota: Moondream (~2GB) é otimizado para prompts curtos e objetivos.
    Prompts longos ou complexos degradam a qualidade da saída.

    Args:
        imagem_base64: String Base64 da imagem (sem prefixo data:).

    Returns:
        Descrição textual da imagem gerada pelo Moondream.

    Raises:
        OllamaClientError: Se a chamada ao Ollama falhar.
    """
    logger.info("Enviando imagem para análise visual com '%s'...", MODELO_VISAO)

    try:
        resposta = _post_ollama("/api/generate", {
            "model": MODELO_VISAO,
            "prompt": "Analyze this screenshot. Describe the main application open, the overall layout, and read ONLY the large, prominent text. Keep it concise, do not guess small blurry text.",
            "images": [imagem_base64],
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 400,
            },
        })

        descricao = resposta.get("response", "").strip()
        logger.info(
            "Análise visual concluída (%d caracteres).", len(descricao)
        )

        # PASSO CRÍTICO: Descarregar Moondream da VRAM antes de chamar Qwen
        descarregar_modelo(MODELO_VISAO)

        return descricao

    except OllamaClientError:
        # Tenta descarregar mesmo em caso de erro
        descarregar_modelo(MODELO_VISAO)
        raise


def chamar_qwen_estruturado(prompt: str) -> dict[str, Any]:
    """Chama o Qwen 2.5 7B com saída JSON estruturada.

    Args:
        prompt: Prompt compilado (texto do usuário + descrição + contexto RAG).

    Returns:
        Dicionário parseado da resposta JSON do Qwen.

    Raises:
        OllamaClientError: Se a chamada ao Ollama falhar.
        json.JSONDecodeError: Se a resposta não for JSON válido.
    """
    logger.info("Chamando '%s' em modo JSON estruturado...", MODELO_CHAT)

    resposta = _post_ollama("/api/generate", {
        "model": MODELO_CHAT,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.1,
        },
    })

    texto_resposta = resposta.get("response", "").strip()
    logger.info("Resposta Qwen recebida (%d caracteres).", len(texto_resposta))

    try:
        return json.loads(texto_resposta)
    except json.JSONDecodeError as e:
        logger.error(
            "Resposta do Qwen não é JSON válido: %s\nResposta bruta: %s",
            e,
            texto_resposta[:500],
        )
        raise


def pipeline_multimodal(
    texto_usuario: str,
    contexto_rag: str,
    imagem_base64: str | None = None,
) -> dict[str, Any]:
    """Executa o pipeline completo dual-model com gestão de VRAM.

    SE imagem presente:
        1. Moondream analisa a imagem → descrição textual
        2. Descarrega Moondream (keep_alive=0)
        3. Compila prompt: texto + descrição + RAG
        4. Qwen retorna JSON estruturado

    SE sem imagem:
        1. Compila prompt: texto + RAG
        2. Qwen retorna JSON estruturado

    Args:
        texto_usuario: Texto digitado/falado pelo usuário.
        contexto_rag: Contexto recuperado do banco vetorial.
        imagem_base64: Imagem em Base64 (opcional).

    Returns:
        Dicionário JSON validável contra SystemResponse.
    """
    descricao_tela = ""

    # ── Passo 1: Análise visual (se imagem presente) ──
    if imagem_base64:
        try:
            descricao_tela = analisar_imagem_com_visao(imagem_base64)
        except OllamaClientError as e:
            logger.error("Pipeline de visão falhou: %s. Continuando sem descrição.", e)
            descricao_tela = "[Erro na análise visual — imagem não processada]"

    # ── Passo 2: Compilar prompt ──
    partes_prompt = [f"Texto do Utilizador: {texto_usuario}"]

    if descricao_tela:
        partes_prompt.append(f"Descrição da Tela (análise visual):\n{descricao_tela}")

    if contexto_rag:
        partes_prompt.append(
            f"Contexto do Banco Vetorial:\n{contexto_rag}"
        )

    partes_prompt.append(
        "\nResponda OBRIGATORIAMENTE neste formato JSON:\n"
        '{"response": "sua resposta aqui", '
        '"action": {"type": "CMD|FINANCE|AGENDA|NONE", '
        '"payload": null, "confidence": 0.0}}'
    )

    prompt_compilado = "\n\n".join(partes_prompt)

    # ── Passo 3: Chamar Qwen ──
    return chamar_qwen_estruturado(prompt_compilado)
