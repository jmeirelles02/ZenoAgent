# Zeno System

## O que é o Zeno?
O Zeno é um assistente virtual de operação local. Ele processa comandos de voz e texto para executar tarefas no sistema operacional Windows. O sistema une um back-end construído em Python com uma interface visual desenvolvida em Tauri (HTML/CSS/JS).

A arquitetura funciona como um restaurante. A interface Tauri atua como o salão de atendimento. O servidor Flask em Python funciona como a cozinha. O modelo Google Gemini 2.5 Flash opera como o chef que dita as ações, as buscas na web e as lógicas de Extração, Transformação e Carga (ETL).

O Zeno possui as seguintes funções ativas:
* Executar comandos de sistema e abrir programas.
* Escrever e rodar scripts Python locais automaticamente.
* Consultar dados atualizados na internet.
* Armazenar memória de longo prazo usando PostgreSQL.
* Sintetizar respostas em áudio (Text-to-Speech).

## Configuração de Ambiente (.env)
O sistema exige um arquivo de texto chamado `.env` na pasta raiz do projeto. Este arquivo armazena as credenciais de acesso de forma segura. Você não deve subir este arquivo para o controle de versão (Git).

Crie o arquivo `.env` e declare as seguintes variáveis:

```text
DATABASE_URL=postgresql://usuario:senha@localhost:5432/nome_do_banco
GEMINI_API_KEY=sua_chave_gerada_no_google_ai_studio
```
Detalhamento das Variáveis
DATABASE_URL: Define a rota de conexão com o banco de dados PostgreSQL. O sistema utiliza este banco para salvar e recuperar fatos sobre o usuário e o contexto das tarefas.

GEMINI_API_KEY: Guarda o token de autenticação da API do Google. O motor Python usa esta chave para enviar os dados estruturados e receber o raciocínio do modelo de inteligência artificial.

Como Iniciar
Você aciona o sistema através do inicializador silencioso.

Execute o arquivo zeno_invisivel.vbs.

O script inicia o servidor Flask em segundo plano.

A interface gráfica do Tauri abre na tela após 3 segundos.
