"""Autenticação unificada com APIs do Google (Calendar + Gmail)."""

import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from src.config import ESCOPOS_GOOGLE

logger = logging.getLogger(__name__)

_credenciais_cache: Credentials | None = None


def autenticar_google() -> Credentials:
    """Autentica com as APIs do Google via OAuth2 com cache em memória."""
    global _credenciais_cache

    if _credenciais_cache and _credenciais_cache.valid:
        return _credenciais_cache

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

    _credenciais_cache = credenciais
    return credenciais
