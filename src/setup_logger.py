from loguru import logger
import google.cloud.logging as cloud_logging  # type: ignore
from google.cloud.logging_v2.handlers import CloudLoggingHandler
import sys


def setup_logging(
    env_type: str, log_level: str
):
    logger.remove()

    if env_type == "PROD":
        gcp_logger_name = "gcp_log_processor"

        client = cloud_logging.Client()
        handler = CloudLoggingHandler(client, name=gcp_logger_name)
        handler.setLevel(level=log_level)
        logger.add(handler)
        
        # logger.add(
        #     sys.stdout,
        #     serialize=True,
        #     level=log_level,
        #     format="{message}",
        #     catch=True
        # )
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
