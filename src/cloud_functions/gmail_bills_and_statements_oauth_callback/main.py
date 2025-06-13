import json
import yaml
from pathlib import Path
from google.cloud import firestore
from google.cloud import secretmanager

# from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token  # To verify ID Token and get email
from loguru import logger  # For logging in Cloud Function

import functions_framework

ENV_VARS_YAML_PATH = Path("./env.yaml")

if ENV_VARS_YAML_PATH.exists():
    ENV_VARS = yaml.safe_load(ENV_VARS_YAML_PATH.open(encoding="utf8"))
else:
    raise FileNotFoundError("Failed to find YAML file with variables")


REDIRECT_URI = ENV_VARS["APP_OAUTH_FUNCTION_URI"]

# Initialize Firestore client
db_client = firestore.Client(database=ENV_VARS["FIRESTORE_DATABASE_ID"])


def get_client_credentials_from_secret_manager() -> dict:
    """
    Fetches the OAuth client ID and client secret from Google Secret Manager.
    Returns the client configuration as a dictionary.
    """
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(
        request={"name": ENV_VARS["APP_CLIENT_ID_SECRET"]}
    )
    return json.loads(response.payload.data.decode("UTF-8"))


@functions_framework.http
def oauth_callback_function(request):
    """Cloud function to handle OAuth flow to get app permissions
    for gmail accounts.
    """
    logger.info("OAuth callback Cloud Function triggered.")
    request_args = request.args
    auth_code = request_args.get("code")
    # state = request_args.get('state') # Optional: For security (CSRF prevention), you can verify this 'state'

    gmail_client_id = get_client_credentials_from_secret_manager()

    if not auth_code:
        logger.error("Error: Authorization code not found in the request.")
        return "Error: Authorization code not found. Please try again.", 400

    try:
        logger.info("Starting OAuth flow")
        flow = Flow.from_client_config(
            gmail_client_id, ENV_VARS["OAUTH_SCOPES"], redirect_uri=REDIRECT_URI
        )
        logger.info("Fetching token")
        flow.fetch_token(code=auth_code)
        creds = flow.credentials

        if not creds.refresh_token:
            logger.error(
                "No Refresh Token was received. User might not have granted 'offline' access."
            )
            return "Failed", 400

        logger.info("Refresh Token obtained successfully.")

        if not creds.id_token:
            logger.warning(
                "ID Token not received. Check 'openid' and 'email' scopes and user consent."
            )
            return "Error: ID Token missing. Check OAuth scopes.", 400
    except Exception as e:
        logger.error(e)
        raise e
        # return f"Internal server error: {e}", 500

    try:
        id_info = id_token.verify_oauth2_token(
            creds.id_token, Request(), creds.client_id
        )
        user_email = id_info.get("email")

        if not user_email:
            logger.warning("User email not found in ID Token.")
            return "Error: User email not found in ID Token. Cannot store.", 400

        logger.info(f"User email identified: {user_email}")
        db_client.document(f"users/{user_email}").set(
            {"authTokens": json.loads(creds.to_json())}, merge=True
        )
        logger.info(f"OAuth tokens for {user_email} successfully saved to Firestore.")
    except ValueError as e:
        logger.error(f"Invalid ID Token or problem verifying: {e}")
        return "Error: ID Token validation failed.", 400

    return "SUCCESS", 200
