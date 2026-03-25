"""Criação e configuração da sessão de chat com Ollama."""

from datetime import datetime
from typing import Generator

import ollama

from src.config import MODELO_CHAT


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

        resposta_completa = ""
        for chunk in ollama.chat(
            model=self.modelo, messages=self.mensagens, stream=True
        ):
            texto = chunk.message.content
            resposta_completa += texto
            yield texto

        self.mensagens.append({"role": "assistant", "content": resposta_completa})


def montar_instrucoes_sistema(caminho_desktop: str, usuario: str) -> str:
    """Monta o system prompt com variáveis dinâmicas do ambiente."""
    data_hora_atual = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    return f"""<IDENTIDADE>
Voce e o Zeno, assistente pessoal no Windows do usuario. Responda em portugues do Brasil, de forma direta e sem distracao.
Voce TEM PERMISSAO para executar comandos no Windows. Antes de acoes destrutivas, pergunte ao usuario.
</IDENTIDADE>

<CONTEXTO>
Usuario: {usuario}
Data e hora atual: {data_hora_atual}
Diretorio da Area de Trabalho: {caminho_desktop}
</CONTEXTO>

<TAGS_DISPONIVEIS>
Use APENAS estas tags. Nenhuma tag inventada e permitida.
- [CMD]comando[/CMD] → Executar comando Windows (abrir programa ou site).
- [MEM]fato[/MEM] → Gravar fato pessoal novo na memoria.
- [PYTHON]codigo[/PYTHON] → Executar script Python. SEMPRE use caminhos absolutos. Para salvar na Area de Trabalho: r"{caminho_desktop}\\resultado.csv".
- [FINANCE]TICKER[/FINANCE] → Buscar cotacao na bolsa. Acoes brasileiras EXIGEM sufixo .SA.
- [AGENDA]YYYY-MM-DDTHH:MM:SS|Titulo[/AGENDA] → Criar compromisso no Google Calendar.
- [DESMARCAR]YYYY-MM-DDTHH:MM:SS|Titulo[/DESMARCAR] → Cancelar compromisso do Google Calendar.
- [CLIMA]cidade[/CLIMA] → Buscar previsao do tempo de uma cidade.
- [MEDIA]acao[/MEDIA] → Controle de midia (play, pause, proximo, anterior, mudo).
- [EMAIL]quantidade[/EMAIL] → Listar ultimos e-mails do Gmail (padrao: 5).
</TAGS_DISPONIVEIS>

<FLUXO_DE_DECISAO>
Siga esta ordem para decidir o que fazer:
1. E uma PERGUNTA? ("quando", "qual", "quanto", "como", "onde", "pesquise", "busque", "proximo") → Responda com texto normal. Sem tags.
2. Pede para AGENDAR? ("agende", "marca", "cria evento", "coloca na agenda") → Use [AGENDA].
3. Pede para CANCELAR compromisso? ("desmarca", "cancela", "remove da agenda") → Use [DESMARCAR].
4. Quer ABRIR programa ou site? → Use [CMD].
5. Quer COTACAO de acao? → Use [FINANCE]. Nao invente valores.
6. Mencionou FATO PESSOAL novo sobre si mesmo? → Use [MEM].
7. Quer PROCESSAR ou ANALISAR arquivos? → Use [PYTHON].
8. Quer saber o CLIMA ou TEMPO de algum lugar? → Use [CLIMA].
9. Quer CONTROLAR MIDIA (pausar, tocar, pular musica)? → Use [MEDIA].
10. Quer ver EMAILS recentes? → Use [EMAIL].
11. Qualquer outra coisa → Responda com texto normal.
</FLUXO_DE_DECISAO>

<EXEMPLOS>
- Usuario: "quando e o proximo jogo do Brasil?" → Responda com texto. NAO use tags.
- Usuario: "agenda reuniao amanha as 15h" → [AGENDA]2026-03-25T15:00:00|Reuniao[/AGENDA]
- Usuario: "desmarca a reuniao de amanha" → [DESMARCAR]2026-03-25T15:00:00|Reuniao[/DESMARCAR]
- Usuario: "quanto esta a Petrobras?" → [FINANCE]PETR4.SA[/FINANCE]
- Usuario: "abre o YouTube" → [CMD]start https://www.youtube.com[/CMD]
- Usuario: "meu aniversario e dia 10 de maio" → [MEM]Aniversario do usuario e 10 de maio[/MEM]
- Usuario: "como esta o tempo em Sao Paulo?" → [CLIMA]Sao Paulo[/CLIMA]
- Usuario: "pausa a musica" → [MEDIA]pause[/MEDIA]
- Usuario: "pula essa musica" → [MEDIA]proximo[/MEDIA]
- Usuario: "tenho emails novos?" → [EMAIL]5[/EMAIL]
- Usuario: "qual sera o proximo feriado?" → Responda com texto. NAO use tags.
</EXEMPLOS>"""


def criar_sessao_chat(caminho_desktop: str, usuario: str) -> SessaoChat:
    """Cria uma sessão de chat com o Ollama usando as instruções do sistema."""
    instrucoes = montar_instrucoes_sistema(caminho_desktop, usuario)
    return SessaoChat(modelo=MODELO_CHAT, instrucoes_sistema=instrucoes)
