# from datetime import datetime

from loguru import logger

import functions_framework
import firebase_admin
from firebase_admin import firestore

logger.info("Starting Gmail Bills and Statements Message Watcher")

logger.info("Starting Firebase Admin SDK")
firebase_app = firebase_admin.initialize_app()
logger.info("Initialized Firebase Admin SDK")


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
    request_json = request.get_json(silent=True)
    # request_args = request.args

    db = firestore.client(database_id="gmail-app")

    doc_ref = db.collection("user_refresh_watch").document(request_json["userId"])
    doc_ref.set({"historyId": "1234567890", "expiration": "1431990098200"})

    return "SUCCESS"
