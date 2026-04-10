#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || { echo "Erro: não foi possível entrar no diretório $SCRIPT_DIR"; read -p "Pressione Enter para sair..."; exit 1; }

echo ">> Iniciando A.R.I.S no modo Linux..."

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Erro: venv não encontrado. Execute ./setup.sh primeiro."
    read -p "Pressione Enter para sair..."
    exit 1
fi

python3 main.py &
BACKEND_PID=$!

sleep 3

# Caso o Rust não esteja no PATH
if [ -f "$HOME/.cargo/env" ]; then
    source "$HOME/.cargo/env"
fi

cd Agent-ui
npm run tauri dev
TAURI_EXIT=$?

kill $BACKEND_PID 2>/dev/null

if [ $TAURI_EXIT -ne 0 ]; then
    echo ""
    echo "========================================"
    echo " A.R.I.S encerrou com erro (código $TAURI_EXIT)"
    echo "========================================"
    read -p "Pressione Enter para fechar..."
fi
