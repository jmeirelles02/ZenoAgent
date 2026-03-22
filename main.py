import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pygame")

import os
import sys
import subprocess
import re
import pygame
import speech_recognition as sr
from google import genai
from google.genai import types
import threading
import psycopg2
from flask import Flask, jsonify, request
from flask_cors import CORS
from ddgs import DDGS
import keyboard
from dotenv import load_dotenv
import queue

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
cliente_gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

pygame.mixer.init()

estado_zeno = {
    "status": "ONLINE",
    "usuario": "Aguardando comando...",
    "zeno": "Sistemas iniciados."
}

fila_comandos = queue.Queue()

app = Flask(__name__)
CORS(app)

@app.route('/estado', methods=['GET'])
def estado():
    return jsonify(estado_zeno)

@app.route('/enviar', methods=['POST'])
def receber_comando():
    dados = request.json
    comando = dados.get('comando', '')
    if comando:
        if comando == "[CANCELAR]":
            pygame.mixer.music.stop()
            with fila_comandos.mutex:
                fila_comandos.queue.clear()
        elif comando == "[VOZ]":
            with fila_comandos.mutex:
                fila_comandos.queue.clear()
            fila_comandos.put(comando)
        else:
            fila_comandos.put(comando)
    return jsonify({"status": "recebido"})

def rodar_servidor():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(port=5000, debug=False, use_reloader=False)

def inicializar_banco():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memoria (
            id SERIAL PRIMARY KEY,
            usuario TEXT,
            informacao TEXT,
            vetor vector(768)
        )
    ''')
    conn.commit()
    conn.close()

def gerar_embedding(texto):
    resultado = cliente_gemini.models.embed_content(
        model="text-multilingual-embedding-002",
        contents=texto
    )
    return resultado.embeddings[0].values

def salvar_memoria(usuario, informacao):
    vetor = gerar_embedding(informacao)
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO memoria (usuario, informacao, vetor) VALUES (%s, %s, %s)', 
        (usuario, informacao, str(vetor))
    )
    conn.commit()
    conn.close()

def buscar_memoria_relevante(pergunta, limite=3):
    try:
        vetor_pergunta = gerar_embedding(pergunta)
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT informacao FROM memoria ORDER BY vetor <=> %s::vector LIMIT %s",
            (str(vetor_pergunta), limite)
        )
        resultados = cursor.fetchall()
        conn.close()
        if resultados:
            return "\n".join([f"* {r[0]}" for r in resultados])
        return ""
    except Exception as e:
        print(f"\n[Aviso de Memoria: Tabela vazia ou erro de RAG: {e}]")
        return ""

def executar_comando(comando):
    try:
        resultado = subprocess.run(comando, shell=True, check=True, capture_output=True, text=True, timeout=15)
        return resultado.stdout
    except subprocess.TimeoutExpired:
        return "Erro: O comando bloqueou o sistema e foi cancelado por tempo excedido."
    except subprocess.CalledProcessError as erro:
        return erro.stderr

def executar_python(codigo):
    caminho = os.path.join(os.environ.get('TEMP', os.getcwd()), 'zeno_script.py')
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write(codigo)
    try:
        resultado = subprocess.run([sys.executable, caminho], capture_output=True, text=True, timeout=20)
        return resultado.stdout if resultado.stdout else "Executado sem saida visual."
    except subprocess.TimeoutExpired:
        return "Erro de Timeout."
    except subprocess.CalledProcessError as e:
        return e.stderr

def processar_tags_ocultas(texto, usuario_atual):
    comandos = re.findall(r'\[CMD\](.*?)\[/CMD\]', texto, flags=re.DOTALL)
    for cmd in comandos:
        print(f"\n[Executando comando: {cmd.strip()}]")
        saida = executar_comando(cmd.strip())
        if saida:
            print(f"[Saida do Sistema]: {saida.strip()}")

    blocos_python = re.findall(r'\[PYTHON\](.*?)\[/PYTHON\]', texto, flags=re.DOTALL)
    for codigo in blocos_python:
        print(f"\n[Executando rotina de dados em Python...]")
        saida = executar_python(codigo.strip())
        if saida:
            print(f"[Saida do Script]:\n{saida.strip()}")
            
    memorias = re.findall(r'\[MEM\](.*?)\[/MEM\]', texto)
    for mem in memorias:
        print(f"\n[Gravando na memoria: {mem}]")
        salvar_memoria(usuario_atual, mem)

def limpar_texto_para_fala(texto):
    texto_limpo = re.sub(r'\[CMD\].*?\[/CMD\]', '', texto, flags=re.DOTALL)
    texto_limpo = re.sub(r'\[MEM\].*?\[/MEM\]', '', texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r'\[PYTHON\].*?\[/PYTHON\]', '', texto_limpo, flags=re.DOTALL)
    texto_limpo = re.sub(r'[*#_]', '', texto_limpo)
    return texto_limpo

def falar(texto):
    global estado_zeno
    texto_limpo = limpar_texto_para_fala(texto)
    if not texto_limpo.strip():
        return
        
    estado_zeno["status"] = "FALANDO..."
    voz = "pt-BR-AntonioNeural"
    arquivo = "resposta.mp3"
    
    try:
        subprocess.run(["edge-tts", "--voice", voz, "--text", texto_limpo, "--write-media", arquivo])
        pygame.mixer.music.load(arquivo)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            if keyboard.is_pressed('space'):
                pygame.mixer.music.stop()
                print("\n[Zeno interrompido]")
                break
            pygame.time.Clock().tick(10)
            
        pygame.mixer.music.unload()
        if os.path.exists(arquivo):
            os.remove(arquivo)
    except Exception as e:
        print(f"\n[Erro de Audio: {e}]")

def ouvir():
    global estado_zeno
    reconhecedor = sr.Recognizer()
    reconhecedor.pause_threshold = 2.0
    with sr.Microphone() as fonte:
        estado_zeno["status"] = "OUVINDO..."
        print("\n[Zeno ouvindo...]")
        reconhecedor.adjust_for_ambient_noise(fonte, duration=0.5)
        try:
            audio = reconhecedor.listen(fonte, timeout=5)
            texto = reconhecedor.recognize_google(audio, language='pt-BR')
            print(f"Voce (Voz): {texto}")
            return texto
        except sr.WaitTimeoutError:
            return ""
        except sr.UnknownValueError:
            return ""
        except Exception:
            return ""

def obter_caminho_desktop():
    caminho_usuario = os.environ.get('USERPROFILE') or os.path.expanduser('~')
    caminhos = [
        os.path.join(caminho_usuario, 'OneDrive', 'Área de Trabalho'),
        os.path.join(caminho_usuario, 'OneDrive', 'Desktop'),
        os.path.join(caminho_usuario, 'Desktop'),
        os.path.join(caminho_usuario, 'Área de Trabalho')
    ]
    for caminho in caminhos:
        if os.path.exists(caminho):
            return caminho
    return os.path.join(caminho_usuario, 'Desktop')

def buscar_na_internet(consulta):
    try:
        resultados = DDGS().text(consulta, region='br-pt', timelimit='w', max_results=3)
        if not resultados:
            resultados = DDGS().text(consulta, region='br-pt', timelimit='m', max_results=3)
        if not resultados:
            return "Nenhuma informacao recente encontrada."
        
        texto_compilado = "Dados extraidos da internet:\n"
        for r in resultados:
            texto_compilado += f"* Titulo: {r['title']}\n  Resumo: {r['body']}\n"
        return texto_compilado
    except Exception as e:
        return f"Falha na conexao com a rede externa: {e}"

def iniciar_zeno_core():
    global estado_zeno
    print("==================================================")
    print("Zeno System Iniciado. Conectado ao Google Gemini.")
    print("==================================================")
    
    inicializar_banco()
    thread_servidor = threading.Thread(target=rodar_servidor, daemon=True)
    thread_servidor.start()

    caminho_desktop = obter_caminho_desktop()
    usuario_db = "Joao"

    instrucoes_sistema = f"""Voce e o Zeno, um assistente virtual de elite.
Voce TEM PERMISSAO PARCIAL para executar comandos no Windows do usuario. NUNCA diga que nao pode abrir programas.
O diretorio da Area de Trabalho e: {caminho_desktop}

MEMORIA DE CONTEXTO PESSOAL:
Nome do usuario atual na sessao: {usuario_db}

REGRAS OBRIGATORIAS DE MEMORIA:
1. Grave fatos novos em tags separadas usando EXCLUSIVAMENTE [MEM] e [/MEM]. 
2. PROIBICAO ABSOLUTA: NUNCA crie tags inventadas.

REGRAS PARA USO DE COMANDOS:
1. Para abrir programas, forneca o comando APENAS dentro de [CMD] e [/CMD].
2. Exemplo: [CMD]start https://www.youtube.com[/CMD].

REGRAS PARA PROCESSAMENTO DE DADOS (ETL):
1. Escreva o codigo Python exato dentro de [PYTHON] e [/PYTHON].
2. SEMPRE use caminhos absolutos para ler arquivos.
3. OBRIGATORIO: Para salvar arquivos na Area de Trabalho, use EXATAMENTE a string r"{caminho_desktop}\\resultado.csv" dentro do script.
4. NUNCA use caminhos relativos.

COMUNICACAO:
Responda em portugues do Brasil de forma direta e sem firulas. NUNCA imprima o seu raciocinio de etapas na tela."""

    configuracao_chat = types.GenerateContentConfig(
        system_instruction=instrucoes_sistema,
    )
    
    chat = cliente_gemini.chats.create(model="gemini-3.1-flash-lite-preview", config=configuracao_chat)

    while True:
        try:
            estado_zeno["status"] = "ONLINE"
            
            try:
                entrada = fila_comandos.get(timeout=1.0)
            except queue.Empty:
                continue
            
            if entrada.lower() in ['sair', 'exit', 'quit', 'fechar', 'desligar']:
                estado_zeno["status"] = "DESLIGANDO..."
                falar("Encerrando protocolos. Ate a proxima, senhor.")
                break
            
            if entrada == "[VOZ]":
                pergunta = ouvir()
                if pergunta == "":
                    continue
            else:
                pergunta = entrada

            estado_zeno["usuario"] = pergunta
            
            dados_web = ""
            gatilhos_pesquisa = [
                "pesquise", "busque", "internet", "resultado", "último", "hoje", 
                "notícia", "preço", "valor", "cotação", "quanto custa", "atual", "mercado"
            ]
            
            if any(g in pergunta.lower() for g in gatilhos_pesquisa):
                estado_zeno["status"] = "BUSCANDO NA REDE..."
                dados_web = buscar_na_internet(pergunta)
                
            estado_zeno["status"] = "RECUPERANDO DADOS..."
            contexto_memoria = buscar_memoria_relevante(pergunta)
            
            pergunta_formatada = pergunta
            
            if dados_web:
                pergunta_formatada = f"Resultados da web:\n{dados_web}\n\nPergunta: {pergunta_formatada}\nInstrução: Responda de forma direta usando APENAS os dados da web. NUNCA invente valores."
                
            if contexto_memoria:
                pergunta_formatada = f"Contexto salvo no banco de dados (use apenas se for relevante):\n{contexto_memoria}\n\n{pergunta_formatada}"

            estado_zeno["status"] = "PENSANDO..."
            
            resposta_streaming = chat.send_message_stream(pergunta_formatada)
            
            texto_resposta_completa = ""
            print("Zeno: ", end="")
            for chunk in resposta_streaming:
                if chunk.text:
                    texto_chunk = chunk.text
                    print(texto_chunk, end="", flush=True)
                    texto_resposta_completa += texto_chunk
            print()
            
            estado_zeno["zeno"] = limpar_texto_para_fala(texto_resposta_completa)
            
            processar_tags_ocultas(texto_resposta_completa, usuario_db)
            falar(texto_resposta_completa)

        except KeyboardInterrupt:
            sys.exit()
        except Exception as e:
            print(f"\nOcorreu um erro: {e}")

if __name__ == "__main__":
    iniciar_zeno_core()