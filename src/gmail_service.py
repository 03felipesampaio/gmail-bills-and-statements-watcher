from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from loguru import logger
from collections.abc import Callable


class GmailService:
    def __init__(self, service):
        self.service = service

    def fetch_message_by_id(self, message_id: str, format: str):
        """
        Retrieve a Gmail message by its ID.

        Args:
            message_id (str): The ID of the Gmail message.
            format (str): The format of the message ('full', 'metadata', 'minimal', or 'raw').

        Returns:
            dict: The message resource as returned by the Gmail API.
        """

        logger.info(f"Fetching message with id '{message_id}'")
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

    def get_new_messsages_ids_and_max_history_id(
        self, start_history_id: str, end_history_id: str
    ) -> tuple[str, list[str]]:
        """Get all new messages IDs from Gmail API since last execution until the new one, received by Cloud Functions.

        Args:
            start_history_id (str): Start historyId, queried from database.
            end_history_id (str): End historyId, usually is the historyId from topic.

        Returns:
            tuple[str, list[str]]: Max historyID and the list of all messages IDs.
        """
        # Placeholder just to start while loop
        res = {"nextPageToken": None}
        max_history_id = "0"
        messages_ids = []

        while "nextPageToken" in res and int(max_history_id) < int(end_history_id):
            req = (
                self.service.users()
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
                if int(hist["id"]) > int(end_history_id):
                    if "nextPageToken" in res:
                        del res["nextPageToken"]
                    break

                max_history_id = str(max(int(max_history_id), int(hist["id"])))

                for message in hist.get("messagesAdded", []):
                    messages_ids.append(message["message"]["id"])

        return max_history_id, messages_ids
    
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
                        self.service.users()
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


def build_user_gmail_service(creds: Credentials):
    if not creds or not creds.valid:
        raise ValueError("Received a not valid credentials for build service.")

    service = build("gmail", "v1", credentials=creds)

    return service
