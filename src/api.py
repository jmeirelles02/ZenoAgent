"""Servidor FastAPI para comunicação com a UI do Zeno."""

import logging
import queue
import secrets

import pygame
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.config import PORTA_API
from src.state import estado
from src.system_monitor import obter_metricas_sistema

logger = logging.getLogger(__name__)

fila_comandos: queue.Queue[str] = queue.Queue()

TOKEN_SESSAO: str = secrets.token_hex(16)

app = FastAPI(title="ZenoAgent API", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ComandoRequest(BaseModel):
    """Schema de validação para comandos recebidos da UI."""

    comando: str = Field(..., min_length=1, max_length=2000)


def verificar_token(x_zeno_token: str = Header(default="")) -> None:
    """Valida o token de sessão nos headers da requisição."""
    if x_zeno_token != TOKEN_SESSAO:
        raise HTTPException(status_code=403, detail="Token inválido.")


@app.get("/estado")
def rota_estado() -> dict:
    """Retorna o estado atual do Zeno como JSON."""
    return estado.to_dict()


@app.get("/sistema")
def rota_sistema() -> dict:
    """Retorna métricas de CPU, RAM, disco e bateria."""
    return obter_metricas_sistema()


@app.post("/enviar")
def receber_comando(
    dados: ComandoRequest, _: None = Depends(verificar_token)
) -> dict:
    """Recebe comandos da UI e os coloca na fila de processamento."""
    if dados.comando == "[CANCELAR]":
        pygame.mixer.music.stop()
        with fila_comandos.mutex:
            fila_comandos.queue.clear()
    elif dados.comando == "[VOZ]":
        with fila_comandos.mutex:
            fila_comandos.queue.clear()
        fila_comandos.put(dados.comando)
    else:
        fila_comandos.put(dados.comando)
    return {"status": "recebido"}


@app.get("/token")
def obter_token() -> dict:
    """Endpoint para a UI obter o token de sessão."""
    return {"token": TOKEN_SESSAO}


def rodar_servidor() -> None:
    """Inicia o servidor FastAPI em modo silencioso."""
    logging.getLogger("uvicorn").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)
    uvicorn.run(app, host="127.0.0.1", port=PORTA_API, log_level="error")
