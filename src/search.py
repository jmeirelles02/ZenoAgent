"""Busca de informações na internet via DuckDuckGo."""

import logging

from duckduckgo_search import DDGS

from src.plugins import aris_tool

logger = logging.getLogger(__name__)


@aris_tool
def buscar_na_internet(consulta: str) -> str:
    """Pesquisa informações atualizadas na internet sobre qualquer tema.

    consulta: O que pesquisar na internet (ex: 'preço do dólar hoje', 'notícias sobre IA')
    """
    try:
        resultados = DDGS().text(consulta, region="br-pt", timelimit="w", max_results=3)
        if not resultados:
            resultados = DDGS().text(consulta, region="br-pt", timelimit="m", max_results=3)
        if not resultados:
            return "Nenhuma informacao recente encontrada."

        texto_compilado = "Dados extraidos da internet:\n"
        for r in resultados:
            texto_compilado += f"* Titulo: {r['title']}\n  Resumo: {r['body']}\n"
        return texto_compilado
    except Exception as e:
        logger.error("Falha na conexão com a rede externa: %s", e)
        return f"Falha na conexao com a rede externa: {e}"
