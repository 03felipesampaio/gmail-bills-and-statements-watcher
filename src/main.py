import os
from pathlib import Path
from loguru import logger
from datetime import datetime
import yaml  # type: ignore

import functions_framework
from cloudevents.http.event import CloudEvent
from google.cloud import firestore  # type: ignore

import setup_logger
import setup_env
import gcloud_utils
import oauth_utils
import gmail_service
import firestore_service
import handler_service

import default_handlers

setup_logger.setup_logging(os.getenv("ENVIRON", "DEV"), os.getenv("LOG_LEVEL", "DEBUG"))

logger.info("Initializing function environment.")
logger.info("Looking up for environment YAML.")
if Path("env.yaml").exists():
    # logger.info("Found env.yaml file locally. Loading it.")
    env_data = yaml.safe_load(Path("env.yaml").read_text("utf8"))
else:
    # logger.info("Did not find env.yaml. Fetching file from Cloud Secrets.")
    env_data = gcloud_utils.get_secret_yaml(os.environ["CONFIG_YAML_SECRET_NAME"])

logger.info("Sending env variables for validation.")
settings = setup_env.load_and_validate_environment(env_data)

logger.info(
    "Connecting to firestore database '{database}'",
    database=settings.FIRESTORE_DATABASE_ID,
)
db = firestore_service.FirestoreService(
    firestore.Client(database=settings.FIRESTORE_DATABASE_ID)
)
logger.info(
    "Successfully connected to firestore '{database}'",
    database=settings.FIRESTORE_DATABASE_ID,
)


def build_gmail_service_from_user_tokens(
    user_email: str, auth_tokens: dict
) -> gmail_service.GmailService:
    logger.debug("Building Gmail service for user {user_email}", user_email=user_email)
    creds = oauth_utils.build_credentials_from_token(auth_tokens, settings.OAUTH_SCOPES)
    if not creds.valid:
        creds = oauth_utils.refresh_user_credentials(creds)
        db.set_user_auth_tokens(user_email, creds)
    gmail = gmail_service.GmailService(
        gmail_service.build_user_gmail_service(creds), user_email
    )
    logger.debug("Built Gmail service for user {user_email}", user_email=user_email)

    return gmail


@functions_framework.http
def oauth_callback_function(request):
    """Cloud function to handle OAuth flow to get app permissions
    for gmail accounts.
    """
    logger.info("OAuth callback Cloud Function triggered.")
    request_args = request.args
    auth_code = request_args.get("code")

    if not auth_code:
        logger.error("Authorization code not found in the request.")
        return "Authorization code not found. Please try again.", 400

    try:
        gmail_client_id = gcloud_utils.get_client_credentials_from_secret_manager(
            settings.APP_CLIENT_ID_SECRET
        )
    except Exception:
        logger.exception("Failed to fetch secret from Secret Manager")
        return "Error building credentials", 500

    try:
        logger.info("Starting OAuth flow")
        creds = oauth_utils.start_oauth_flow(
            gmail_client_id,
            auth_code,
            settings.OAUTH_SCOPES,
            settings.APP_OAUTH_FUNCTION_URI,
        )

        user_email = oauth_utils.get_user_email_from_credentials(creds)
        logger.info("Finished OAuth flow")
    except Exception:
        logger.exception("Failed OAuth flow")
        return "Failed OAuth flow", 500

    db.set_user_auth_tokens(user_email, creds)
    logger.info(
        "OAuth tokens for {user_email} writen on database.", user_email=user_email
    )

    return "SUCCESSFULLY AUTHORIZED", 200


@functions_framework.http
def refresh_watch(request):
    logger.info("Starting execution of refresh_watch")
    users_refreshed = 0
    users_failed = 0

    for user_ref in db.get_all_users_iterator():
        logger.info("Refreshing watch for user '{user_id}'", user_id=user_ref.id)
        try:
            user_data = db.get_user_data(user_ref.id)

            if not user_data:
                raise ValueError(
                    f"User '{user_ref.id}' data was not found. Probably was deleted after the start of this function"
                )
                
            if not user_data.get("authTokens"):
                raise ValueError(
                    f"User '{user_ref.id}' does not have authTokens. Cannot refresh watch."
                )

            gmail = build_gmail_service_from_user_tokens(
                user_ref.id, user_data["authTokens"]
            )

            # Calling watch() for user
            watch_res = gmail.watch(settings.PUBSUB_TOPIC)

            # Writing watch response to database
            with db.client.transaction() as transaction:
                db.update_user_last_watch(
                    transaction,
                    user_ref.id,
                    datetime.now(),
                    datetime.fromtimestamp(int(watch_res["expiration"][:-3])),
                    watch_res["historyId"],
                )

            users_refreshed += 1
            logger.info(
                "Refreshed watch for user '{user_id}'",
                user_id=user_ref.id,
                watch=watch_res,
            )
        except Exception:
            logger.exception(
                "Failed to refresh watch for user '{user_id}'",
                user_id=user_ref.id,
            )
            users_failed += 1

    response = {"usersRefreshed": users_refreshed, "usersFailedRefresh": users_failed}
    logger.info("Finished refresh", **response)

    return response, (200 if users_failed == 0 else 500)


@functions_framework.cloud_event
def handle_events(cloud_event: CloudEvent):
    """
    Cloud Function to handle Gmail messages for bills and statements.
    This function is triggered by a CloudEvent from Pub/Sub.
    """
    data = cloud_event.data
    logger.info("Received event from pubsub", event_data=data)
    topic_message = gcloud_utils.decode_topic_message(data)

    user_email = topic_message["emailAddress"]
    event_history_id = topic_message["historyId"]
    logger.info(
        "Identified event email: {user_email}",
        user_email=user_email,
        topic_message=topic_message,
    )

    user = db.get_user_data(user_email)

    if not user:
        logger.warning("No user found for email {user_email}", user_email=user_email)
        return f"There is no record of user '{user_email}'", 404

    try:
        gmail = build_gmail_service_from_user_tokens(user_email, user["authTokens"])
    except Exception as e:
        logger.exception(
            "Failed to build service for user {user_email}", user_email=user_email
        )
        raise e

    message_handlers = [
        handler_service.build_message_handler_from_dict(h, gmail=gmail)
        for h in db.get_user_message_handlers(user_email)
    ]
    if not message_handlers:
        logger.warning(
            "No message handlers found for user {user_email}. Using default handlers.",
            user_email=user_email,
        )
        message_handlers = default_handlers.get_default_handlers(
            gmail, settings.ATTACHMENT_DESTINATION_BUCKET
        )

    handler = handler_service.HandlerFunctionService(
        gmail=gmail,
        handlers=message_handlers,
        db=db,
    )

    # It starts from the last successful run historyId + 1
    # If its the first run, it starts from the current event
    last_success_history_id = int(user.get("lastHistoryId", event_history_id - 1))
    start_history_id = last_success_history_id + 1

    try:
        last_success_history_id = handler.sync_events(
            start_history_id, event_history_id
        )
    except Exception as e:
        new_history_id = db.get_user_last_history_id(user_email)
        
        logger.exception(
            "Failed to sync events for user {user_email}. HistoryId expected: {expected}, got: {curr}",
            user_email=user_email,
            expected=event_history_id,
            curr=new_history_id,
        )
        raise e

    finally:
        new_history_id = db.get_user_last_history_id(user_email)

        logger.info(
            "Finished syncing events for user {user_email}. From historyId {start_history_id} to {end_history_id}",
            user_email=user_email,
            start_history_id=start_history_id,
            end_history_id=new_history_id,
        )
