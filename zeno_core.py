import ollama
import sys
import os
import subprocess
import re
import pygame

pygame.mixer.init()

def limpar_texto_para_fala(texto):
    texto_limpo = re.sub(r'[*#_]', '', texto)
    return texto_limpo

def falar(texto):
    texto_limpo = limpar_texto_para_fala(texto)
    voz = "pt-BR-AntonioNeural"
    arquivo = "resposta.mp3"
    
    try:
        subprocess.run(["edge-tts", "--voice", voz, "--text", texto_limpo, "--write-media", arquivo])
        
        pygame.mixer.music.load(arquivo)
        pygame.mixer.music.play()
        
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
            
        pygame.mixer.music.unload()
        try:
            os.remove(arquivo)
        except OSError:
            pass
            
    except Exception as e:
        print(f"\n[Erro de Áudio: {e}]")

def iniciar_zeno_core():
    print("--------------------------------------------------")
    print("Zeno Core Iniciado! (Digite 'sair' para encerrar)")
    print("--------------------------------------------------")
    
    mensagens = [
        {
            "role": "system", 
            "content": """Você é o Zeno, uma inteligência artificial que se manifesta como uma molécula brilhante e minimalista de cor roxa e azul claro.
                          Você é prestativo, inteligente, organizado e muito discreto, agindo como um mordomo digital sofisticado.
                          Responda sempre em português do Brasil, de forma clara, direta e concisa. Evite respostas longas demais."""
        }
    ]

    while True:
        try:
            pergunta = input("\nVocê: ")
            
            if pergunta.lower() in ['sair', 'exit', 'quit']:
                despedida = "Desligando meus sistemas. Até breve, senhor."
                print(f"\nZeno: {despedida}")
                falar(despedida)
                break
            if not pergunta.strip():
                continue

            mensagens.append({"role": "user", "content": pergunta})

            sys.stdout.write("Zeno processando...")
            sys.stdout.flush()

            resposta_streaming = ollama.chat(
                model='llama3.2', 
                messages=mensagens,
                stream=True
            )

            sys.stdout.write("\r" + " " * 20 + "\r")
            
            print("Zeno: ", end="")
            texto_resposta_completa = ""
            
            for chunk in resposta_streaming:
                texto_chunk = chunk['message']['content']
                print(texto_chunk, end="", flush=True)
                texto_resposta_completa += texto_chunk
            
            print() 
            
            falar(texto_resposta_completa)

            mensagens.append({"role": "assistant", "content": texto_resposta_completa})

        except KeyboardInterrupt:
            print("\nZeno desligando...")
            sys.exit()
        except Exception as e:
            print(f"\nOcorreu um erro: {e}")

if __name__ == "__main__":
    iniciar_zeno_core()