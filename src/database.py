"""Gerenciamento do banco de dados vetorial e memória."""

import logging
from contextlib import contextmanager
from typing import Generator

import ollama
import psycopg2

from src.config import DATABASE_URL, MODELO_EMBEDDING

logger = logging.getLogger(__name__)


@contextmanager
def conectar_banco() -> Generator:
    """Gerencia conexão com o banco garantindo fechamento seguro."""
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=10, options="-c statement_timeout=15000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inicializar_banco() -> None:
    """Cria a extensão pgvector e a tabela de memória se não existirem."""
    try:
        with conectar_banco() as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")

            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'memoria' AND column_name = 'vetor'
            """)
            tabela_valida = cursor.fetchone() is not None

            cursor.execute("""
                SELECT to_regclass('public.memoria')
            """)
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
        logger.info("Banco de dados conectado com sucesso.")
    except Exception as e:
        logger.warning("Banco de dados indisponível. Memória desativada: %s", e)


def gerar_embedding(texto: str) -> list[float]:
    """Gera embedding vetorial usando modelo local via Ollama."""
    resultado = ollama.embed(model=MODELO_EMBEDDING, input=texto)
    return resultado.embeddings[0]


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
    """Busca memórias semanticamente similares à pergunta via pgvector."""
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
        logger.warning("Tabela vazia ou erro de RAG: %s", e)
        return ""
