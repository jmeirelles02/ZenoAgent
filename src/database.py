"""Gerenciamento do banco de dados vetorial e memória."""

import logging
import time
from collections import OrderedDict
from contextlib import contextmanager
from typing import Generator

import ollama
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

from src.config import DATABASE_URL, MODELO_EMBEDDING

logger = logging.getLogger(__name__)

_pool: ThreadedConnectionPool | None = None
_banco_disponivel: bool = False

MAX_CACHE_EMBEDDINGS: int = 100
_cache_embeddings: OrderedDict[str, list[float]] = OrderedDict()


def _criar_pool() -> bool:
    """Tenta criar o pool de conexões. Retorna True se obteve sucesso."""
    global _pool, _banco_disponivel
    if not DATABASE_URL:
        logger.warning("DATABASE_URL não configurada. Memória desativada.")
        _banco_disponivel = False
        return False
    try:
        _pool = ThreadedConnectionPool(1, 5, DATABASE_URL, connect_timeout=10)
        _banco_disponivel = True
        return True
    except Exception as e:
        logger.warning("Falha ao criar pool de conexões: %s", e)
        _banco_disponivel = False
        return False


@contextmanager
def conectar_banco() -> Generator:
    """Gerencia conexão via pool garantindo devolução segura."""
    if not _banco_disponivel or _pool is None:
        raise ConnectionError("Banco de dados indisponível.")
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)


def inicializar_banco() -> None:
    """Cria o pool, extensão pgvector e tabela de memória com retry."""
    global _banco_disponivel
    for tentativa in range(3):
        if _criar_pool():
            try:
                with conectar_banco() as conn:
                    cursor = conn.cursor()
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")

                    cursor.execute("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = 'memoria' AND column_name = 'vetor'
                    """)
                    tabela_valida = cursor.fetchone() is not None

                    cursor.execute("SELECT to_regclass('public.memoria')")
                    tabela_existe = cursor.fetchone()[0] is not None

                    if tabela_existe and not tabela_valida:
                        logger.warning("Tabela 'memoria' com schema incompatível. Recriando...")
                        cursor.execute("DROP TABLE memoria")

                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS memoria (
                            id SERIAL PRIMARY KEY,
                            usuario TEXT,
                            informacao TEXT,
                            vetor vector(768)
                        )
                    """)
                logger.info("Banco de dados conectado com sucesso (pool ativo).")
                return
            except Exception as e:
                logger.warning("Tentativa %d/3 de inicialização falhou: %s", tentativa + 1, e)
                _banco_disponivel = False
        if tentativa < 2:
            espera = 2 ** tentativa
            logger.info("Aguardando %ds antes de nova tentativa...", espera)
            time.sleep(espera)

    logger.warning("Banco indisponível após 3 tentativas. Memória desativada.")
    _banco_disponivel = False


def gerar_embedding(texto: str) -> list[float]:
    """Gera embedding com cache LRU em memória."""
    if texto in _cache_embeddings:
        _cache_embeddings.move_to_end(texto)
        return _cache_embeddings[texto]

    resultado = ollama.embed(model=MODELO_EMBEDDING, input=texto)
    embedding = resultado.embeddings[0]

    _cache_embeddings[texto] = embedding
    if len(_cache_embeddings) > MAX_CACHE_EMBEDDINGS:
        _cache_embeddings.popitem(last=False)

    return embedding


def dividir_em_chunks(
    texto: str, tamanho_max: int = 500, sobreposicao: int = 50
) -> list[str]:
    """Divide texto em pedaços com sobreposição para melhor recuperação."""
    if len(texto) <= tamanho_max:
        return [texto]

    chunks: list[str] = []
    inicio = 0
    while inicio < len(texto):
        fim = inicio + tamanho_max
        chunks.append(texto[inicio:fim])
        inicio = fim - sobreposicao
    return chunks


def salvar_memoria(usuario: str, informacao: str) -> None:
    """Salva informação na memória vetorial dividida em chunks."""
    if not _banco_disponivel:
        logger.warning("Tentativa de salvar memória com banco indisponível.")
        return
    try:
        pedacos = dividir_em_chunks(informacao)
        with conectar_banco() as conn:
            cursor = conn.cursor()
            for pedaco in pedacos:
                vetor = gerar_embedding(pedaco)
                cursor.execute(
                    "INSERT INTO memoria (usuario, informacao, vetor) VALUES (%s, %s, %s)",
                    (usuario, pedaco, str(vetor)),
                )
    except Exception as e:
        logger.warning("Falha ao salvar memória: %s", e)


def buscar_memoria_relevante(pergunta: str, limite: int = 3) -> str:
    """Busca memórias semanticamente similares via pgvector."""
    if not _banco_disponivel:
        return ""
    try:
        vetor_pergunta = gerar_embedding(pergunta)
        with conectar_banco() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT informacao FROM memoria ORDER BY vetor <=> %s::vector LIMIT %s",
                (str(vetor_pergunta), limite),
            )
            resultados = cursor.fetchall()
            if resultados:
                return "\n".join([f"* {r[0]}" for r in resultados])
            return ""
    except Exception as e:
        logger.warning("Erro de RAG: %s", e)
        return ""


def fechar_pool() -> None:
    """Fecha o pool de conexões. Chamar ao encerrar o sistema."""
    global _pool, _banco_disponivel
    if _pool:
        _pool.closeall()
        _pool = None
    _banco_disponivel = False
