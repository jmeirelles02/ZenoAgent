"""Consulta de previsao do tempo via Open-Meteo."""

from src.plugins import aris_tool
import logging
import requests

logger = logging.getLogger(__name__)

# Codigos WMO para condicoes climaticas basicas em portugues
WMO_CODES = {
    0: "Ceu limpo", 1: "Maior parte limpo", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Nevoeiro", 48: "Nevoeiro com geada", 51: "Chuvisco leve", 53: "Chuvisco",
    55: "Chuvisco forte", 61: "Chuva leve", 63: "Chuva moderada", 65: "Chuva forte",
    66: "Chuva congelante leve", 67: "Chuva congelante forte",
    71: "Neve leve", 73: "Neve moderada", 75: "Neve forte", 77: "Graos de neve",
    80: "Pancadas de chuva leve", 81: "Pancadas de chuva moderada", 82: "Pancadas de chuva forte",
    85: "Pancadas de neve leve", 86: "Pancadas de neve forte",
    95: "Trovoada", 96: "Trovoada com granizo leve", 99: "Trovoada com granizo forte"
}

@aris_tool
def buscar_clima(cidade: str) -> str:
    """Busca a previsão do tempo atual para a cidade informada.

    cidade: Nome da cidade para consultar o clima (ex: 'São Paulo', 'Rio de Janeiro')
    """
    try:
        # Primeiro, usamos a geocoding API para pegar as cordenadas da cidade
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={cidade}&count=1&language=pt&format=json"
        geo_res = requests.get(geo_url, timeout=10)
        geo_res.raise_for_status()
        geo_data = geo_res.json()
        
        if not geo_data.get("results"):
            return f"Nao encontrei dados de clima para '{cidade}'."
            
        lat = geo_data["results"][0]["latitude"]
        lon = geo_data["results"][0]["longitude"]
        nome_real = geo_data["results"][0]["name"]
        
        # Agora buscamos o clima atual
        weather_url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                       f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code&timezone=auto")
        weather_res = requests.get(weather_url, timeout=10)
        weather_res.raise_for_status()
        
        current = weather_res.json().get("current", {})
        temp = current.get("temperature_2m", "")
        umid = current.get("relative_humidity_2m", "")
        vento = current.get("wind_speed_10m", "")
        codigo = current.get("weather_code")
        condicao = WMO_CODES.get(codigo, "Desconhecido")
        
        return f"Clima em {nome_real}: {condicao}, {temp}°C, Umidade {umid}%, Vento {vento} km/h"
    except requests.Timeout:
        return "Erro: tempo esgotado ao buscar previsao do tempo."
    except Exception as e:
        logger.error("Erro ao buscar clima: %s", e)
        return f"Erro ao buscar clima: {e}"
