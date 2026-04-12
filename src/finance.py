"""Consulta de cotações do mercado financeiro."""

from src.plugins import aris_tool
import logging

import yfinance as yf

logger = logging.getLogger(__name__)


@aris_tool
def buscar_cotacao(ticker: str) -> str:
    """Busca a cotação atual de um ativo na bolsa de valores.

    ticker: Código do ativo no Yahoo Finance (ex: 'PETR4.SA', 'VALE3.SA', 'AAPL')
    """
    try:
        ativo = yf.Ticker(ticker)
        dados = ativo.history(period="1d")
        if dados.empty:
            return f"Não encontrei dados para o ativo {ticker}."

        preco_atual = dados["Close"].iloc[-1]
        abertura = dados["Open"].iloc[-1]
        variacao = ((preco_atual - abertura) / abertura) * 100
        tendencia = "alta" if variacao > 0 else "queda"

        return (
            f"A cotação atual de {ticker} é R$ {preco_atual:.2f}, "
            f"operando em {tendencia} de {abs(variacao):.2f}% hoje."
        )
    except Exception as e:
        logger.error("Erro ao acessar o mercado financeiro: %s", e)
        return f"Erro ao acessar o mercado financeiro: {e}"
