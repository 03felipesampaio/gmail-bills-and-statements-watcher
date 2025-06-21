from google.cloud import firestore

import json
from loguru import logger
from google.oauth2.credentials import Credentials


class FirestoreService:
    def __init__(self, client: firestore.Client):
        self.client = client

    def get_user_data(self, user_email: str) -> dict | None:
        """Retrieves user document data."""
        doc_ref = self.db.collection("users").document(user_email)
        doc_snapshot = doc_ref.get()
        if doc_snapshot.exists:
            return doc_snapshot.to_dict()
        return None

    def set_user_data(self, user_email: str, data: dict) -> None:
        """Sets or updates user document data."""
        doc_ref = self.client.collection("users").document(user_email)
        doc_ref.set(data, merge=True)

    def set_user_auth_tokens(self, user_email: str, token: dict|Credentials) -> None:
        if isinstance(token, Credentials):
            token = json.loads(token.to_json(), merge=True)
        doc_ref = self.client.collection("users").document(user_email)
        doc_ref.set({"authTokens": token}, merge=True)
        