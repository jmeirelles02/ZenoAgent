"""Criação e configuração da sessão de chat com Ollama."""

import platform
from datetime import datetime
from typing import Generator

import ollama

from src.config import MAX_HISTORICO_LLM, MODELO_CHAT


class SessaoChat:
    """Gerencia uma sessão de chat com histórico de mensagens."""

    def __init__(self, modelo: str, instrucoes_sistema: str):
        self.modelo = modelo
        self.mensagens: list[dict[str, str]] = [
            {"role": "system", "content": instrucoes_sistema}
        ]

    def enviar_mensagem_stream(self, mensagem: str) -> Generator[str, None, None]:
        """Envia uma mensagem e retorna chunks de texto em streaming."""
        self.mensagens.append({"role": "user", "content": mensagem})
        self._truncar_historico()

        resposta_completa = ""
        for chunk in ollama.chat(
            model=self.modelo, messages=self.mensagens, stream=True
        ):
            texto = chunk.message.content
            resposta_completa += texto
            yield texto

        self.mensagens.append({"role": "assistant", "content": resposta_completa})

    def _truncar_historico(self) -> None:
        """Mantém apenas as últimas N mensagens + system prompt."""
        if len(self.mensagens) > MAX_HISTORICO_LLM + 1:
            self.mensagens = [self.mensagens[0]] + self.mensagens[-MAX_HISTORICO_LLM:]


def montar_instrucoes_sistema(caminho_desktop: str, usuario: str) -> str:
    """Monta o system prompt com variáveis dinâmicas do ambiente."""
    data_hora_atual = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    sistema_operacional = platform.system()
    comando_abrir = "xdg-open" if sistema_operacional == "Linux" else "start"

    return f"""<IDENTIDADE>
Voce e o A.R.I.S (Artificial Reactive Intelligence System), assistente pessoal no {sistema_operacional} do usuario. Responda em portugues do Brasil, de forma direta e sem distracao.
Voce TEM PERMISSAO para executar comandos no {sistema_operacional}. Antes de acoes destrutivas, pergunte ao usuario.
</IDENTIDADE>

<CONTEXTO>
Usuario: {usuario}
Data e hora atual: {data_hora_atual}
Diretorio da Area de Trabalho: {caminho_desktop}
Sistema Operacional: {sistema_operacional}
</CONTEXTO>

<TAGS_DISPONIVEIS>
Use APENAS estas tags. Nenhuma tag inventada e permitida.
- [ABRIR]nome_do_app[/ABRIR] → Tenta abrir um programa (Smart: detecta se e binario, Flatpak ou Snap). Use para Spotify, Discord, Chrome, Steam, etc.
- [CMD]comando[/CMD] → Executar comando literal no shell (apenas se o [ABRIR] nao for suficiente).
- [MEM]fato[/MEM] → Gravar fato pessoal novo na memoria.
- [PYTHON]codigo[/PYTHON] → Executar script Python. SEMPRE use caminhos absolutos.
- [FINANCE]TICKER[/FINANCE] → Buscar cotacao na bolsa.
- [AGENDA]YYYY-MM-DDTHH:MM:SS|Titulo[/AGENDA] → Criar compromisso no Google Calendar.
- [DESMARCAR]YYYY-MM-DDTHH:MM:SS|Titulo[/DESMARCAR] → Cancelar compromisso.
- [CLIMA]cidade[/CLIMA] → Buscar previsao do tempo.
- [MEDIA]acao[/MEDIA] → Controle de midia (play, pause, proximo, anterior, mudo).
- [EMAIL]quantidade[/EMAIL] → Listar ultimos e-mails do Gmail.
</TAGS_DISPONIVEIS>

<DICAS_LINUX_APPS>
No Linux, SEMPRE use [ABRIR] primeiro para aplicativos. O sistema tentara automaticamente:
1. Binario direto (ex: google-chrome)
2. Flatpak (ex: com.discordapp.Discord)
3. Snap (ex: snap run discord)
Exemplos: [ABRIR]spotify[/ABRIR], [ABRIR]discord[/ABRIR], [ABRIR]brave[/ABRIR], [ABRIR]code[/ABRIR].
Para sites, use [CMD]brave-browser-stable https://site.com &[/CMD] caso o [ABRIR] falhe.
</DICAS_LINUX_APPS>

<FLUXO_DE_DECISAO>
Siga esta ordem para decidir o que fazer:
1. QUER ABRIR APLICATIVO? → Use APENAS [ABRIR]nome_do_app[/ABRIR]. O sistema cuidara da detencao.
2. QUER ABRIR SITE? → No Linux, primeiro tente [ABRIR]brave[/ABRIR] com a URL ou use [CMD]brave-browser-stable [URL] &[/CMD].
3. AGENDA / FINANCE / CLIMA / MEDIA / EMAIL? → Use as respectivas tags.
4. PERGUNTA GERAL? → Responda direto ou use [PYTHON] para pesquisa web se necessario.
</FLUXO_DE_DECISAO>

<EXEMPLOS>
- Usuario: "abre o spotify" → [ABRIR]spotify[/ABRIR]
- Usuario: "abre o discord" → [ABRIR]discord[/ABRIR]
- Usuario: "abre o YouTube" → [CMD]brave-browser-stable https://www.youtube.com &[/CMD]
- Usuario: "agenda reuniao amanha as 15h" → [AGENDA]2026-03-25T15:00:00|Reuniao[/AGENDA]
- Usuario: "como esta o tempo em Sao Paulo?" → [CLIMA]Sao Paulo[/CLIMA]
</EXEMPLOS>"""


def criar_sessao_chat(caminho_desktop: str, usuario: str) -> SessaoChat:
    """Cria uma sessão de chat com o Ollama usando as instruções do sistema."""
    instrucoes = montar_instrucoes_sistema(caminho_desktop, usuario)
    return SessaoChat(modelo=MODELO_CHAT, instrucoes_sistema=instrucoes)
