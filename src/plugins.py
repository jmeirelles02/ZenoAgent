"""Sistema de plugins e ferramentas (Native Tool Calling) para o A.R.I.S.

Gera automaticamente schemas de ferramentas no formato Ollama a partir
das assinaturas e docstrings das funções registradas com @aris_tool.
"""

import inspect
import logging
import re
from typing import Any, Callable, get_type_hints

logger = logging.getLogger(__name__)

_TOOL_REGISTRY: dict[str, Callable] = {}

# Mapeamento de tipos Python → tipos JSON Schema
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def aris_tool(func: Callable) -> Callable:
    """Decorator para registrar uma função como ferramenta para o LLM."""
    _TOOL_REGISTRY[func.__name__] = func
    logger.info("Ferramenta registrada: %s", func.__name__)
    return func


def _extrair_descricao_parametro(docstring: str, nome_param: str) -> str:
    """Extrai a descrição de um parâmetro da docstring."""
    if not docstring:
        return f"Parâmetro {nome_param}"
    # Tentar extrair do formato Google-style docstring
    padrao = rf"{nome_param}\s*[:\-]\s*(.+)"
    match = re.search(padrao, docstring)
    if match:
        return match.group(1).strip()
    return f"Parâmetro {nome_param}"


def _gerar_schema_funcao(func: Callable) -> dict[str, Any]:
    """Gera o schema de tool calling para uma função registrada.

    Formato esperado pelo Ollama:
    {
        "type": "function",
        "function": {
            "name": "nome_da_funcao",
            "description": "Docstring da função",
            "parameters": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }
    }
    """
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    docstring = inspect.getdoc(func) or ""

    propriedades: dict[str, Any] = {}
    obrigatorios: list[str] = []

    for nome, param in sig.parameters.items():
        tipo_python = hints.get(nome, str)
        tipo_json = _TYPE_MAP.get(tipo_python, "string")

        propriedades[nome] = {
            "type": tipo_json,
            "description": _extrair_descricao_parametro(docstring, nome),
        }

        # Parâmetros sem default são obrigatórios
        if param.default is inspect.Parameter.empty:
            obrigatorios.append(nome)

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": docstring.split("\n")[0] if docstring else func.__name__,
            "parameters": {
                "type": "object",
                "properties": propriedades,
                "required": obrigatorios,
            },
        },
    }


def obter_schemas_ferramentas() -> list[dict[str, Any]]:
    """Retorna os schemas de todas as ferramentas para passar ao Ollama."""
    return [_gerar_schema_funcao(func) for func in _TOOL_REGISTRY.values()]


def obter_ferramentas() -> list[Callable]:
    """Retorna todas as funções registradas (compatibilidade)."""
    return list(_TOOL_REGISTRY.values())


def executar_ferramenta(nome: str, argumentos: dict) -> Any:
    """Executa uma ferramenta pelo nome com os argumentos fornecidos."""
    if nome in _TOOL_REGISTRY:
        try:
            print(f"\n⚡ [A.R.I.S executando ferramenta: {nome}]")
            for k, v in argumentos.items():
                print(f"  ├─ {k}: {v}")
            resultado = _TOOL_REGISTRY[nome](**argumentos)
            print(f"  └─ Resultado: {resultado}")
            return resultado
        except Exception as e:
            err_msg = f"Erro ao executar {nome}: {str(e)}"
            logger.error(err_msg)
            return err_msg
    return f"Erro: Ferramenta '{nome}' não encontrada."


def listar_ferramentas() -> list[str]:
    """Lista os nomes de todas as ferramentas registradas."""
    return list(_TOOL_REGISTRY.keys())
