from loguru import logger
import gmail_service
from . import message_handlers


class HandlerFunctionService:
    def __init__(
        self,
        gmail: gmail_service.GmailService,
        handlers: list[message_handlers.MessageHandler],
    ):
        self.gmail = gmail
        self.user_email = gmail.user_email
        self.handlers = handlers

    def sync_events(
        self,
        start_history_id: int,
        max_history_id: int,
    ):
        logger.info(
            "Start handling events from historyId {min_history_id} to {max_history_id}. (user {user_email})",
            min_history_id=start_history_id,
            max_history_id=max_history_id,
            user_email=self.user_email,
        )

        last_success_history_id = start_history_id

        for page in self.gmail.list_histories(str(start_history_id), ["messageAdded"]):
            last_success_history_id = self._process_history_page(
                page, max_history_id, last_success_history_id
            )

            if last_success_history_id == max_history_id:
                break

        return last_success_history_id

    def _process_history_page(
        self,
        history_page: gmail_service.models.HistoryList,
        max_history_id: int,
        last_success_history_id: int,
    ) -> int:
        user_email = self.user_email

        for history_events in history_page.get("history", []):
            # We only want to process until the historyId from event
            # This if stops the processing when we arrive to the final historyID
            current_history_id = int(history_events["id"])
            if current_history_id > max_history_id:
                logger.info(
                    "Encountered a historyId ({current_history_id}) greater than the target ({end_history_id}). Stopping processing this page.",
                    current_history_id=current_history_id,
                    end_history_id=max_history_id,
                )
                break

            logger.debug(
                "Starting to process events from historyId {history_id} (user {user_email})",
                history_id=current_history_id,
                user_email=user_email,
            )

            try:
                self._process_history_events(history_events)
                last_success_history_id = current_history_id
            except Exception:
                logger.exception(
                    "Failed to process events from historyId {history_id} (user {user_email})",
                    user_email=user_email,
                    history_id=current_history_id,
                )
                break

            logger.debug(
                "Finished processing events from historyId {history_id} (user {user_email})",
                history_id=current_history_id,
                user_email=user_email,
            )

        return last_success_history_id

    def _process_history_events(
        self, history_events: gmail_service.models.HistoryRecord
    ):
        for message_info in history_events.get("messagesAdded", []):
            message = message_info["message"]
            try:
                self._handle_message_added(message)
            except Exception as e:
                logger.error(
                    "Failed to process message {message_id} from historyId {history_id} (user {user_email})",
                    message_id=message["id"],
                    history_id=history_events["id"],
                    user_email=self.user_email,
                )
                raise e

    def _handle_message_added(self, message: gmail_service.models.MessageMinimal):
        user_email = self.user_email
        message_id = message["id"]
        message_content = self.gmail.fetch_message_by_id(message_id, "full")
        # message_subject = self.gmail.get_message_subject(message_content)
        logger.debug(
            "Starting to handle message {message_id}. (user {user_email})",
            message_id=message_id,
            user_email=user_email,
        )

        for handler in self.handlers:
            if not handler.check_conditions(message_content):
                logger.debug(
                    "Message {message_id} did not match conditions of handler {handler_name}. Skipping...",
                    message_id=message_content["id"],
                    handler_name=handler.name,
                    user_email=user_email,
                )
                continue

            logger.debug(
                "Message {message_id} matches conditions of handler {handler_name}.",
                message_id=message_content["id"],
                handler_name=handler.name,
                user_email=user_email,
            )

            handler.handle(message_content)

        logger.debug(
            "Finished to handle message {message_id}. (user {user_email})",
            message_id=message_id,
            user_email=user_email,
        )
