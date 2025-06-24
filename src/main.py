import os
from pathlib import Path
from loguru import logger
from datetime import datetime
import yaml

import functions_framework
from cloudevents.http.event import CloudEvent
from google.cloud import firestore


from . import setup_env
from . import gcloud_utils
from . import oauth_utils
from . import firestore_service
from . import gmail_service
from . import message_handler

if Path("env.yaml").exists():
    env_data = yaml.safe_load(Path("env.yaml").read_text("utf8"))
else:
    env_data = gcloud_utils.get_secret_yaml(os.getenv("CONFIG_YAML_SECRET_NAME"))

settings = setup_env.load_and_validate_environment(env_data)

db = firestore_service.FirestoreService(
    firestore.Client(database=settings.FIRESTORE_DATABASE_ID)
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
    users_refreshed = []
    users_failed = {}

    for user_ref in db.get_all_users_iterator():
        try:
            user_data = user_ref.to_dict()

            if not user_data.get("authTokens"):
                logger.warning(
                    f"There is no tokens for user '{user_ref.id}'. Skipping..."
                )
                continue

            creds = oauth_utils.refresh_user_credentials(
                user_data["authTokens"], settings.OAUTH_SCOPES
            )
            db.set_user_auth_tokens(user_ref.id, creds)
            gmail = gmail_service.GmailService(
                gmail_service.build_user_gmail_service(creds)
            )
            watch_res = gmail.watch(settings.PUBSUB_TOPIC)

            with db.client.transaction() as transaction:
                db.update_user_last_watch(
                    transaction,
                    user_ref.id,
                    datetime.now(),
                    datetime.fromtimestamp(int(watch_res["expiration"][:-3])),
                    watch_res["historyId"],
                )

            users_refreshed.append(user_ref.id)
        except Exception as e:
            users_failed[user_ref.id] = {"errorMessage": str(e)}

    return {"usersRefreshed": users_refreshed, "failed": users_failed}, 200


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
            gmail_service.build_user_gmail_service(creds),
            event_email
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
                    f"Message '{message["id"]}' has a desired subject '{message_subject}'. Getting it attachments."
                )
                
                attachment_handlers = SUBJECTS[message_subject]
                
                for handler in attachment_handlers:
                    attachments = gmail.download_attachments_with_condition(
                        message_content, handler.filter
                    )

                    for attachment in attachments:
                        handler.run(message_content, attachment)
                    
            logger.info(f"Updating history_id_checkpoint from '{history_id_checkpoint}' to '{message_content["historyId"]}'")
            history_id_checkpoint = int(message_content["historyId"])
        
    except Exception as e:
        logger.error(f"Failed to handle messages for user '{event_email}'. Error: {e}")
        raise e
    finally:
        if history_id_checkpoint != user_last_history_id:
            with db.transaction() as transaction:
                db.update_user_last_history_id(transaction, event_email, history_id_checkpoint)
    
    
    return (
        f"Successfully updated history to '{topic_message['historyId']}' for user '{event_email}'",
        200,
    )
