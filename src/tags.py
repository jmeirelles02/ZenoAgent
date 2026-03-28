"""Processamento de tags ocultas geradas pelo LLM."""

import logging
import re
from typing import Callable

from src.calendar_service import criar_evento_calendario, remover_evento_calendario
from src.commands import executar_comando, executar_python, abrir_aplicativo
from src.config import TAGS_OCULTAS
from src.database import salvar_memoria
from src.email_service import listar_emails_recentes
from src.finance import buscar_cotacao
from src.media import controlar_midia
from src.state import estado
from src.weather import buscar_clima

logger = logging.getLogger(__name__)


def limpar_texto_para_fala(texto: str) -> str:
    """Remove todas as tags internas e formatação markdown do texto."""
    texto_limpo = texto
    for tag in TAGS_OCULTAS:
        texto_limpo = re.sub(
            rf"\[{tag}\].*?\[/{tag}\]", "", texto_limpo, flags=re.DOTALL
        )
    return re.sub(r"[*#_]", "", texto_limpo)


def processar_tags_ocultas(
    texto: str,
    usuario_atual: str,
    callback_falar: Callable[[str], None],
) -> None:
    """Extrai e executa todas as tags ocultas presentes na resposta do LLM."""
    comandos = re.findall(r"\[CMD\](.*?)\[/CMD\]", texto, flags=re.DOTALL)
    for cmd in comandos:
        logger.info("TAG [CMD]: %s", cmd.strip())
        print(f"\n[Executando comando: {cmd.strip()}]")
        saida = executar_comando(cmd.strip())
        if saida:
            print(f"[Saida do Sistema]: {saida.strip()}")
            estado.atualizar(aris=saida.strip())
            estado.adicionar_mensagem("aris", saida.strip())

    aberturas = re.findall(r"\[ABRIR\](.*?)\[/ABRIR\]", texto, flags=re.DOTALL)
    for app in aberturas:
        logger.info("TAG [ABRIR]: %s", app.strip())
        print(f"\n[Tentando abrir aplicação: {app.strip()}]")
        saida = abrir_aplicativo(app.strip())
        if saida:
            print(f"[Resultado]: {saida.strip()}")
            estado.atualizar(aris=saida.strip())
            estado.adicionar_mensagem("aris", saida.strip())

    blocos_python = re.findall(r"\[PYTHON\](.*?)\[/PYTHON\]", texto, flags=re.DOTALL)
    for codigo in blocos_python:
        logger.info("TAG [PYTHON]: %d caracteres", len(codigo.strip()))
        print("\n[Executando rotina de dados em Python...]")
        saida = executar_python(codigo.strip())
        if saida:
            print(f"[Saida do Script]:\n{saida.strip()}")
            estado.atualizar(aris=saida.strip())
            estado.adicionar_mensagem("aris", saida.strip())

    memorias = re.findall(r"\[MEM\](.*?)\[/MEM\]", texto)
    for mem in memorias:
        logger.info("TAG [MEM]: %s", mem)
        print(f"\n[Gravando na memoria: {mem}]")
        salvar_memoria(usuario_atual, mem)

    financas = re.findall(r"\[FINANCE\](.*?)\[/FINANCE\]", texto)
    for ticker in financas:
        logger.info("TAG [FINANCE]: %s", ticker.strip())
        print(f"\n[Acessando Bolsa de Valores: {ticker.strip()}]")
        resultado_fin = buscar_cotacao(ticker.strip())
        print(f"[Mercado]: {resultado_fin}")
        estado.atualizar(aris=resultado_fin)
        estado.adicionar_mensagem("aris", resultado_fin)
        callback_falar(resultado_fin)

    agendas = re.findall(r"\[AGENDA\](.*?)\[/AGENDA\]", texto)
    for ag in agendas:
        logger.info("TAG [AGENDA]: %s", ag.strip())
        print("\n[Acessando Google Calendar...]")
        resultado_ag = criar_evento_calendario(ag.strip())
        print(f"[Google]: {resultado_ag}")
        estado.atualizar(aris=resultado_ag)
        estado.adicionar_mensagem("aris", resultado_ag)
        callback_falar(resultado_ag)

    desmarcacoes = re.findall(r"\[DESMARCAR\](.*?)\[/DESMARCAR\]", texto)
    for dm in desmarcacoes:
        logger.info("TAG [DESMARCAR]: %s", dm.strip())
        print("\n[Removendo evento do Google Calendar...]")
        resultado_dm = remover_evento_calendario(dm.strip())
        print(f"[Google]: {resultado_dm}")
        estado.atualizar(aris=resultado_dm)
        estado.adicionar_mensagem("aris", resultado_dm)
        callback_falar(resultado_dm)

    climas = re.findall(r"\[CLIMA\](.*?)\[/CLIMA\]", texto)
    for cidade in climas:
        logger.info("TAG [CLIMA]: %s", cidade.strip())
        print(f"\n[Buscando clima: {cidade.strip()}]")
        resultado_clima = buscar_clima(cidade.strip())
        print(f"[Clima]: {resultado_clima}")
        estado.atualizar(aris=resultado_clima)
        estado.adicionar_mensagem("aris", resultado_clima)
        callback_falar(resultado_clima)

    medias = re.findall(r"\[MEDIA\](.*?)\[/MEDIA\]", texto)
    for acao in medias:
        logger.info("TAG [MEDIA]: %s", acao.strip())
        print(f"\n[Controle de midia: {acao.strip()}]")
        resultado_media = controlar_midia(acao.strip())
        print(f"[Media]: {resultado_media}")
        estado.atualizar(aris=resultado_media)
        estado.adicionar_mensagem("aris", resultado_media)

    emails = re.findall(r"\[EMAIL\](.*?)\[/EMAIL\]", texto)
    for qtd in emails:
        logger.info("TAG [EMAIL]: %s", qtd.strip())
        print("\n[Acessando Gmail...]")
        quantidade = int(qtd.strip()) if qtd.strip().isdigit() else 5
        resultado_email = listar_emails_recentes(quantidade)
        print(f"[Gmail]: {resultado_email}")
        estado.atualizar(aris=resultado_email)
        estado.adicionar_mensagem("aris", resultado_email)
        callback_falar(resultado_email)
