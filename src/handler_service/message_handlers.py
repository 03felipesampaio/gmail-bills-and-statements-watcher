import base64
from datetime import datetime, timezone
from typing import Generator, NotRequired, TypedDict
from loguru import logger
from pathlib import Path
from gmail_service.models import AttachmentResponse, MessageFull, MessagePayload
from gmail_service.service import GmailService
from .conditions import MessageConditions
import models
from google.cloud import storage  # type: ignore
import json


class AttachmentFilter(TypedDict):
    extension: NotRequired[str]
    filename: NotRequired[str]


class MessageAction:
    def __init__(self, **kwargs):
        self.extras = kwargs

    def run(self, message: MessageFull):
        pass


class MessageActionDownloadLocally(MessageAction):
    def __init__(self, path: str, name_fun=None):
        self.path = path
        self.name_fun = name_fun

        if name_fun is None:
            self.name_fun = lambda x: f"{x['id']}.json"

    def run(self, message: MessageFull):
        file = Path(self.path) / self.name_fun(message)
        file.write_text(json.dumps(message, indent=4, ensure_ascii=False))


class AttachmentAction(MessageAction):
    def __init__(
        self, attachments_filter: AttachmentFilter, gmail: GmailService, **kwargs
    ):
        self.attachments_filter = attachments_filter
        self.gmail = gmail

    def _attachment_passes_filter(self, message_payload: MessagePayload) -> bool:
        filename = message_payload.get("filename", "")
        extension = filename.split(".")[-1] if "." in filename else ""

        if "extension" in self.attachments_filter:
            if extension.lower() != self.attachments_filter["extension"].lower():
                return False

        if "filename" in self.attachments_filter:
            if self.attachments_filter["filename"].lower() not in filename.lower():
                return False

        return True

    def handle_attachment(
        self,
        message: MessageFull,
        attachment_part: MessagePayload,
        attachment: AttachmentResponse,
    ) -> None:
        raise NotImplementedError()

    def run(self, message: MessageFull) -> None:
        def walk_parts(parts) -> Generator[MessagePayload, None, None]:
            for part in parts:
                if "parts" in part and part["parts"]:
                    yield from walk_parts(part["parts"])
                else:
                    yield part

        payload = message.get("payload", {})
        parts = payload.get("parts", [])
        for part in walk_parts(parts):
            if not self._attachment_passes_filter(part):
                logger.debug(
                    "Attachment from partId {partId} does not pass filter for message {message_id}. (Action {action_name}).",
                    message_id=message["id"],
                    action_name=self.__class__.__name__,
                    partId=part.get("partId", ""),
                )
                continue
            
            logger.debug(
                    "Attachment from partId {partId} pass filter for message {message_id}. (Action {action_name}).",
                    message_id=message["id"],
                    action_name=self.__class__.__name__,
                    partId=part.get("partId", ""),
                )

            attachment_res = self.gmail.download_attachment(
                message["id"], part["body"]["attachmentId"], part["filename"]
            )
            self.handle_attachment(message, part, attachment_res)


class AttachmentActionSendToGCPCloudStorage(AttachmentAction):
    def __init__(
        self,
        attachments_filter: AttachmentFilter,
        bucket_name: str,
        path: str,
        gmail: GmailService,
        **kwargs,
    ):
        super().__init__(attachments_filter, gmail, **kwargs)
        self.bucket_name = bucket_name
        self.bucket = self._build_bucket(bucket_name)
        self.path = path

    def _build_bucket(self, name):
        return storage.Client().bucket(name)

    def handle_attachment(
        self,
        message: MessageFull,
        attachment_part: MessagePayload,
        attachment: AttachmentResponse,
    ) -> None:
        msg_date = datetime.fromtimestamp(
            int(message["internalDate"][:-3]), tz=timezone.utc
        ).strftime("%Y%m%d_%H%M%S")
        filename = (
            f"{self.path}/{msg_date}__{message['id']}__{attachment_part['filename']}"
        )
        blob = self.bucket.blob(filename)

        logger.debug(
            "Starting to send message {message_id} attachment {attachment_name} to bucket {bucket_name}'s file {filename}",
            message_id=message["id"],
            attachment_name=attachment_part["filename"],
            bucket_name=self.bucket_name,
            filename=filename,
        )

        blob.upload_from_string(
            data=base64.urlsafe_b64decode(attachment["data"]),
            content_type=attachment_part["mimeType"],
        )

        logger.debug(
            "Finished sending message {message_id} attachment {attachment_name} to bucket {bucket_name}'s file {filename}",
            message_id=message["id"],
            attachment_name=attachment_part["filename"],
            bucket_name=self.bucket_name,
            filename=filename,
        )


class MessageHandler:
    def __init__(
        self,
        name: str,
        conditions: MessageConditions,
        actions: list[MessageAction],
        **kwargs,
    ):
        self.name = name
        self.conditions = conditions
        self.actions = actions

        self.extras = kwargs

    def handle(self, message: MessageFull):
        logger.debug(
            "Starting handler {name} execution. Message {message_id}",
            name=self.name,
            message_id=message["id"],
        )
        for action in self.actions:
            logger.debug(
                "Starting the execution of handler {handler_name} action {action_name} for message {message_id}.",
                handler_name=self.name,
                action_name=action.__class__.__name__,
                message_id=message["id"],
            )
            action.run(message, **self.extras)
            logger.debug(
                "Finished the execution of handler {handler_name} action {action_name} for message {message_id}.",
                handler_name=self.name,
                action_name=action.__class__.__name__,
                message_id=message["id"],
            )
        logger.debug(
            "Finished handler {name} execution. Message {message_id}",
            name=self.name,
            message_id=message["id"],
        )


def build_message_handler_from_dict(
    handler_dict: models.MessageHandler, **kwargs
) -> MessageHandler:
    """
    Converte um dict do tipo models.MessageHandler em uma instância de MessageHandler.
    Instancia dinamicamente as actions a partir do nome da classe.
    """
    name = handler_dict["name"]
    logger.debug("Starting to instanciate handler {name}", name=name)
    conditions = MessageConditions(handler_dict["filterCondition"])
    actions = []
    for action_dict in handler_dict.get("actions", []):
        # Busca a classe dinamicamente no namespace atual
        action_cls = globals().get(action_dict["className"])
        if action_cls is not None:
            actions.append(action_cls(**action_dict.get("args", {})))
        else:
            logger.error(
                "Failed to find message action with name {class_name}",
                class_name=action_dict["className"],
            )

    logger.debug("Finished to instanciate handler {name}", name=name)
    return MessageHandler(name, conditions, actions, gmail=kwargs["gmail"])


# Como que posso usar isso?
# Start point: O gmail_service fez a req get da messagem (format full)
# Nesse momento o handler message ja vai ter sido instaciado com os handlers especificos do usuario
# Os handlers dos usuarios vao ficar no banco de dados com o formato:
# user: [{filter: dict, actions: list[dict]}]

# Quando o handle_service chamar os handlers
# For h in handlers:
#   Verificar se passa no filtro
#   Executar açoes

# Mas e os attachments? Como que vou chamar?
# 01. Para realizar o fetch dos attachements eu preciso fazer uma req no gmail service
# 02. Eu nao quero fazer a req toda vez que for executar um attachment handler
# 03. Para um attachment handler ser executado, é preciso passar por um filtro antes
# 04. Uma vez que o attachment for baixado, deve ficar disponivel para outros handlers
#
