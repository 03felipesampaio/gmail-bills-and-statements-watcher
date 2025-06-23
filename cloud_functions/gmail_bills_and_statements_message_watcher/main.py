from pathlib import Path
import yaml
from loguru import logger
import json
from datetime import datetime

import functions_framework
from google.cloud import firestore
from google.cloud import secretmanager

from . import repository
from . import gmail

logger.info("Starting Gmail Bills and Statements Message Watcher")

ENV_VARS_YAML_PATH = Path("./env.yaml")

if ENV_VARS_YAML_PATH.exists():
    ENV_VARS = yaml.safe_load(ENV_VARS_YAML_PATH.open(encoding="utf8"))
else:
    raise FileNotFoundError("Failed to find YAML file with variables")

GMAIL_CLIENT_ID_SECRET = ENV_VARS["APP_CLIENT_ID_SECRET"]
PROJECT_ID = ENV_VARS["PROJECT_ID"]
REGION = ENV_VARS["REGION"]
PUBSUB_TOPIC = ENV_VARS["PUBSUB_TOPIC"]
FIRESTORE_DATABASE_ID = ENV_VARS["FIRESTORE_DATABASE_ID"]


def get_client_credentials_from_secret_manager() -> dict:
    """
    Fetches the OAuth client ID and client secret from Google Secret Manager.
    Returns the client configuration as a dictionary.
    """
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(request={"name": GMAIL_CLIENT_ID_SECRET})
    return json.loads(response.payload.data.decode("UTF-8"))


gmail_client_id = get_client_credentials_from_secret_manager()
db = repository.FirestoreRepository(firestore.Client(database=FIRESTORE_DATABASE_ID))


@functions_framework.http
def refresh_watch(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    # Receive request data
    # request_json = request.get_json(silent=True)
    # request_args = request.args

    for user_old in db.get_all_users_iterator():
        user = db.update_user_document(user_old)
        user_data = user.to_dict()

        if not user_data.get("authTokens"):
            logger.warning(f"There is no tokens for user '{user.id}'")
            continue
        

        user_creds = gmail.refresh_user_credentials(user_data["authTokens"], ENV_VARS["OAUTH_SCOPES"])
        
        user_with_refreshed_token = db.update_user_oauth_token(user.id, json.loads(user_creds.to_json()))
        user_gmail_service = gmail.build_user_gmail_service(user_creds)

        res = user_gmail_service.users().watch(userId="me", body={"topicName": PUBSUB_TOPIC}).execute()
        
        db.update_user_last_refresh(user_with_refreshed_token.id, datetime.now(), datetime.fromtimestamp(int(res["expiration"][:-3])), res["historyId"])

    return ("SUCCESS", 200)
