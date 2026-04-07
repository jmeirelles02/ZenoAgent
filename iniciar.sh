#!/bin/bash
echo ">> Iniciando A.R.I.S no modo Linux..."

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Erro: venv não encontrado. Execute ./setup.sh primeiro."
    exit 1
fi

python3 main.py &
BACKEND_PID=$!

sleep 3

# Carregar novo compilador Rust (rustup) caso exista
if [ -f "$HOME/.cargo/env" ]; then
    source "$HOME/.cargo/env"
fi

cd Agent-ui
npm run tauri dev

kill $BACKEND_PID
