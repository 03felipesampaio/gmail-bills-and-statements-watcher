from loguru import logger
from pathlib import Path
from gmail_service.models import MessageFull
from .conditions import MessageConditions
import models

import json


class MessageAction:
    def __init__(self):
        pass

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


class AttachmentAction:
    def __init__(self, conditions: dict):
        pass

    def check_conditions_on_attachment_headers(self, attachment_header: dict) -> bool:
        return False

    # def run(self, a)


class MessageHandler:
    def __init__(
        self, name: str, conditions: MessageConditions, actions: list[MessageAction]
    ):
        self.name = name
        self.conditions = conditions
        self.actions = actions

    def check_conditions(self, message: MessageFull) -> bool:
        # return self.conditions.check_message(message)
        return True

    def handle(self, message: MessageFull):
        logger.debug(
            "Starting handler {name} execution. Message {message_id}",
            name=self.name,
            message_id=message["id"],
        )
        for action in self.actions:
            action.run(message)
        logger.debug(
            "Finished handler {name} execution. Message {message_id}",
            name=self.name,
            message_id=message["id"],
        )


def build_message_handler_from_dict(
    handler_dict: models.MessageHandler,
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
    return MessageHandler(name, conditions, actions)


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
