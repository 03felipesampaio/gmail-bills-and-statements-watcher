from google.cloud import firestore   # type: ignore

import json
from datetime import datetime
from loguru import logger
from google.oauth2.credentials import Credentials
from typing import Generator
import models

class FirestoreService:
    def __init__(self, client: firestore.Client):
        self.client = client

    def transaction(self):
        return self.client.transaction()

    def get_user_reference(self, user_email):
        return self.client.document(f"users/{user_email}")

    def get_user_data(self, user_email: str, transaction=None) -> models.User|None:
        """Retrieves user document data."""
        doc_ref = self.get_user_reference(user_email)
        doc_snapshot = doc_ref.get(transaction=transaction)
        if doc_snapshot.exists:
            return doc_snapshot.to_dict()
        return None

    def set_user_data(self, user_email: str, data: dict) -> None:
        """Sets or updates user document data."""
        doc_ref = self.client.collection("users").document(user_email)
        doc_ref.set(data, merge=True)

    def set_user_auth_tokens(self, user_email: str, token: dict | Credentials) -> None:
        if isinstance(token, Credentials):
            token = json.loads(token.to_json())
        doc_ref = self.client.collection("users").document(user_email)
        doc_ref.set({"authTokens": token}, merge=True)

    def get_all_users_iterator(self) -> Generator[models.User, None, None]:
        """Get a firestore stream from users collections. Iterate to get all users.

        Returns:
            Iterator: An interator to fetch all documents.
        """
        return self.client.collection("users").stream()

    def update_user_last_watch(
        self,
        transaction: firestore.Transaction,
        user_email: str,
        last_refresh: datetime,
        expiration: datetime,
        history_id: str,
    ):
        user_ref = self.get_user_reference(user_email)
        user_data = self.get_user_data(user_email)

        if not user_data:
            raise ValueError(
                f"Failed to fetch user '{user_email}'. There is no user with this ID."
            )

        logger.debug(f"Updating watch information on database for user '{user_email}'.")
        transaction.set(
            user_ref,
            {
                "currentWatch": {
                    "timestamp": last_refresh.isoformat(),
                    "status": "success",
                    "response": {
                        "historyId": history_id,
                        "expiration": expiration.isoformat(),
                    },
                    "errorMessage": None,
                }
            },
            merge=True,
        )

        logger.debug(f"Updated watch information on database for user '{user_email}'.")

        current_watch = user_data.get("currentWatch")
        
        if current_watch:
            historic_watch_ref = user_ref.collection("watchHistory").document(
                current_watch["timestamp"]
            )

            transaction.set(historic_watch_ref, current_watch)
            logger.debug(
                f"Added old watch information on historical database for user '{user_email}'."
            )

    def update_user_last_history_id(self, user_email: str, history_id: int):
        user = self.client.document(f"users/{user_email}")

        current_history_id = (
            user.get(["lastHistoryId"]).to_dict().get("lastHistoryId", 0)
        )

        if int(current_history_id) > int(history_id):
            logger.warning(
                "Tried to update lastHistoryId for user '{user_email}' with a historyId smaller than the current. Current historyId: '{current}'. Received historyId: {new}. Operation was not concluded.",
                user_email=user_email,
                current=current_history_id,
                new=history_id
            )
            return

        # transaction.set(user, {"lastHistoryId": history_id}, merge=True)
        user.set({"lastHistoryId": history_id}, merge=True)
        logger.info(
            "Set user '{user_email}' lastHistoryId from {old} to '{new}'",
            user_email=user_email,
            new=history_id,
            old=current_history_id,
        )

    def get_user_message_handlers(self, user_email: str) -> list[models.MessageHandler]:
        return [
            {
                "name": "Inter_01",
                "actions": [
                    {
                        "className": "MessageActionDownloadLocally",
                        "args": {
                            "path": "_messages"
                        }
                    }    
                ],
                "filterCondition": {
                    "subject": {
                        "contains": "a"
                    }
                }
            }
        ]