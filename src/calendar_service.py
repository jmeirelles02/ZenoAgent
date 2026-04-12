"""Integração com o Google Calendar."""

import logging
from datetime import datetime, timedelta

from googleapiclient.discovery import build

from src.google_auth import autenticar_google
from src.plugins import aris_tool

logger = logging.getLogger(__name__)


def _obter_servico():
    """Obtém o serviço autenticado do Google Calendar."""
    credenciais = autenticar_google()
    return build("calendar", "v3", credentials=credenciais)


@aris_tool
def criar_evento_calendario(data_hora: str, titulo: str) -> str:
    """Cria um evento no Google Calendar com data/hora e título.

    data_hora: Data e hora do evento no formato ISO 8601 (ex: '2026-04-15T14:00:00')
    titulo: Título ou descrição do compromisso (ex: 'Reunião com equipe')
    """
    try:
        inicio_dt = datetime.fromisoformat(data_hora)
        fim_dt = inicio_dt + timedelta(hours=1)

        servico = _obter_servico()
        evento = {
            "summary": titulo,
            "start": {
                "dateTime": inicio_dt.isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
            "end": {
                "dateTime": fim_dt.isoformat(),
                "timeZone": "America/Sao_Paulo",
            },
        }

        servico.events().insert(calendarId="primary", body=evento).execute()
        return (
            f"O compromisso '{titulo}' foi agendado com sucesso para "
            f"{inicio_dt.strftime('%d/%m/%Y às %H:%M')}."
        )
    except ValueError as e:
        logger.error("Formato de data inválido: %s", e)
        return f"Erro: Formato de data inválido: {e}"
    except Exception as e:
        logger.error("Falha ao registrar na nuvem: %s", e)
        return f"Falha ao registrar na nuvem: {e}"


@aris_tool
def remover_evento_calendario(data_hora: str, titulo: str) -> str:
    """Remove um evento do Google Calendar buscando por título e data.

    data_hora: Data do evento no formato ISO 8601 (ex: '2026-04-15T14:00:00')
    titulo: Título do compromisso a remover
    """
    try:
        data_ref = datetime.fromisoformat(data_hora)
        inicio_dia = (
            data_ref.replace(hour=0, minute=0, second=0).isoformat() + "Z"
        )
        fim_dia = (
            data_ref.replace(hour=23, minute=59, second=59).isoformat() + "Z"
        )

        titulo_busca = titulo.lower()
        servico = _obter_servico()
        resultado = (
            servico.events()
            .list(
                calendarId="primary",
                timeMin=inicio_dia,
                timeMax=fim_dia,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        eventos = resultado.get("items", [])
        for evento in eventos:
            resumo_evento = evento.get("summary", "").lower()
            if titulo_busca in resumo_evento or resumo_evento in titulo_busca:
                servico.events().delete(
                    calendarId="primary", eventId=evento["id"]
                ).execute()
                return (
                    f"O compromisso '{evento.get('summary')}' foi removido "
                    "com sucesso da sua agenda do Google."
                )

        return (
            f"Nenhum compromisso com título semelhante a '{titulo}' "
            "foi encontrado nesta data."
        )
    except ValueError as e:
        logger.error("Formato de data inválido: %s", e)
        return f"Erro: Formato de data inválido: {e}"
    except Exception as e:
        logger.error("Falha ao remover evento: %s", e)
        return f"Falha ao remover evento da nuvem: {e}"
