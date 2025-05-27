from datetime import datetime
import os

from loguru import logger
from dotenv import load_dotenv

import functions_framework
import firebase_admin
from firebase_admin import firestore

from . import repository
from . import gmail

logger.info("Starting Gmail Bills and Statements Message Watcher")
load_dotenv()

GCP_PROJECT_ID = os.environ["GCP_PROJECT_ID"]
GCP_REGION = os.environ["GCP_REGION"]
PUBSUB_TOPIC = os.environ["PUBSUB_TOPIC"]
FIRESTORE_DATABASE_ID = os.environ.get("FIRESTORE_DATABASE_ID", "(default)")

firebase_sdk = firebase_admin.initialize_app()


@functions_framework.http
def refresh_watch(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    # Receive request data
    # request_json = request.get_json(silent=True)
    # request_args = request.args
    
    db = repository.FirestoreRepository(firestore.client(database_id=FIRESTORE_DATABASE_ID))

    # If the expiration date is less than current date is due, we trow a warning, informing that a synchronization is needed
    users_last_refresh = db.get_users_last_refresh()

    # For each user, we will make a request to the Gmail API to refresh the watch
    responses = []
    for user in users_last_refresh:
        watcher_response = gmail.refresh_gmail_watcher(
            None,  # Replace with actual Gmail service instance
            user.user_id,
            PUBSUB_TOPIC,
        )
        responses.append(watcher_response)

        db.update_user_last_refresh(
            user.user_id,
            last_refresh=watcher_response["historyId"],
            expiration=datetime.fromtimestamp(int(watcher_response["expiration"])),
            history_id=watcher_response["historyId"],
        )

        logger.info(
            f"Refreshed watch for user {user.user_id} || user_id: {user.user_id} || historyId: {watcher_response['historyId']} || expiration: {datetime.fromtimestamp(int(watcher_response['expiration']))}"
        )

    return "SUCCESS", 200
