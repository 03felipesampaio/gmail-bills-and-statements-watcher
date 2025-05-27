from datetime import datetime

from loguru import logger

import functions_framework

import repository
import gmail

logger.info("Starting Gmail Bills and Statements Message Watcher")


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

    # Execute query to get users ids
    # Execute query to get users last expiration date
    users_last_refresh = repository.get_users_last_refresh(None)
    # If the expiration date is less than current date is due, we trow a warning, informing that a synchronization is needed

    # For each user, we will make a request to the Gmail API to refresh the watch
    responses = []
    for user in users_last_refresh:
        watcher_response = gmail.refresh_gmail_watcher(
            None,  # Replace with actual Gmail service instance
            user.user_id,
            "projects/your-project-id/topics/your-topic-name",
            labelsIds=["INBOX"],
        )
        responses.append(watcher_response)

        repository.update_user_last_refresh(
            None,  # Replace with actual database instance
            user.user_id,
            last_refresh=watcher_response["historyId"],
            expiration=datetime.fromtimestamp(int(watcher_response["expiration"])),
            history_id=watcher_response["historyId"],
        )

        logger.info(
            f"Refreshed watch for user {user.user_id} || user_id: {user.user_id} || historyId: {watcher_response['historyId']} || expiration: {datetime.fromtimestamp(int(watcher_response['expiration']))}"
        )

    # Then we will add the new historyId and expiration date to the Firestore database
    # db = firestore.client(database_id="gmail-app")

    # doc_ref = db.collection("user_refresh_watch").document("me")
    # doc_ref.set({"historyId": "1234567890", "expiration": "1431990098200"})

    # Then we will return a success message

    return "SUCCESS"
