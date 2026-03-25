"""Monitoramento de recursos do sistema."""

import logging
import platform

import psutil

logger = logging.getLogger(__name__)


def obter_metricas_sistema() -> dict:
    """Retorna métricas atuais de CPU, RAM, disco e bateria."""
    try:
        cpu = psutil.cpu_percent(interval=0)
        memoria = psutil.virtual_memory()
        disco = psutil.disk_usage("/")

        metricas = {
            "cpu": cpu,
            "ram_usada": round(memoria.percent, 1),
            "ram_total_gb": round(memoria.total / (1024**3), 1),
            "disco_usado": round(disco.percent, 1),
            "disco_total_gb": round(disco.total / (1024**3), 1),
            "so": platform.system(),
            "bateria": None,
            "carregando": False,
        }

        bateria = psutil.sensors_battery()
        if bateria:
            metricas["bateria"] = round(bateria.percent, 1)
            metricas["carregando"] = bateria.power_plugged

        return metricas
    except Exception as e:
        logger.error("Erro ao obter métricas do sistema: %s", e)
        return {}
