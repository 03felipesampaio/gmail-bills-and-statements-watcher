# setup.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from loguru import logger


class AppSettings(BaseSettings):
    # Configuration for pydantic-settings
    model_config = SettingsConfigDict(
        env_file=".env",  # Could be used if you had a .env file
        env_file_encoding="utf-8",
        extra="ignore",  # Ignores fields in YAML/env not defined in the class
    )

    PROJECT_ID: str
    REGION: str
    PUBSUB_TOPIC: str
    FIRESTORE_DATABASE_ID: str
    ATTACHMENT_DESTINATION_BUCKET: str

    APP_CLIENT_ID_SECRET: str
    APP_OAUTH_FUNCTION_URI: str
    OAUTH_SCOPES: list[str]


def load_and_validate_environment(env_data: dict) -> AppSettings:
    """
    Reads the YAML file, loads it into the AppSettings class, and validates it.
    """
    try:
        settings = AppSettings(**env_data)
        logger.info("Environment variables validated successfully with Pydantic.")
        return settings
    except ValueError as e:
        logger.error(f"Pydantic validation error for the environment: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading and validating the environment: {e}")
        raise
