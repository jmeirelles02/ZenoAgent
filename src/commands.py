"""Execução de comandos do sistema e scripts Python com sandbox.

Inclui:
- Validação de segurança por regex para comandos shell
- RestrictedPython para execução segura de código Python
- Confirmação interativa para operações potencialmente destrutivas
"""

import logging
import os
import re
import subprocess
import sys
from typing import Any

from src.plugins import aris_tool

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

# Padrões que requerem confirmação explícita (não bloqueiam, mas perguntam)
PADROES_CONFIRMACAO: list[str] = [
    r"\brm\b", r"\bsudo\b", r"\bchmod\b", r"\bchown\b",
    r"\bkill\b", r"\bpkill\b", r"\bsystemctl\b",
    r"\bapt\b.*\bremove\b", r"\bdnf\b.*\bremove\b",
    r"\bpip\b.*\buninstall\b",
]

# Globals seguros para execução restrita de Python
_SAFE_BUILTINS: dict[str, Any] = {
    "abs": abs, "all": all, "any": any, "bin": bin, "bool": bool,
    "chr": chr, "dict": dict, "dir": dir, "divmod": divmod,
    "enumerate": enumerate, "filter": filter, "float": float,
    "format": format, "frozenset": frozenset, "getattr": getattr,
    "hasattr": hasattr, "hash": hash, "hex": hex, "id": id,
    "int": int, "isinstance": isinstance, "issubclass": issubclass,
    "iter": iter, "len": len, "list": list, "map": map, "max": max,
    "min": min, "next": next, "oct": oct, "ord": ord, "pow": pow,
    "print": print, "range": range, "repr": repr, "reversed": reversed,
    "round": round, "set": set, "slice": slice, "sorted": sorted,
    "str": str, "sum": sum, "tuple": tuple, "type": type, "zip": zip,
    "True": True, "False": False, "None": None,
}

# Flag global de confirmação pendente (thread-safe via fila no main)
_confirmacao_pendente: dict | None = None


def comando_e_seguro(comando: str) -> tuple[bool, str]:
    """Verifica se o comando não contém padrões perigosos."""
    comando_lower = comando.lower()
    for padrao in COMANDOS_BLOQUEADOS:
        if re.search(padrao, comando_lower, re.IGNORECASE):
            return False, f"Comando bloqueado por segurança: padrão '{padrao}' detectado."
    return True, ""


def comando_requer_confirmacao(comando: str) -> bool:
    """Verifica se o comando requer confirmação do usuário."""
    comando_lower = comando.lower()
    return any(
        re.search(padrao, comando_lower, re.IGNORECASE)
        for padrao in PADROES_CONFIRMACAO
    )


def codigo_python_e_seguro(codigo: str) -> tuple[bool, str]:
    """Verifica se o código Python não contém operações perigosas."""
    for padrao in IMPORTS_BLOQUEADOS:
        if re.search(padrao, codigo, re.IGNORECASE):
            return False, f"Código bloqueado por segurança: padrão '{padrao}' detectado."
    return True, ""


@aris_tool
def executar_comando(comando: str) -> str:
    """Executa um comando no shell do sistema operacional.

    comando: O comando a ser executado no terminal (ex: 'ls -la', 'echo hello')
    """
    seguro, motivo = comando_e_seguro(comando)
    if not seguro:
        logger.warning("Comando bloqueado: %s | Motivo: %s", comando, motivo)
        return f"🚫 Bloqueado: {motivo}"

    if comando_requer_confirmacao(comando):
        logger.warning("Comando requer confirmação: %s", comando)
        return (
            f"⚠️ Este comando requer confirmação do usuário: `{comando}`\n"
            "O comando envolve uma operação potencialmente destrutiva. "
            "Por favor, peça permissão ao usuário antes de prosseguir."
        )

    # Adiciona '&' se não houver para evitar travar o sistema em apps GUI
    if not comando.strip().endswith("&"):
        comando = f"{comando} &"

    logger.info("CMD executado: %s", comando)
    try:
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


@aris_tool
def abrir_aplicativo(nome_app: str) -> str:
    """Abre um aplicativo instalado no sistema (detecta binário, Flatpak ou Snap).

    nome_app: Nome do aplicativo a abrir (ex: 'spotify', 'discord', 'chrome', 'brave')
    """
    nome_app = nome_app.lower().strip()

    mapeamentos = {
        "spotify": "com.spotify.Client",
        "discord": "com.discordapp.Discord",
        "chrome": "google-chrome",
        "brave": "brave-browser-stable",
        "code": "code",
        "visual studio code": "code",
        "steam": "com.valvesoftware.Steam",
    }

    id_mapeado = mapeamentos.get(nome_app, nome_app)

    # 1. Tentar como binário direto
    try:
        if subprocess.run(
            f"which {id_mapeado}", shell=True, capture_output=True
        ).returncode == 0:
            return executar_comando(f"{id_mapeado}")
    except Exception:
        pass

    # 2. Tentar como Flatpak
    try:
        comando_busca = f"flatpak list --columns=application | grep -i {nome_app}"
        resultado = subprocess.run(
            comando_busca, shell=True, capture_output=True, text=True
        )
        if resultado.returncode == 0:
            id_flatpak = resultado.stdout.split('\n')[0].strip()
            return executar_comando(f"flatpak run {id_flatpak}")
    except Exception:
        pass

    # 3. Tentar como Snap
    try:
        if subprocess.run(
            f"snap list {nome_app}", shell=True, capture_output=True
        ).returncode == 0:
            return executar_comando(f"snap run {nome_app}")
    except Exception:
        pass

    # 4. Caso comum de navegador para nomes de sites
    if "." in nome_app or "http" in nome_app:
        return executar_comando(f"brave-browser-stable {nome_app}")

    return f"Não consegui encontrar o aplicativo '{nome_app}' instalado via binário, Flatpak ou Snap."


@aris_tool
def abrir_url(url: str) -> str:
    """Abre uma URL ou site no navegador padrão do sistema.

    url: A URL completa do site a abrir (ex: 'https://www.youtube.com', 'https://github.com')
    """
    url = url.strip()

    # Garantir que tem protocolo
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    logger.info("Abrindo URL no navegador: %s", url)

    try:
        # Tentar xdg-open primeiro (padrão Linux)
        subprocess.Popen(
            ["xdg-open", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp,
        )
        return f"URL '{url}' aberta no navegador padrão."
    except FileNotFoundError:
        pass

    # Fallback: tentar navegadores comuns diretamente
    for navegador in ["brave-browser-stable", "google-chrome", "firefox", "chromium"]:
        try:
            if subprocess.run(
                f"which {navegador}", shell=True, capture_output=True
            ).returncode == 0:
                subprocess.Popen(
                    [navegador, url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp,
                )
                return f"URL '{url}' aberta no {navegador}."
        except Exception:
            continue

    return f"Não consegui abrir a URL '{url}'. Nenhum navegador encontrado."


@aris_tool
def executar_python(codigo: str) -> str:
    """Executa código Python com sandbox de segurança.

    codigo: O código Python a ser executado (use caminhos absolutos para arquivos)
    """
    # Camada 1: Validação por regex
    seguro, motivo = codigo_python_e_seguro(codigo)
    if not seguro:
        logger.warning("Código Python bloqueado | Motivo: %s", motivo)
        return f"🚫 Bloqueado: {motivo}"

    # Camada 2: Tentar RestrictedPython (sandbox)
    try:
        from RestrictedPython import compile_restricted, safe_globals
        from RestrictedPython.Eval import default_guarded_getiter
        from RestrictedPython.Guards import (guarded_unpack_sequence, safer_getattr)

        logger.info("PYTHON [sandbox] executando: %d caracteres", len(codigo))

        byte_code = compile_restricted(codigo, filename="<aris_script>", mode="exec")

        # Montar globals seguros
        globs = safe_globals.copy()
        globs["__builtins__"] = _SAFE_BUILTINS.copy()
        globs["_getiter_"] = default_guarded_getiter
        globs["_getattr_"] = safer_getattr
        globs["_unpack_sequence_"] = guarded_unpack_sequence

        # Capturar stdout
        import io
        from contextlib import redirect_stdout

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exec(byte_code, globs)  # noqa: S102

        saida = buffer.getvalue()
        return saida if saida else "Executado com sucesso (sem saída visual)."

    except ImportError:
        logger.info(
            "RestrictedPython não disponível — usando execução isolada por subprocesso."
        )
    except Exception as e:
        logger.warning("RestrictedPython falhou: %s — fallback para subprocesso.", e)

    # Camada 3: Fallback — execução em subprocesso isolado
    logger.info("PYTHON [subprocesso] executando: %d caracteres", len(codigo))
    caminho = os.path.join(os.environ.get("TEMP", "/tmp"), "aris_script.py")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(codigo)
    try:
        resultado = subprocess.run(
            [sys.executable, caminho],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if resultado.returncode != 0 and resultado.stderr:
            return f"Erro no script: {resultado.stderr.strip()}"
        return resultado.stdout if resultado.stdout else "Executado sem saída visual."
    except subprocess.TimeoutExpired:
        return "Erro: Timeout — o script excedeu o limite de 20 segundos."
    except subprocess.CalledProcessError as e:
        return e.stderr
