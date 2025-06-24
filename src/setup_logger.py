from loguru import logger
import sys


def setup_logging(
    env_type: str, log_level: str
):  # Se você estiver usando um módulo separado para isso
    logger.remove()  # Remove o handler padrão para ter controle total

    if env_type == "PROD":  # Exemplo: só habilita em desenvolvimento
        logger.add(
            sys.stdout,
            serialize=True,
            level=log_level,
            format="{message}",
            catch=True
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
