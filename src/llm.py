"""Criação e configuração da sessão de chat com Ollama — Native Tool Calling.

Suporta dois modos de operação:
  1. Chat com Tool Calling nativo — o modelo decide quando e qual ferramenta usar.
  2. Pipeline multimodal estruturado — para requisições com imagem (dual-model).
"""

import json
import logging
import platform
from datetime import datetime
from typing import Any, Generator

import ollama
from pydantic import ValidationError

from src.config import MAX_HISTORICO_LLM, MODELO_CHAT
from src.database import buscar_memoria_relevante
from src.models import SystemResponse, validar_resposta_llm
from src.ollama_client import OllamaClientError, pipeline_multimodal
from src.plugins import executar_ferramenta, obter_schemas_ferramentas

logger = logging.getLogger(__name__)


class SessaoChat:
    """Gerencia uma sessão de chat com histórico e tool calling nativo."""

    def __init__(self, modelo: str, instrucoes_sistema: str):
        self.modelo = modelo
        self.mensagens: list[dict[str, Any]] = [
            {"role": "system", "content": instrucoes_sistema}
        ]
        self._tools = obter_schemas_ferramentas()
        logger.info(
            "Sessão de chat criada com %d ferramentas disponíveis.", len(self._tools)
        )

    def enviar_mensagem_stream(self, mensagem: str) -> Generator[str, None, None]:
        """Envia uma mensagem e retorna chunks de texto em streaming.

        Fluxo com Tool Calling:
        1. Envia mensagem ao modelo com schemas de ferramentas.
        2. Se o modelo retornar tool_calls, executa cada ferramenta.
        3. Injeta resultados como mensagens role="tool" no histórico.
        4. Re-envia ao modelo para gerar resposta final.
        5. Yield dos chunks de texto da resposta final em streaming.
        """
        self.mensagens.append({"role": "user", "content": mensagem})
        self._truncar_historico()

        # ── Passo 1: Primeira chamada (pode gerar tool_calls) ──
        resposta_inicial = ollama.chat(
            model=self.modelo,
            messages=self.mensagens,
            tools=self._tools,
            stream=False,
        )

        msg_assistente = resposta_inicial.message

        # ── Passo 2: Processar tool calls (se houver) ──
        if msg_assistente.tool_calls:
            logger.info(
                "LLM solicitou %d ferramenta(s).", len(msg_assistente.tool_calls)
            )

            # Adicionar a mensagem do assistente (com tool_calls) ao histórico
            self.mensagens.append({
                "role": "assistant",
                "content": msg_assistente.content or "",
                "tool_calls": [
                    {
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    }
                    for tc in msg_assistente.tool_calls
                ],
            })

            # Executar cada ferramenta e injetar resultado
            for tool_call in msg_assistente.tool_calls:
                nome = tool_call.function.name
                args = tool_call.function.arguments
                logger.info("Executando ferramenta: %s(%s)", nome, args)

                resultado = executar_ferramenta(nome, args)

                self.mensagens.append({
                    "role": "tool",
                    "content": str(resultado),
                })

            # ── Passo 3: Re-enviar ao modelo com resultados das ferramentas ──
            resposta_completa = ""
            for chunk in ollama.chat(
                model=self.modelo,
                messages=self.mensagens,
                stream=True,
            ):
                texto = chunk.message.content
                resposta_completa += texto
                yield texto

            self.mensagens.append({
                "role": "assistant",
                "content": resposta_completa,
            })
        else:
            # ── Sem tool calls: retornar resposta direta ──
            texto = msg_assistente.content or ""
            self.mensagens.append({"role": "assistant", "content": texto})
            yield texto

    def _truncar_historico(self) -> None:
        """Mantém apenas as últimas N mensagens + system prompt."""
        if len(self.mensagens) > MAX_HISTORICO_LLM + 1:
            self.mensagens = (
                [self.mensagens[0]] + self.mensagens[-MAX_HISTORICO_LLM:]
            )


def processar_requisicao_multimodal(
    texto_usuario: str,
    imagem_base64: str | None = None,
) -> dict[str, Any]:
    """Processa uma requisição usando o pipeline dual-model com validação.

    Este é o ponto de entrada para requisições multimodais vindas da API.
    Segue a árvore de decisão:
      - COM imagem: Moondream (visão) → descarrega → Qwen (lógica/JSON)
      - SEM imagem: Qwen (lógica/JSON) direto

    Args:
        texto_usuario: Texto do comando do usuário.
        imagem_base64: Imagem capturada em Base64 (opcional).

    Returns:
        Dicionário com a resposta validada ou fallback em caso de erro.
    """
    contexto_rag = buscar_memoria_relevante(texto_usuario)

    try:
        json_bruto = pipeline_multimodal(
            texto_usuario=texto_usuario,
            contexto_rag=contexto_rag,
            imagem_base64=imagem_base64,
        )

        resposta_validada = validar_resposta_llm(json_bruto)
        logger.info(
            "Resposta validada — ação: %s (confiança: %.2f)",
            resposta_validada.action.type,
            resposta_validada.action.confidence,
        )
        return resposta_validada.model_dump()

    except ValidationError as e:
        logger.error("Validação Pydantic falhou: %s", e)
        return _resposta_fallback(
            f"Erro de validação na resposta do modelo. Detalhes: {e}"
        )
    except OllamaClientError as e:
        logger.error("Erro no pipeline Ollama: %s", e)
        return _resposta_fallback(
            f"Erro de comunicação com o Ollama: {e}"
        )
    except json.JSONDecodeError as e:
        logger.error("Resposta do modelo não é JSON válido: %s", e)
        return _resposta_fallback(
            "O modelo não retornou JSON válido. Tente novamente."
        )
    except Exception as e:
        logger.error("Erro inesperado no pipeline multimodal: %s", e)
        return _resposta_fallback(f"Erro inesperado: {e}")


def _resposta_fallback(mensagem_erro: str) -> dict[str, Any]:
    """Gera uma resposta de fallback segura quando o pipeline falha."""
    return {
        "response": mensagem_erro,
        "action": {
            "type": "NONE",
            "payload": None,
            "confidence": 0.0,
        },
    }


def montar_instrucoes_sistema(caminho_desktop: str, usuario: str) -> str:
    """Monta o system prompt para Native Tool Calling.

    O prompt foi simplificado: as instruções sobre tags foram removidas.
    O modelo agora recebe schemas de ferramentas automaticamente via
    o parâmetro `tools` do ollama.chat().
    """
    data_hora_atual = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    sistema_operacional = platform.system()

    return f"""<IDENTIDADE>
Você é o A.R.I.S (Artificial Reactive Intelligence System), assistente pessoal no {sistema_operacional} do usuário. Responda em português do Brasil, de forma direta e sem distração.
Você TEM PERMISSÃO para executar comandos e usar ferramentas no {sistema_operacional}. Antes de ações destrutivas, pergunte ao usuário.
</IDENTIDADE>

<CONTEXTO>
Usuário: {usuario}
Data e hora atual: {data_hora_atual}
Diretório da Área de Trabalho: {caminho_desktop}
Sistema Operacional: {sistema_operacional}
</CONTEXTO>

<FERRAMENTAS>
Você tem acesso a ferramentas que são chamadas automaticamente pelo sistema. Quando precisar executar uma ação, use a ferramenta apropriada. Os schemas das ferramentas são enviados automaticamente.

REGRAS DE USO:
1. Para abrir APLICATIVOS INSTALADOS (Spotify, Discord, Chrome, Steam, VS Code, etc), use 'abrir_aplicativo'.
2. Para abrir SITES e URLs (YouTube, Google, GitHub, qualquer link), use 'abrir_url'. NUNCA use abrir_aplicativo para sites.
3. Para comandos do terminal, use 'executar_comando'.
4. Para PESQUISAR informações na internet, use 'buscar_na_internet'.
5. Para agendar compromissos, use 'criar_evento_calendario' com data_hora em formato ISO 8601.
6. Para cancelar compromissos, use 'remover_evento_calendario'.
7. Para buscar clima, use 'buscar_clima' com o nome da cidade.
8. Para buscar cotações, use 'buscar_cotacao' com o ticker (ex: PETR4.SA).
9. Para gravar memória, use 'salvar_memoria'.
10. Para executar scripts Python, use 'executar_python'.
11. Para controlar mídia (play, pause, próximo, anterior), use 'controlar_midia'.
12. Para listar e-mails, use 'listar_emails_recentes'.

IMPORTANTE:
- Cada ferramenta será executada AUTOMATICAMENTE quando você a chamar.
- O resultado será injetado na conversa para que você formule a resposta final.
- NUNCA invente resultados. Se precisar de dados em tempo real, use a ferramenta.
- Para ABRIR SITES, SEMPRE use 'abrir_url'. Exemplos de sites: youtube, google, github, reddit, twitter.
</FERRAMENTAS>

<EXEMPLOS_FERRAMENTAS>
- Usuário: "abre o spotify" → use abrir_aplicativo(nome_app="spotify")
- Usuário: "abre o discord" → use abrir_aplicativo(nome_app="discord")
- Usuário: "abre o youtube" → use abrir_url(url="https://www.youtube.com")
- Usuário: "acessar o github" → use abrir_url(url="https://www.github.com")
- Usuário: "abre google.com" → use abrir_url(url="https://www.google.com")
- Usuário: "pesquisa sobre inteligência artificial" → use buscar_na_internet(consulta="inteligência artificial")
- Usuário: "agenda reunião amanhã às 15h" → use criar_evento_calendario(data_hora="2026-04-13T15:00:00", titulo="Reunião")
- Usuário: "como está o tempo em São Paulo?" → use buscar_clima(cidade="São Paulo")
- Usuário: "cotação da Petrobras" → use buscar_cotacao(ticker="PETR4.SA")
</EXEMPLOS_FERRAMENTAS>"""


def criar_sessao_chat(caminho_desktop: str, usuario: str) -> SessaoChat:
    """Cria uma sessão de chat com o Ollama usando instruções e tool calling."""
    instrucoes = montar_instrucoes_sistema(caminho_desktop, usuario)
    return SessaoChat(modelo=MODELO_CHAT, instrucoes_sistema=instrucoes)
