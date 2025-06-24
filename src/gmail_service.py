from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from loguru import logger
from collections.abc import Callable


class GmailService:
    def __init__(self, service, user_email):
        self.service = service
        self.user_email = user_email

    def fetch_message_by_id(self, message_id: str, format: str) -> dict:
        """
        Retrieve a Gmail message by its ID.

        Args:
            message_id (str): The ID of the Gmail message.
            format (str): The format of the message ('full', 'metadata', 'minimal', or 'raw').

        Returns:
            dict: The message resource as returned by the Gmail API.
        """

        logger.info(f"Fetching message with id '{message_id}' for user '{self.user_email}'")
        return (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format=format)
            .execute()
        )

    def get_message_subject(self, message: dict) -> str | None:
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

    def watch(self, topic: str) -> dict:
        res = (
            self.service.users().watch(userId="me", body={"topicName": topic}).execute()
        )

        return res

    def fetch_new_messages_from_history_id_range(
        self, start_history_id: int, end_history_id: int
    ) -> list[dict]:
        """
        Retrieves all new message IDs from the Gmail API between two history IDs.

        Args:
            start_history_id (int): The starting historyId, typically queried from the database.
            end_history_id (int): The ending historyId, usually from the notification topic.

        Returns:
            list[dict]: A list of dictionaries, each containing 'historyId' and 'id' of a new message.
        """
        res = {"nextPageToken": None}
        messages_info = []

        while "nextPageToken" in res:
            req = (
                self.service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=str(start_history_id),
                    pageToken=res["nextPageToken"],
                    historyTypes=["messageAdded"],
                )
            )
            res = req.execute()

            for hist in res.get("history", []):
                if int(hist["id"]) > end_history_id:
                    if "nextPageToken" in res:
                        del res["nextPageToken"]
                    break

                for message in hist.get("messagesAdded", []):
                    messages_info.append(message["message"])

        return messages_info
    
    def download_attachments_with_condition(self, message: dict, filter: Callable[[dict], bool]):
        """
        Downloads attachments from a Gmail message that match a filter.

        Args:
            service: The Gmail API service instance.
            message (dict): The message resource as returned by the Gmail API.
            filter (callable): A function that takes an attachment's metadata and returns True if it should be downloaded.

        Returns:
            list: List of attachment contents (dicts as returned by attachments().get()).
        """
        logger.info(f"Fetching attachments for message '{message["id"]}'")
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
                    logger.info(f"Attachment '{part.get('filename')}' is being downloaded. Message '{message['id']}' User '{self.user_email}'")
                    attachment_data = (
                        self.service.users()
                        .messages()
                        .attachments()
                        .get(userId="me", messageId=message["id"], id=attachment_id)
                        .execute()
                    )
                    logger.info(f"Attachment '{part.get('filename')}' was downloaded. Message '{message['id']}' User '{self.user_email}'")
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


def build_user_gmail_service(creds: Credentials):
    if not creds or not creds.valid:
        raise ValueError("Received a not valid credentials for build service.")

    service = build("gmail", "v1", credentials=creds)

    return service
