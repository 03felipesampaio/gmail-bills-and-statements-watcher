from pathlib import Path
import yaml
from loguru import logger

import functions_framework
from google.cloud import firestore

from . import repository
# from . import gmail

logger.info("Starting Gmail Bills and Statements Message Watcher")

ENV_VARS_YAML_PATH = Path("./env.yaml")

if ENV_VARS_YAML_PATH.exists():
    ENV_VARS = yaml.safe_load(ENV_VARS_YAML_PATH.open(encoding="utf8"))
else:
    raise FileNotFoundError("Failed to find YAML file with variables")


PROJECT_ID = ENV_VARS["PROJECT_ID"]
REGION = ENV_VARS["REGION"]
PUBSUB_TOPIC = ENV_VARS["PUBSUB_TOPIC"]
FIRESTORE_DATABASE_ID = ENV_VARS["FIRESTORE_DATABASE_ID"]

db = repository.FirestoreRepository(firestore.Client(database=FIRESTORE_DATABASE_ID))


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

    # gmail_service = gmail.GmailAPIService(None)

    # # If the expiration date is less than current date is due, we trow a warning, informing that a synchronization is needed
    # # db.delete_user_me()
    user = db.get_user_me()
    logger.info(f"Queried user '{user.id}' || {user.to_dict()}")

    # watch_response = gmail_service.watch(user.id, PUBSUB_TOPIC)
    # logger.info(f"Refreshed Pub/Sub watch for user '{user.id}' || {watch_response}")

    # db.update_user_last_refresh(
    #     user.id,
    #     datetime.now(),
    #     datetime.fromtimestamp(int(watch_response["expiration"])),
    #     history_id=watch_response["historyId"],
    # )

    return ("SUCCESS", 200)
