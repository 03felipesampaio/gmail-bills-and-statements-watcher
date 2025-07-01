from loguru import logger
import gmail_service
from . import message_handlers


class HandlerFunctionService:
    def __init__(
        self, gmail: gmail_service.GmailService, handlers: list[message_handlers.MessageHandler]
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
            user_email=self.user_email
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
                self._process_history_events(
                    history_events
                )
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
                continue
            
            logger.debug(
                "Message {message_id} matches conditions of handler {handler_name}.",
                message_id=message_content["id"],
                handler_name=handler.name,
                user_email=user_email
            )
            
            handler.handle(message_content)
            
        logger.debug(
            "Finished to handle message {message_id}. (user {user_email})",
            message_id=message_id,
            user_email=user_email,
        )
        
        # if message_subject not in subjects:
        #     logger.debug(
        #         "Skipping message {message_id}. Message subject is NOT on watched subject list. (user {user_email})",
        #         user_email=user_email,
        #         message_id=message_id,
        #         message_subject=message_subject
        #     )
        #     return
        
        # logger.debug(
        #     "Message '{message_id}' has a desired subject '{message_subject}'. Getting its attachments. (user {user_email})",
        #     message_id=message_id,
        #     message_subject=message_subject,
        #     user_email=user_email,
        # )
        
        # attachment_handlers = subjects[message_subject]
        # for handler in attachment_handlers:
        #     attachments = self.gmail.download_attachments(
        #         message_content, handler.filter
        #     )
        #     for attachment in attachments:
        #         handler.run(message_content, attachment)


# def find_start_history_id(user_last_history_id: int, event_history_id: int) -> int:
#     """
#     Determines the starting history ID for processing Gmail events.
#     If the user's last known history ID is not set (i.e., falsy), returns the event's history ID.
#     Otherwise, returns the next history ID after the user's last known history ID.
#     Args:
#         user_last_history_id (int): The last history ID processed for the user. Can be 0 or None if not set.
#         event_history_id (int): The history ID associated with the current event.
#     Returns:
#         int: The starting history ID to use for processing.
#     """
#     if not user_last_history_id:
#         return int(event_history_id)

#     return int(user_last_history_id) + 1


# def process_history_events(history_events: dict):
#     for message_info in history_events.get("messagesAdded", []):
#         message = message_info.get("message", {})
#         if not message:
#             continue

#         message_id = message["id"]
#         # Fetch the full message content
#         message_content = gmail.fetch_message_by_id(message_id, "full")
#         message_subject = gmail.get_message_subject(message_content)

#         logger.info(
#             f"Handling message '{message_id}' from historyId '{current_history_id}' for user '{user_email}' with subject '{message_subject}'"
#         )

#         if message_subject not in SUBJECTS:
#             logger.debug(
#                 f"Subject '{message_subject}' is NOT on watched subject list. Skipping... (user {user_email})"
#             )
#             continue

#         logger.info(
#             f"Message '{message_id}' has a desired subject '{message_subject}'. Getting its attachments. (user {user_email})"
#         )

#         attachment_handlers = SUBJECTS[message_subject]

#         for handler in attachment_handlers:
#             attachments = gmail.download_attachments_with_condition(
#                 message_content, handler.filter
#             )

#             for attachment in attachments:
#                 handler.run(message_content, attachment)
