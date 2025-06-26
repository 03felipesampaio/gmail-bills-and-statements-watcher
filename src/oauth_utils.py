from loguru import logger

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token  # To verify ID Token and get email


def start_oauth_flow(gmail_client_id, auth_code, scopes, redirect_uri) -> Credentials:
    logger.info("Starting OAuth flow")

    flow = Flow.from_client_config(gmail_client_id, scopes, redirect_uri=redirect_uri)

    logger.info("Fetching token")
    flow.fetch_token(code=auth_code)
    creds = flow.credentials

    if not creds.refresh_token:
        raise ValueError(
            "No Refresh Token was received. User might not have granted 'offline' access."
        )

    logger.info("Refresh Token obtained successfully.")

    if not creds.id_token:
        raise ValueError(
            "ID Token not received. Check 'openid' and 'email' scopes and user consent."
        )

    logger.info("Finished OAuth flow")

    return creds


def get_user_email_from_credentials(creds: Credentials) -> str:
    id_info = id_token.verify_oauth2_token(creds.id_token, Request(), creds.client_id)
    user_email = id_info.get("email")

    if not user_email:
        logger.warning("User email not found in ID Token.")
        raise ValueError("Error: User email not found in ID Token. Cannot store.")

    logger.info(f"User email identified: {user_email}")

    return user_email


def build_credentials_from_token(user_token: dict, scopes: list[str]) -> Credentials:
    return Credentials.from_authorized_user_info(user_token, scopes)


def refresh_user_credentials(creds: Credentials) -> Credentials:
    """
    Refresh and validate user OAuth2 credentials.

    If the credentials are expired and have a refresh token, attempts to refresh them.
    Raises ValueError if credentials are invalid or incomplete.

    Args:
        creds (Credentials): The user's OAuth2 credentials.

    Returns:
        Credentials: A valid, refreshed Credentials object.

    Raises:
        ValueError: If credentials are invalid or incomplete.
        RefreshError: If refreshing the credentials fails.
    """
    if not creds:
        raise ValueError("Credentials are invalid or incomplete.")

    logger.debug(
        "Instancieted Oauth credentials",
        valid=creds.valid,
        expired=creds.expired,
        has_refresh_token=bool(creds.refresh_token),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        logger.info("Refreshed expired credentials.")

    return creds
