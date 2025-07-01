from google.cloud import storage # type: ignore
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger
import base64


class AttachmentHandler:
    def __init__(self, filter: Callable[[dict], bool]):
        self.filter = filter

    def run(self, message: dict, attachment: dict):
        raise NotImplementedError()


# class MessageHandler:
#     def __init__(self, attachment_handlers: list[AttachmentHandler]=None):
#         self.attachment_handlers = attachment_handlers if attachment_handlers else []
        
#     def run(self, message):
#         # Add your message handle logic here
        
#         for attachment_handler in self.attachment_handlers:
#             attachment_handler.run(message)


class AttachmentHandlerUploadGCPCloudStorage(AttachmentHandler):
    def __init__(
        self, filter: Callable[[dict], bool], bucket: storage.Bucket, path: str
    ):
        if path.endswith("/"):
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

        logger.info(
            f"Starting upload to GCP Cloud Storage for file '{filename}'. Message ID: '{msg_id}'. Attachment name: '{attachment['filename']}'"
        )

        blob = self.bucket.blob(filename)
        decoded_data = base64.urlsafe_b64decode(attachment["data"])
        blob.upload_from_string(decoded_data, content_type=attachment["mimeType"])

        logger.info(
            f"Uploaded file to GCP Cloud Storage '{filename}'. Message ID: '{msg_id}'. Attachment name: '{attachment['filename']}'"
        )
        return blob.public_url


# def get_subjects() -> dict[str, list[MessageHandler]]:
#     subjects = {}
