"""Controle de mídia do sistema via teclas de mídia."""

import logging

import keyboard

logger = logging.getLogger(__name__)

ACOES_MIDIA: dict[str, str] = {
    "play": "play/pause media",
    "pause": "play/pause media",
    "pausar": "play/pause media",
    "tocar": "play/pause media",
    "next": "next track",
    "proximo": "next track",
    "proxima": "next track",
    "pular": "next track",
    "anterior": "previous track",
    "previous": "previous track",
    "voltar": "previous track",
    "mudo": "volume mute",
    "mute": "volume mute",
    "silenciar": "volume mute",
}


def controlar_midia(acao: str) -> str:
    """Executa uma ação de controle de mídia via teclas do sistema."""
    acao_lower = acao.strip().lower()
    tecla = ACOES_MIDIA.get(acao_lower)

    if not tecla:
        acoes_validas = ", ".join(sorted(set(ACOES_MIDIA.keys())))
        return f"Ação '{acao}' não reconhecida. Use: {acoes_validas}"

    try:
        keyboard.send(tecla)
        logger.info("MEDIA: %s -> %s", acao, tecla)
        return f"Mídia: '{acao}' executado com sucesso."
    except Exception as e:
        logger.error("Erro ao controlar mídia: %s", e)
        return f"Erro ao controlar mídia: {e}"
