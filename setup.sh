#!/bin/bash
echo ">> Instalando dependências de sistema (pode pedir senha sudo)..."
sudo apt update
sudo apt install -y python3-venv python3-dev portaudio19-dev cmake pkg-config build-essential nodejs npm unzip \
  curl wget file libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev libwebkit2gtk-4.1-dev

echo ">> Instalando Rust (latest) via rustup..."
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"

echo ">> Criando ambiente virtual Python (venv)..."
python3 -m venv venv

echo ">> Baixando modelo de Reconhecimento de Voz Offline (Vosk)..."
if [ ! -d "vosk-model-small-pt-0.3" ]; then
    wget https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip
    unzip -n vosk-model-small-pt-0.3.zip
    rm vosk-model-small-pt-0.3.zip
else
    echo ">> Modelo Vosk já baixado."
fi

echo ">> Ativando venv e instalando libs Python..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ">> Instalando dependências do Agent-ui..."
cd Agent-ui
npm install

echo ">> Setup concluído! Para iniciar, execute ./iniciar.sh"
