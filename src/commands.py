"""Execução de comandos do sistema e scripts Python."""

import logging
import os
import re
import subprocess
import sys

logger = logging.getLogger(__name__)

COMANDOS_BLOQUEADOS: list[str] = [
    r"\bdel\b", r"\brmdir\b", r"\brd\b", r"\bformat\b",
    r"\bshutdown\b", r"\brestart\b", r"\breg\b\s+(delete|add)",
    r"\bnet\s+user\b", r"\bnet\s+localgroup\b",
    r"\btakeown\b", r"\bicacls\b",
    r"powershell\s+-enc", r"powershell\s+-e\b",
    r"\brm\s+-rf\b", r"\bmkfs\b",
    r"Invoke-WebRequest", r"Invoke-RestMethod",
    r"DownloadString", r"DownloadFile",
    r"\bcertutil\b.*-urlcache",
    r"\bwmic\b.*delete", r"\bwmic\b.*call\s+terminate",
    r"\btaskkill\b",
]

IMPORTS_BLOQUEADOS: list[str] = [
    r"\bimport\s+shutil\b", r"\bshutil\.rmtree\b",
    r"\bos\.remove\b", r"\bos\.rmdir\b", r"\bos\.unlink\b",
    r"\bos\.system\b", r"\bsubprocess\b",
    r"\bimport\s+socket\b", r"\bimport\s+http\b",
    r"\bimport\s+urllib\b", r"\bimport\s+requests\b",
    r"\bopen\s*\(.*,\s*['\"]w['\"]", r"\bpathlib\.Path.*unlink\b",
]


def comando_e_seguro(comando: str) -> tuple[bool, str]:
    """Verifica se o comando não contém padrões perigosos."""
    comando_lower = comando.lower()
    for padrao in COMANDOS_BLOQUEADOS:
        if re.search(padrao, comando_lower, re.IGNORECASE):
            return False, f"Comando bloqueado por segurança: padrão '{padrao}' detectado."
    return True, ""


def codigo_python_e_seguro(codigo: str) -> tuple[bool, str]:
    """Verifica se o código Python não contém operações perigosas."""
    for padrao in IMPORTS_BLOQUEADOS:
        if re.search(padrao, codigo, re.IGNORECASE):
            return False, f"Código bloqueado por segurança: padrão '{padrao}' detectado."
    return True, ""


def executar_comando(comando: str) -> str:
    """Executa um comando no shell com validação de segurança e suporte a background."""
    seguro, motivo = comando_e_seguro(comando)
    if not seguro:
        logger.warning("Comando bloqueado: %s | Motivo: %s", comando, motivo)
        return f"Bloqueado: {motivo}"

    # Adiciona '&' se não houver para evitar travar o sistema em apps GUI
    if not comando.strip().endswith("&"):
        comando = f"{comando} &"

    logger.info("CMD executado: %s", comando)
    try:
        # Usamos Popen para não bloquear o assistente enquanto o app está aberto
        subprocess.Popen(
            comando,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp if os.name != 'nt' else None
        )
        return "Comando enviado para execução em segundo plano."
    except Exception as e:
        return f"Erro ao executar comando: {str(e)}"


def abrir_aplicativo(nome_app: str) -> str:
    """Tenta localizar e abrir um aplicativo no Linux (Binário, Flatpak ou Snap)."""
    nome_app = nome_app.lower().strip()
    
    # Lista de mapeamentos conhecidos (IDs de flatpak comum)
    mapeamentos = {
        "spotify": "com.spotify.Client",
        "discord": "com.discordapp.Discord",
        "chrome": "google-chrome",
        "brave": "brave-browser-stable",
        "code": "code",
        "visual studio code": "code",
        "steam": "com.valvesoftware.Steam"
    }
    
    id_mapeado = mapeamentos.get(nome_app, nome_app)

    # 1. Tentar como binário direto
    try:
        if subprocess.run(f"which {id_mapeado}", shell=True, capture_output=True).returncode == 0:
            return executar_comando(f"{id_mapeado}")
    except Exception:
        pass

    # 2. Tentar como Flatpak
    try:
        # Busca o ID exato no flatpak list
        comando_busca = f"flatpak list --columns=application | grep -i {nome_app}"
        resultado = subprocess.run(comando_busca, shell=True, capture_output=True, text=True)
        if resultado.returncode == 0:
            id_flatpak = resultado.stdout.split('\n')[0].strip()
            return executar_comando(f"flatpak run {id_flatpak}")
    except Exception:
        pass

    # 3. Tentar como Snap
    try:
        if subprocess.run(f"snap list {nome_app}", shell=True, capture_output=True).returncode == 0:
            return executar_comando(f"snap run {nome_app}")
    except Exception:
        pass

    # 4. Caso comum de navegador para nomes de sites
    if "." in nome_app or "http" in nome_app:
        return executar_comando(f"brave-browser-stable {nome_app}")

    return f"Não consegui encontrar o aplicativo '{nome_app}' instalado via binário, Flatpak ou Snap."


def executar_python(codigo: str) -> str:
    """Salva e executa um script Python temporário com validação de segurança."""
    seguro, motivo = codigo_python_e_seguro(codigo)
    if not seguro:
        logger.warning("Código Python bloqueado | Motivo: %s", motivo)
        return f"Bloqueado: {motivo}"

    logger.info("PYTHON executado: %d caracteres", len(codigo))
    caminho = os.path.join(os.environ.get("TEMP", os.getcwd()), "aris_script.py")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(codigo)
    try:
        resultado = subprocess.run(
            [sys.executable, caminho],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return resultado.stdout if resultado.stdout else "Executado sem saida visual."
    except subprocess.TimeoutExpired:
        return "Erro de Timeout."
    except subprocess.CalledProcessError as e:
        return e.stderr
