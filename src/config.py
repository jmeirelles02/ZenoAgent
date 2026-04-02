"""Configurações centralizadas e constantes do projeto."""

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv("DATABASE_URL", "")

VOZ_PADRAO: str = "pt-BR-AntonioNeural"
ARQUIVO_AUDIO_TEMP: str = "resposta.mp3"

PAUSA_RECONHECIMENTO: float = 2.0
TIMEOUT_ESCUTA: int = 5
DURACAO_AJUSTE_RUIDO: float = 0.5

MODELO_CHAT: str = "qwen2.5:latest"
MODELO_EMBEDDING: str = "nomic-embed-text"

PORTA_API: int = 5000

MAX_HISTORICO: int = 50
MAX_HISTORICO_LLM: int = 20

TAGS_OCULTAS: list[str] = [
    "CMD", "MEM", "PYTHON", "FINANCE", "AGENDA", "DESMARCAR",
    "CLIMA", "MEDIA", "EMAIL", "ABRIR",
]

GATILHOS_PESQUISA: list[str] = [
    "pesquise na", "busque na", "internet", "pesquise sobre", "notícia", "procurar na web"
]

COMANDOS_SAIDA: list[str] = ["sair", "exit", "quit", "fechar", "desligar"]

ESCOPOS_GOOGLE: list[str] = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
]
