from typing import Callable
import functions_framework
from cloudevents.http.event import CloudEvent
from google.cloud import firestore
from google.cloud import storage
from loguru import logger
import base64
import json
import yaml
from pathlib import Path
from datetime import datetime, timezone


from . import gmail
# from . import repository


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
ATTACHMENT_DESTINATION_BUCKET = ENV_VARS["ATTACHMENT_DESTINATION_BUCKET"]

firestore_client = firestore.Client(database=FIRESTORE_DATABASE_ID)
BUCKET = storage.Client().bucket(ATTACHMENT_DESTINATION_BUCKET)


class AttachmentHandlerUploadGCPCloudStorage:
    def __init__(
        self, filter: Callable[[dict], bool], bucket: storage.Bucket, path: str
    ):
        if path.endswith('/'):
            path = path[:-1]
        self.filter = filter
        self.bucket = bucket
        self.path = path

    def run(self, message: dict, attachment: dict):
        """
        Uploads an attachment to the specified Cloud Storage bucket.

        Args:
            attachment (dict): The attachment dictionary, expected to have 'filename', 'data' (base64 string) and 'mimeType'.

        Returns:
            str: The public URL of the uploaded file.
        """
        # I created this pattern for file names so we can have a idempotent pipeline
        msg_date = datetime.fromtimestamp(
            int(message["internalDate"][:-3]), tz=timezone.utc
        ).strftime("%Y%m%d_%H%M%S")
        msg_id = message["id"]
        original_filename = Path(attachment["filename"]).name
        filename = f"{self.path}/{msg_date}__{msg_id}__{original_filename}"
        
        logger.info(f"Starting upload to GCP Cloud Storage for file '{filename}'. Message ID: '{msg_id}'. Attachment name: '{attachment["filename"]}'")
        
        blob = self.bucket.blob(filename)
        decoded_data = base64.urlsafe_b64decode(attachment["data"])
        blob.upload_from_string(decoded_data, content_type=attachment["mimeType"])
        
        logger.info(f"Uploaded file to GCP Cloud Storage '{filename}'. Message ID: '{msg_id}'. Attachment name: '{attachment["filename"]}'")
        return blob.public_url


SUBJECTS = {
    "Sua fatura fechou e o débito automático está ativado": [
        AttachmentHandlerUploadGCPCloudStorage(
            lambda x: x.get("filename", "").endswith(".pdf"),
            BUCKET,
            "watcher/bills/nubank",
        )
    ],
    "Fatura Cartão Inter": [
        AttachmentHandlerUploadGCPCloudStorage(
            lambda x: x.get("filename", "").lower() == "fatura.pdf",
            BUCKET,
            "watcher/bills/inter",
        )
    ],
}


def decode_topic_message(topic_message_data: str) -> dict:
    message_content_json_str = base64.b64decode(
        topic_message_data["message"]["data"]
    ).decode("utf8")

    return json.loads(message_content_json_str)


def get_user_from_firestore(user_email: str):
    user = firestore_client.document("users/" + user_email).get()
    if not user.exists:
        raise ValueError(
            f"There is no document for user '{user_email}'. Please add it throug OAuth flow to get credentials."
        )
    return user


def get_new_messsages_ids_and_max_history_id(
    service, start_history_id: str, end_history_id: str
) -> tuple[str, list[str]]:
    """Get all new messages IDs from Gmail API since last execution until the new one, received by Cloud Functions.

    Args:
        service (Gmail Service): Gmail Service, already authorized
        start_history_id (str): Start historyId, queried from database.
        end_history_id (str): End historyId, usually is the historyId from topic.

    Returns:
        tuple[str, list[str]]: Max historyID and the list of all messages IDs.
    """
    # Placeholder just to start while loop
    res = {"nextPageToken": None}
    max_history_id = "0"
    messages_ids = []

    while "nextPageToken" in res and max_history_id < end_history_id:
        req = (
            service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=start_history_id,
                pageToken=res["nextPageToken"],
                historyTypes=["messageAdded"],
            )
        )
        res = req.execute()

        for hist in res.get("history", []):
            # It wont add messages with historyId bigger than our current received message by the cloud function
            if hist["id"] > end_history_id:
                if "nextPageToken" in res:
                    del res["nextPageToken"]
                break

            max_history_id = max(max_history_id, hist["id"])

            for message in hist.get("messagesAdded", []):
                messages_ids.append(message["message"]["id"])

    return max_history_id, messages_ids


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

    topic_message = decode_topic_message(data)
    email_address = topic_message["emailAddress"]
    logger.info(f"Received message for user: '{email_address}'")

    try:
        user = get_user_from_firestore(topic_message["emailAddress"])
    except ValueError as e:
        logger.error(str(e))
        raise e

    logger.info(f"Building Gmail service for user '{email_address}'")

    try:
        creds = gmail.refresh_user_credentials(
            user.to_dict()["authTokens"], ENV_VARS["OAUTH_SCOPES"]
        )
        service = gmail.build_user_gmail_service(creds)
    except Exception as e:
        logger.error(f"Failed to build service for user '{email_address}: {e}")
        raise e

    logger.info(f"Built Gmail service for user '{email_address}'")

    user_last_history_id = user.to_dict().get("lastHistoryId")

    if not user_last_history_id:
        logger.warning(f"First time quering messages for user '{email_address}'")
        start_history_id = str(int(topic_message["historyId"]) - 500)
    else:
        logger.info(
            f"Handling messages for user '{email_address}' from historyId starting at '{user_last_history_id}' and going to or beyond '{topic_message['historyId']}'"
        )
        start_history_id = user_last_history_id

    max_history_id, new_messages_ids = get_new_messsages_ids_and_max_history_id(
        service, start_history_id, str(topic_message["historyId"])
    )

    logger.info(
        f"Found {len(new_messages_ids)} new messages for user '{email_address}'."
    )

    for message_id in new_messages_ids:
        logger.info(
            f"Getting message with id '{message_id}' for user '{email_address}'"
        )
        message_content = gmail.get_message_by_id(service, message_id, "full")
        logger.info(f"Got message with id '{message_id}' for user '{email_address}'")
        message_subject = gmail.get_message_subject(message_content)

        if message_subject not in SUBJECTS:
            logger.info(
                f"Subject '{message_subject}' is NOT on watched subject list. Skipping..."
            )
            continue

        logger.info(
            f"Message '{message_id}' has a desired subject '{message_subject}'. Getting it attachments"
        )
        attachment_handlers = SUBJECTS[message_subject]

        for handler in attachment_handlers:
            attachments = gmail.download_attachments_with_condition(
                service, message_content, handler.filter
            )

            for attachment in attachments:
                handler.run(message_content, attachment)
            