import os
from pathlib import Path
from loguru import logger
from datetime import datetime
import yaml

import functions_framework
from cloudevents.http.event import CloudEvent
from google.cloud import firestore

from . import setup_logger
from . import setup_env
from . import gcloud_utils
from . import oauth_utils
from . import firestore_service
from . import gmail_service
from . import message_handler

setup_logger.setup_logging(os.getenv("ENVIRON", "DEV"), os.getenv("LOG_LEVEL", "INFO"))

logger.info("Initializing function environment.")
logger.info("Looking up for environment YAML.")
if Path("env.yaml").exists():
    logger.info("Found env.yaml file locally. Loading it.")
    env_data = yaml.safe_load(Path("env.yaml").read_text("utf8"))
else:
    logger.info("Did not find env.yaml. Fetching file from Cloud Secrets.")
    env_data = gcloud_utils.get_secret_yaml(os.getenv("CONFIG_YAML_SECRET_NAME"))

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

bucket = gcloud_utils.get_bucket(settings.ATTACHMENT_DESTINATION_BUCKET)


SUBJECTS = {
    "Sua fatura fechou e o débito automático está ativado": [
        message_handler.AttachmentHandlerUploadGCPCloudStorage(
            lambda x: x.get("filename", "").endswith(".pdf"),
            bucket,
            "watcher/bills/nubank",
        )
    ],
    "Fatura Cartão Inter": [
        message_handler.AttachmentHandlerUploadGCPCloudStorage(
            lambda x: x.get("filename", "").lower() == "fatura.pdf",
            bucket,
            "watcher/bills/inter",
        )
    ],
}


@functions_framework.http
def oauth_callback_function(request):
    """Cloud function to handle OAuth flow to get app permissions
    for gmail accounts.
    """
    logger.info("OAuth callback Cloud Function triggered.")
    request_args = request.args
    auth_code = request_args.get("code")

    if not auth_code:
        logger.error("Error: Authorization code not found in the request.")
        return "Error: Authorization code not found. Please try again.", 400

    gmail_client_id = gcloud_utils.get_client_credentials_from_secret_manager(
        settings.APP_CLIENT_ID_SECRET
    )

    try:
        creds = oauth_utils.start_oauth_flow(
            gmail_client_id,
            auth_code,
            settings.OAUTH_SCOPES,
            settings.APP_OAUTH_FUNCTION_URI,
        )

        user_email = oauth_utils.get_user_email_from_credentials(creds)
    except ValueError as e:
        logger.error(e)
        return str(e), 400

    db.set_user_auth_tokens(user_email, creds)
    logger.info(f"OAuth tokens for {user_email} successfully saved to database.")

    return "SUCCESSFULLY AUTHORIZED", 200


@functions_framework.http
def refresh_watch(request):
    logger.info("Starting execution of refresh_watch")
    users_refreshed = 0
    users_failed = 0

    for user_ref in db.get_all_users_iterator():
        user_logger = logger.bind(user_id=user_ref.id)
        user_logger.info("Refreshing watch")
        try:
            user_data = db.get_user_data(user_ref.id)

            if not user_data:
                raise ValueError(
                    f"User '{user_ref.id}' data was not found. Probably was deleted after the start of this function"
                )

            if not user_data.get("authTokens"):
                user_logger.warning(
                    "Found no tokens. Skipping...",
                )
                continue

            # Getting credentials and building Gmail Service for user

            creds = oauth_utils.refresh_user_credentials(
                user_data["authTokens"], settings.OAUTH_SCOPES
            )
            db.set_user_auth_tokens(user_ref.id, creds)
            gmail = gmail_service.GmailService(
                gmail_service.build_user_gmail_service(creds), user_ref.id
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
            user_logger.info(
                "Refreshed watch",
                watch=watch_res,
            )
        except Exception:
            user_logger.exception(
                "Failed to refresh watch",
            )
            users_failed += 1

    response = {"usersRefreshed": users_refreshed, "usersFailedRefresh": users_failed}
    logger.info("Finished refresh", **response)

    return response, 200 if users_failed == 0 else 500


@functions_framework.cloud_event
def download_statements_and_bills_from_message_on_topic(cloud_event: CloudEvent):
    """
    Cloud Function to handle Gmail messages for bills and statements.
    This function is triggered by a CloudEvent from Pub/Sub.

    Args:
        cloud_event (CloudEvent): The CloudEvent containing the Gmail message data.
    """
    # Extract the data from the CloudEvent
    data = cloud_event.data

    topic_message = gcloud_utils.decode_topic_message(data)
    logger.info(f"Received message: {topic_message}")

    event_email = topic_message["emailAddress"]
    event_history_id = topic_message["historyId"]

    user = db.get_user_data(event_email)

    if not user:
        return f"There is no record of user '{event_email}'", 404

    try:
        logger.info(f"Building Gmail service for user '{event_email}'")
        creds = oauth_utils.refresh_user_credentials(
            user["authTokens"], settings.OAUTH_SCOPES
        )
        db.set_user_auth_tokens(event_email, creds)
        gmail = gmail_service.GmailService(
            gmail_service.build_user_gmail_service(creds), event_email
        )
        logger.info(f"Built Gmail service for user '{event_email}'")
    except Exception as e:
        logger.error(f"Failed to build service for user '{event_email}: {e}")
        return e, 500

    user_last_history_id = user.get("lastHistoryId")

    if user_last_history_id:
        start_history_id = int(user_last_history_id) + 1
        logger.info(
            f"Processing messages for user '{event_email}' from history ID '{user_last_history_id}' to '{event_history_id}'."
        )
    else:
        logger.warning(f"First time quering messages for user '{event_email}'")
        start_history_id = topic_message["historyId"]

    new_messages = gmail.fetch_new_messages_from_history_id_range(
        start_history_id, topic_message["historyId"]
    )

    logger.info(f"Found {len(new_messages)} new messages for user '{event_email}'.")

    history_id_checkpoint = user_last_history_id

    try:
        for message in new_messages:
            message_content = gmail.fetch_message_by_id(message["id"], "full")
            message_subject = gmail.get_message_subject(message_content)

            if message_subject not in SUBJECTS:
                logger.info(
                    f"Subject '{message_subject}' is NOT on watched subject list. Skipping..."
                )
            else:
                logger.info(
                    f"Message '{message['id']}' has a desired subject '{message_subject}'. Getting it attachments."
                )

                attachment_handlers = SUBJECTS[message_subject]

                for handler in attachment_handlers:
                    attachments = gmail.download_attachments_with_condition(
                        message_content, handler.filter
                    )

                    for attachment in attachments:
                        handler.run(message_content, attachment)

            logger.info(
                f"Updating history_id_checkpoint from '{history_id_checkpoint}' to '{message_content['historyId']}'"
            )
            history_id_checkpoint = int(message_content["historyId"])

    except Exception as e:
        logger.error(f"Failed to handle messages for user '{event_email}'. Error: {e}")
        raise e
    finally:
        # TODO add correct transaction here. The current one is failing on get methods
        if history_id_checkpoint != user_last_history_id:
            db.update_user_last_history_id(event_email, history_id_checkpoint)

    return (
        f"Successfully updated history to '{topic_message['historyId']}' for user '{event_email}'",
        200,
    )
