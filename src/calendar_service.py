"""Integração com o Google Calendar."""

import logging
import os
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.config import ESCOPOS_GOOGLE

logger = logging.getLogger(__name__)


def autenticar_google():
    """Autentica com a API do Google Calendar via OAuth2."""
    credenciais = None
    if os.path.exists("token.json"):
        credenciais = Credentials.from_authorized_user_file("token.json", ESCOPOS_GOOGLE)

    if not credenciais or not credenciais.valid:
        if credenciais and credenciais.expired and credenciais.refresh_token:
            credenciais.refresh(Request())
        else:
            fluxo = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", ESCOPOS_GOOGLE
            )
            credenciais = fluxo.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(credenciais.to_json())

    return build("calendar", "v3", credentials=credenciais)


def criar_evento_calendario(texto_tag: str) -> str:
    """Cria um evento no Google Calendar a partir de uma string formatada."""
    try:
        partes = texto_tag.split("|")
        if len(partes) != 2:
            return "Erro: Formato de agenda inválido."

        inicio_str = partes[0].strip()
        resumo = partes[1].strip()

        inicio_dt = datetime.fromisoformat(inicio_str)
        fim_dt = inicio_dt + timedelta(hours=1)

        servico = autenticar_google()
        evento = {
            "summary": resumo,
            "start": {"dateTime": inicio_dt.isoformat(), "timeZone": "America/Sao_Paulo"},
            "end": {"dateTime": fim_dt.isoformat(), "timeZone": "America/Sao_Paulo"},
        }

        servico.events().insert(calendarId="primary", body=evento).execute()
        return f"O compromisso '{resumo}' foi agendado com sucesso na sua conta do Google."
    except ValueError as e:
        logger.error("Formato de data inválido: %s", e)
        return f"Erro: Formato de data inválido: {e}"
    except Exception as e:
        logger.error("Falha ao registrar na nuvem: %s", e)
        return f"Falha ao registrar na nuvem: {e}"


def remover_evento_calendario(texto_tag: str) -> str:
    """Remove um evento do Google Calendar buscando por título e data."""
    try:
        partes = texto_tag.split("|")
        if len(partes) != 2:
            return "Erro: Formato de desmarcação inválido."

        data_str = partes[0].strip()
        titulo_busca = partes[1].strip().lower()

        data_ref = datetime.fromisoformat(data_str)
        inicio_dia = data_ref.replace(hour=0, minute=0, second=0).isoformat() + "Z"
        fim_dia = data_ref.replace(hour=23, minute=59, second=59).isoformat() + "Z"

        servico = autenticar_google()
        resultado = servico.events().list(
            calendarId="primary",
            timeMin=inicio_dia,
            timeMax=fim_dia,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        eventos = resultado.get("items", [])
        for evento in eventos:
            resumo_evento = evento.get("summary", "").lower()
            if titulo_busca in resumo_evento or resumo_evento in titulo_busca:
                servico.events().delete(
                    calendarId="primary", eventId=evento["id"]
                ).execute()
                return f"O compromisso '{evento.get('summary')}' foi removido com sucesso da sua agenda do Google."

        return f"Nenhum compromisso com título semelhante a '{partes[1].strip()}' foi encontrado nesta data."
    except ValueError as e:
        logger.error("Formato de data inválido: %s", e)
        return f"Erro: Formato de data inválido: {e}"
    except Exception as e:
        logger.error("Falha ao remover evento: %s", e)
        return f"Falha ao remover evento da nuvem: {e}"
