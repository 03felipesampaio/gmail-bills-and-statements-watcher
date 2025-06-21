import typing
from loguru import logger

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


def refresh_user_credentials(user_token: dict, scopes: list[str]) -> Credentials:
    creds = Credentials.from_authorized_user_info(user_token, scopes)

    if not creds:
        logger.error("Credentials are invalid or incomplete.")
        raise ValueError("Credentials are invalid or incomplete.")

    logger.info(f"Got user token. Expired: '{creds.expired}' Has refresh token: {bool(creds.refresh_token)}")
    if creds.expired and creds.refresh_token:
        logger.info("Atempting to refresh user credentials.")
        creds.refresh(Request())
        logger.info("Refreshed expired credentials.")

    return creds


def build_user_gmail_service(creds: Credentials):
    if not creds:
        raise ValueError("Received a not valid credentials for build service.")
    service = build("gmail", "v1", credentials=creds)

    return service


def build_service_from_user_token(user_token: dict, scopes: list[str]):
    creds = refresh_user_credentials(user_token, scopes)
    service = build_user_gmail_service(creds)
    return service


def get_message_by_id(service, message_id: str, format: str):
    """
    Retrieve a Gmail message by its ID.

    Args:
        message_id (str): The ID of the Gmail message.
        format (str): The format of the message ('full', 'metadata', 'minimal', or 'raw').
        service: The Gmail API service instance.

    Returns:
        dict: The message resource as returned by the Gmail API.
    """
    return (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format=format)
        .execute()
    )


def get_message_subject(message: dict) -> str | None:
    """
    Extracts the subject from a Gmail message resource.

    Args:
        message (dict): The message resource as returned by the Gmail API.

    Returns:
        str | None: The subject of the email, or None if not found.
    """
    headers = message.get("payload", {}).get("headers", [])
    for header in headers:
        if header.get("name", "").lower() == "subject":
            return header.get("value")
    return None

def download_attachments_with_condition(service, message: dict, filter: typing.Callable[[dict], bool]):
    """
    Downloads attachments from a Gmail message that match a filter.

    Args:
        service: The Gmail API service instance.
        message (dict): The message resource as returned by the Gmail API.
        filter (callable): A function that takes an attachment's metadata and returns True if it should be downloaded.

    Returns:
        list: List of attachment contents (dicts as returned by attachments().get()).
    """
    attachments_content = []
    payload = message.get("payload", {})
    parts = payload.get("parts", [])

    def find_attachments(parts):
        for part in parts:
            if not part.get("filename"):
                continue
            
            body = part.get("body", {})
            attachment_id = body.get("attachmentId")
            if attachment_id and filter(part):
                logger.info(f"Attachment '{part.get('filename')}' is being downloaded.")
                attachment_data = (
                    service.users()
                    .messages()
                    .attachments()
                    .get(userId="me", messageId=message["id"], id=attachment_id)
                    .execute()
                )
                # Add filename and mimetype to the attachment data
                attachment_data["filename"] = part.get("filename")
                attachment_data["mimeType"] = part.get("mimeType")
                attachments_content.append(attachment_data)
                logger.info(f"Successfully downloaded attachment '{part.get('filename')}'.")
            # Recursively search for attachments in subparts
            if "parts" in part:
                find_attachments(part["parts"])

    find_attachments(parts)
    return attachments_content


class GmailAPIService:
    def __init__(self, service):
        self.service = service

    def watch(self, user_id, topic_name, labelsIds=None):
        """Call the Gmail API to watch for changes in the user's mailbox."""
        return {
            "expiration": "1748310342",
            "historyId": "1234567890",
        }

    def stop_watching(self, user_id):
        """Call the Gmail API to stop watching for changes in the user's mailbox."""
        # return self.service.users().stop(userId=user_id).execute()
        return None
