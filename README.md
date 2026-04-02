# A.R.I.S (ARTIFICIAL REACTIVE INTELLIGENT SYSTEM)

## O que é o A.R.I.S?

O A.R.I.S é um assistente virtual de operação local. Ele processa comandos de voz e texto para executar tarefas no sistema operacional. O sistema une um back-end construído em Python (FastAPI + Ollama) com uma interface visual desenvolvida em Tauri (HTML/CSS/JS).

O ARIS possui as seguintes funções ativas:

- Executar comandos de sistema e abrir programas (binário, Flatpak, Snap).
- Escrever e rodar scripts Python locais automaticamente.
- Consultar dados atualizados na internet (DuckDuckGo).
- Armazenar memória de longo prazo usando busca vetorial (RAG) com pgvector e embeddings via Ollama.
- Sintetizar respostas em áudio (Text-to-Speech via edge-tts).
- Detecção de wake word offline (Vosk).
- Integração com Google Calendar e Gmail.
- Consulta de cotações financeiras (Yahoo Finance).
- Previsão do tempo (Open-Meteo).
- Controle de mídia do sistema.
- Monitoramento de CPU, RAM, disco e bateria.

## Configuração de Ambiente (.env)

O sistema exige um arquivo de texto chamado `.env` na pasta raiz do projeto. Este arquivo armazena as credenciais de acesso de forma segura. Você não deve subir este arquivo para o controle de versão (Git).

Crie o arquivo `.env` e declare as seguintes variáveis:

```text
DATABASE_URL=postgresql://usuario:senha@localhost:5432/nome_do_banco
```

### Detalhamento das Variáveis

- **DATABASE_URL**: Define a rota de conexão com o banco de dados PostgreSQL (pgvector). O sistema utiliza este banco para salvar e recuperar fatos sobre o usuário via busca vetorial (RAG).

### Dependências Externas

- **Ollama** (local): O modelo de linguagem roda localmente via Ollama. Instale o Ollama e baixe o modelo configurado em `src/config.py` (padrão: `qwen2.5:latest`).
- **PostgreSQL com pgvector**: Banco de dados para memória de longo prazo.
- **Google OAuth** (opcional): Para integração com Google Calendar e Gmail, configure o `credentials.json`.

## Como Iniciar

### Linux

1. Execute o setup: `./setup.sh`
2. Inicie o sistema: `./iniciar.sh`

O script inicia o backend FastAPI em segundo plano e abre a interface gráfica do Tauri.
