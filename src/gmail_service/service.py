from google.oauth2.credentials import Credentials
from googleapiclient import discovery  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore
from loguru import logger
from collections.abc import Callable
from typing import Generator

from . import models


class GmailService:
    def __init__(self, service, user_email):
        self.service = service
        self.user_email = user_email

    def fetch_message_by_id(
        self, message_id: str, format: str = "full"
    ) -> models.MessageFull | None:
        """
        Retrieve a Gmail message by its ID.

        Args:
            message_id (str): The ID of the Gmail message.
            format (str): The format of the message ('full', 'metadata', 'minimal', or 'raw').

        Returns:
            dict: The message resource as returned by the Gmail API.
        """

        logger.debug(
            f"Fetching message with id '{message_id}' for user '{self.user_email}'"
        )
        
        try:
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format=format)
                .execute()
            )
        except HttpError as e:
            logger.warning(
                "Failed to fetch message with id '{message_id}' for user '{user_email}': {error}",
                message_id=message_id,
                user_email=self.user_email,
                error=str(e),
            )
            return None
        
        return message 

    def get_message_subject(self, message: models.MessageFull) -> str | None:
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

    def watch(self, topic: str) -> models.WatchResponse:
        res = (
            self.service.users().watch(userId="me", body={"topicName": topic}).execute()
        )

        return res

    def list_histories(
        self,
        start_history_id: str,
        history_types: list[str],
    ) -> Generator[models.HistoryList, None, None]:
        """
        A generator that fetches pages from the Gmail history().list API.

        With each iteration, it makes a new paginated request and yields the complete
        raw JSON response dictionary from the API.

        Args:
            start_history_id (str): The starting historyId to list from.
            history_types (list[str]): The types of history events to list (e.g., ['messageAdded']).
            max_history_id_to_fetch (str): The maximum historyId to fetch, used as a stop condition.

        Yields:
            dict: The raw JSON response dictionary from the API for a single page.
        """
        res = {"nextPageToken": None}
        start_history_id = str(start_history_id)  # Ensure it's a string

        # This loop condition is explicit, as requested.
        # Exceptions from the API call will propagate to the caller.
        while "nextPageToken" in res:
            logger.debug(
                f"Fetching history page with starting historyId '{start_history_id}' and pageToken: '{res.get('nextPageToken')}'"
            )

            req = (
                self.service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=start_history_id,
                    pageToken=res.get("nextPageToken"),
                    historyTypes=history_types,
                )
            )

            res = req.execute()

            yield res

        logger.debug("No next page token found. End of pagination.")
        return  # Ends the generator explicitly.

    def download_attachment(
        self, message_id: str, attachment_id: str, attachment_filename: str | None
    ) -> models.AttachmentResponse:
        logger.debug(
            "Starting to download attachment '{filename}' from message '{message_id}' for user '{user_email}'",
            filename=attachment_filename,
            attachment_id=attachment_id,
            message_id=message_id,
            user_email=self.user_email,
        )
        attachment = (
            self.service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        logger.debug(
            "Finished downloading attachment '{filename}' from message '{message_id}' for user '{user_email}'",
            filename=attachment_filename,
            attachment_id=attachment_id,
            message_id=message_id,
            user_email=self.user_email,
        )
        return attachment

    def download_attachments_by_condition(
        self, message: models.MessageFull, filter: Callable[[dict], bool] | None = None
    ):
        """
        Downloads attachments from a Gmail message that match a filter.

        Args:
            service: The Gmail API service instance.
            message (dict): The message resource as returned by the Gmail API.
            filter (callable): A function that takes an attachment's metadata and returns True if it should be downloaded.

        Returns:
            list: List of attachment contents (dicts as returned by attachments().get()).
        """
        if filter is None:
            filter = lambda x: True  # noqa: E731

        logger.info(f"Fetching attachments for message '{message['id']}'")
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
                    logger.info(
                        f"Attachment '{part.get('filename')}' is being downloaded. Message '{message['id']}' User '{self.user_email}'"
                    )
                    attachment_data = (
                        self.service.users()
                        .messages()
                        .attachments()
                        .get(userId="me", messageId=message["id"], id=attachment_id)
                        .execute()
                    )
                    logger.info(
                        f"Attachment '{part.get('filename')}' was downloaded. Message '{message['id']}' User '{self.user_email}'"
                    )
                    # Add filename and mimetype to the attachment data
                    attachment_data["filename"] = part.get("filename")
                    attachment_data["mimeType"] = part.get("mimeType")
                    attachments_content.append(attachment_data)
                    logger.info(
                        f"Successfully downloaded attachment '{part.get('filename')}'."
                    )
                # Recursively search for attachments in subparts
                if "parts" in part:
                    find_attachments(part["parts"])

        find_attachments(parts)
        return attachments_content


def build_user_gmail_service(creds: Credentials):
    if not creds or not creds.valid:
        raise ValueError("Received a not valid credentials for build service.")

    service = discovery.build("gmail", "v1", credentials=creds)

    return service
