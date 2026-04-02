"""Integração com Gmail para leitura de e-mails."""

import logging

from googleapiclient.discovery import build

from src.google_auth import autenticar_google

logger = logging.getLogger(__name__)


def _obter_servico():
    """Obtém o serviço autenticado do Gmail."""
    credenciais = autenticar_google()
    return build("gmail", "v1", credentials=credenciais)


def listar_emails_recentes(quantidade: int = 5) -> str:
    """Lista os e-mails mais recentes da caixa de entrada."""
    try:
        servico = _obter_servico()
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

            if "<" in remetente:
                nome = remetente.split("<")[0].strip().strip('"')
                remetente = nome if nome else remetente

            resumos.append(f"- De: {remetente} | Assunto: {assunto}")

        return "Seus e-mails mais recentes:\n" + "\n".join(resumos)
    except Exception as e:
        logger.error("Erro ao acessar Gmail: %s", e)
        return f"Erro ao acessar e-mails: {e}"
