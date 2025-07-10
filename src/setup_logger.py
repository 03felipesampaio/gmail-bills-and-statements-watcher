from loguru import logger

import sys
import json


def dump_log_to_json_for_cloud_logging(
    message,
):  # Note: Não retorna string para o Loguru aqui
    """
    Formata um registro de log do Loguru em JSON compatível com o Cloud Logging
    e o imprime no sys.stdout.
    """
    record = message.record
    
    log_entry = {
        "severity": record["level"].name.upper(),
        "message": record["message"].strip(),  # A mensagem principal
        "timestamp": record["time"].isoformat(),
        "logger_name": record["name"],
        "function": record["function"],
        "line": record["line"],
        **record["extra"],  # Inclui quaisquer dados 'extra' adicionados ao log
    }
    
    sys.stdout.write(json.dumps(log_entry) + "\n")
    sys.stdout.flush()


def setup_logging(env_type: str, log_level: str):
    logger.remove()

    if env_type == "PROD":
        logger.add(
            sink=dump_log_to_json_for_cloud_logging,
            level=log_level,
            enqueue=True, # Importante para evitar bloqueios em ambiente de produção
            backtrace=True, # Desabilita backtrace padrão do Loguru
            diagnose=False,  # Desabilita diagnose padrão do Loguru
            catch=True # Captura exceções dentro do handler
        )
    else:
        logger.add(
            sys.stdout,
            colorize=True,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>\n"
                "<level>{message}</level> {extra}\n"
                # "{exception} "
            ),
            level="DEBUG",
            diagnose=False,   # Show variables in tracebacks
            # backtrace=True,  # Full stack trace
            catch=True
        )
