from loguru import logger
import firestore_service
import gmail_service


class HandlerFunctionService:
    def __init__(
        self, gmail: gmail_service.GmailService, db: firestore_service.FirestoreService
    ):
        self.gmail = gmail
        self.db = db

    def sync_events_for_user(
        self,
        user_email: str,
        event_history_id: int,
        subjects: dict,
    ):
        """
        Processa todos os eventos do usuário, faz fail-fast, atualiza o banco e faz todo o logging.
        Deixa a função cloud function enxuta.
        """
        user = self.db.get_user_data(user_email)
        user_last_history_id = user.get("lastHistoryId")
        if not user_last_history_id:
            logger.warning("First time querying messages for user {user_email}", user_email=user_email)
        # Calcula o start_history_id
        start_history_id = int(event_history_id) if not user_last_history_id else int(user_last_history_id) + 1
        last_success_history_id = user_last_history_id
        for page in self.gmail.get_history_pages_generator(
            start_history_id, ["messageAdded"], event_history_id
        ):
            for history_events in page.get("history", []):
                current_history_id = int(history_events.get("id"))
                if current_history_id > event_history_id:
                    logger.info(
                        "Encountered a historyId ({current_history_id}) greater than the target end_history_id ({end_history_id}). Stopping processing this page.",
                        current_history_id=current_history_id,
                        end_history_id=event_history_id,
                    )
                    break
                try:
                    self.process_history_events(history_events, user_email, current_history_id, subjects)
                    last_success_history_id = current_history_id
                except Exception as e:
                    logger.error(
                        "Erro ao processar historyId {current_history_id} para user {user_email}: {error}",
                        current_history_id=current_history_id,
                        user_email=user_email,
                        error=str(e),
                    )
                    # Atualiza o banco antes de propagar a exceção
                    if last_success_history_id != user_last_history_id:
                        self.db.update_user_last_history_id(user_email, last_success_history_id)
                    raise e
        # Atualiza o banco ao final
        if last_success_history_id != user_last_history_id:
            self.db.update_user_last_history_id(user_email, last_success_history_id)
        logger.info(
            "Finished syncing events from historyId '{from_history_id}' to '{to_history_id}' (user {user_email})",
            from_history_id=user_last_history_id,
            to_history_id=event_history_id,
            user_email=user_email,
        )
        return last_success_history_id

    def process_history_events(self, history_events: dict, user_email: str, current_history_id: int, subjects: dict):
        for message_info in history_events.get("messagesAdded", []):
            message = message_info.get("message", {})
            if not message:
                continue
            self.handle_message_added(message, user_email, current_history_id, subjects)

    def handle_message_added(self, message: dict, user_email: str, current_history_id: int, subjects: dict):
        message_id = message["id"]
        message_content = self.gmail.fetch_message_by_id(message_id, "full")
        message_subject = self.gmail.get_message_subject(message_content)
        logger.info(
            "Handling message '{message_id}' from historyId '{current_history_id}' for user '{user_email}' with subject '{message_subject}'",
            message_id=message_id,
            current_history_id=current_history_id,
            user_email=user_email,
            message_subject=message_subject,
        )
        if message_subject not in subjects:
            logger.debug(
                "Subject '{subject}' is NOT on watched subject list. Skipping... (user {user_email})",
                subject=message_subject,
                user_email=user_email,
            )
            return
        logger.info(
            "Message '{message_id}' has a desired subject '{message_subject}'. Getting its attachments. (user {user_email})",
            message_id=message_id,
            message_subject=message_subject,
            user_email=user_email,
        )
        attachment_handlers = subjects[message_subject]
        for handler in attachment_handlers:
            attachments = self.gmail.download_attachments_with_condition(
                message_content, handler.filter
            )
            for attachment in attachments:
                handler.run(message_content, attachment)


def parse_data_from_event(event_data) -> dict:
    pass


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
