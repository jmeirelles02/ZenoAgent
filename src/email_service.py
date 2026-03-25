"""Integração com Gmail para leitura de e-mails."""

import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.config import ESCOPOS_GOOGLE

logger = logging.getLogger(__name__)


def autenticar_gmail():
    """Autentica com a API do Gmail via OAuth2."""
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

    return build("gmail", "v1", credentials=credenciais)


def listar_emails_recentes(quantidade: int = 5) -> str:
    """Lista os e-mails mais recentes da caixa de entrada."""
    try:
        servico = autenticar_gmail()
        resultado = servico.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=quantidade
        ).execute()

        mensagens = resultado.get("messages", [])
        if not mensagens:
            return "Sua caixa de entrada está vazia."

        resumos: list[str] = []
        for msg in mensagens:
            detalhe = servico.users().messages().get(
                userId="me", id=msg["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"]
            ).execute()

            headers = {h["name"]: h["value"] for h in detalhe.get("payload", {}).get("headers", [])}
            remetente = headers.get("From", "Desconhecido")
            assunto = headers.get("Subject", "Sem assunto")
            data = headers.get("Date", "")

            if "<" in remetente:
                nome = remetente.split("<")[0].strip().strip('"')
                remetente = nome if nome else remetente

            resumos.append(f"- De: {remetente} | Assunto: {assunto}")

        return "Seus e-mails mais recentes:\n" + "\n".join(resumos)
    except Exception as e:
        logger.error("Erro ao acessar Gmail: %s", e)
        return f"Erro ao acessar e-mails: {e}"
