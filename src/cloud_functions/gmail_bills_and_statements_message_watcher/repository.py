from datetime import datetime
from loguru import logger
import os

from firebase_admin import firestore

# import dto


class FirestoreRepository:
    """
    This class is a placeholder for the Firestore repository.
    In a real implementation, this would interact with Firestore to manage user records.
    """

    def __init__(self, db: firestore.Client):
        self.db = db

    def get_user_me(self):
        user = self.db.collection("users").document("me").get()

        if not user.exists:
            user = self.initialize_user_data()

        return user
    
    def get_all_users_iterator(self):
        """Get a firestore stream from users collections. Iterate to get all users.

        Returns:
            Iterator: An interator to fetch all documents.
        """
        return self.db.collection("users").stream()

    def delete_user_me(self):
        """
        Deletes the 'me' user document from the Firestore database.
        This is a placeholder for the actual deletion logic.
        """
        logger.warning("Deleting user 'me' record from Firestore.")
        self.db.collection("users").document("me").delete()

        # Optionally, you can return a confirmation message or status
        return
    
    def update_user_document(self, user):
        user_data = user.to_dict()
        
        user_obj = {
            "email": user.id,
            "watchConfig": user_data.get("watchConfig", {}),
            "currentWatch": user_data.get("currentWatch", {})
        }
        
        self.db.document("users/"+user.id).set(user_obj, merge=True)
        
        return self.db.document("users/"+user.id).get()
    

    def update_user_oauth_token(self, user_id: str, token: dict):
        self.db.document("users/"+user_id).set({"authTokens": token}, merge=True)
        
        return self.db.document("users/"+user_id).get()
        

    def update_user_last_refresh(
        self,
        user_id: str,
        last_refresh: datetime,
        expiration: datetime,
        history_id: str,
    ):
        # Move the user old record to the 'history' subcollection
        old_record = self.db.collection("users").document(user_id).get()
        
        logger.info(f"Queried old record of user '{user_id}'")

        self.db.document(f"users/{user_id}").update(
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
            }
        )
        
        logger.info(f"Updated currentWatch for user '{user_id}'")

        if not old_record.to_dict()["currentWatch"]:
            logger.warning(f"There was no currentWatch for user '{user_id}'")
            return

        old_data = old_record.to_dict()
        current_watch = old_data.get("currentWatch")
        if current_watch and "timestamp" in current_watch:
            self.db.collection("users").document(user_id).collection(
                "watchHistory"
            ).document(current_watch["timestamp"]).set(current_watch)
            logger.info(f"Saved old record on watchHistory for user '{user_id}'")
        else:
            logger.warning(f"No valid currentWatch to archive for user '{user_id}'")

        return

    def initialize_user_data(self):
        """
        Initializes the 'me' user document. This should be called ONCE during initial setup.
        """
        logger.warning("No records of user 'me' were found. Initializing database.")
        # if label_ids is None:
        #     label_ids = ['INBOX']

        initial_data = {
            "userId": os.environ["SETUP_USER_ID"],
            "email": os.environ["SETUP_USER_EMAIL"],
            # "authTokens": {
            #     "accessToken": access_token,
            #     "refreshToken": refresh_token,
            #     "expiresAt": expires_at.isoformat()
            # },
            # "watchConfig": {
            #     "labelIds": label_ids
            # },
            "currentWatch": {},  # Start as empty map
            "lastWatchRenewalAttempt": None,
            "watchStatus": "inactive",
        }
        # Use merge=True to ensure it doesn't overwrite existing fields if document already partially exists
        self.db.collection("users").document(initial_data["userId"]).set(
            initial_data, merge=True
        )
        new_user = self.db.collection("users").document(initial_data["userId"])

        # Setting watchHistory for user
        new_user.collection("watchHistory").document(datetime.now().isoformat()).set({})

        new_user_data = new_user.get()

        logger.info(f"User created. {new_user_data}")

        return new_user_data

