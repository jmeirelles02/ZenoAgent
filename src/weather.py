"""Consulta de previsão do tempo via wttr.in."""

import logging

import requests

logger = logging.getLogger(__name__)


def buscar_clima(cidade: str) -> str:
    """Busca a previsão do tempo atual para a cidade informada."""
    try:
        url = f"https://wttr.in/{cidade}?format=%C+%t+%h+%w&lang=pt"
        resposta = requests.get(url, timeout=10, headers={"Accept-Language": "pt-BR"})
        resposta.raise_for_status()

        dados = resposta.text.strip()
        if "Unknown" in dados or "não" in dados.lower():
            return f"Não encontrei dados de clima para '{cidade}'."

        return f"Clima em {cidade}: {dados}"
    except requests.Timeout:
        return "Erro: tempo esgotado ao buscar previsão do tempo."
    except Exception as e:
        logger.error("Erro ao buscar clima: %s", e)
        return f"Erro ao buscar clima: {e}"
