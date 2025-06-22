import os
from pathlib import Path
from loguru import logger
from datetime import datetime

import functions_framework
from google.cloud import firestore


from . import setup_env
from . import gcloud_utils
from . import oauth_utils
from . import firestore_service
from . import gmail_service

settings = setup_env.load_and_validate_environment(
    Path(os.getenv("YAML_CONFIG_PATH", "./env.yaml"))
)

db = firestore_service.FirestoreService(
    firestore.Client(database=settings.FIRESTORE_DATABASE_ID)
)


@functions_framework.http
def oauth_callback_function(request):
    """Cloud function to handle OAuth flow to get app permissions
    for gmail accounts.
    """
    logger.info("OAuth callback Cloud Function triggered.")
    request_args = request.args
    auth_code = request_args.get("code")

    if not auth_code:
        logger.error("Error: Authorization code not found in the request.")
        return "Error: Authorization code not found. Please try again.", 400

    gmail_client_id = gcloud_utils.get_client_credentials_from_secret_manager(
        settings.APP_CLIENT_ID_SECRET
    )

    try:
        creds = oauth_utils.start_oauth_flow(
            gmail_client_id,
            auth_code,
            settings.OAUTH_SCOPES,
            settings.APP_OAUTH_FUNCTION_URI,
        )

        user_email = oauth_utils.get_user_email_from_credentials(creds)
    except ValueError as e:
        logger.error(e)
        return str(e), 400

    db.set_user_auth_tokens(user_email, creds)
    logger.info(f"OAuth tokens for {user_email} successfully saved to database.")

    return "SUCCESSFULLY AUTHORIZED", 200


@functions_framework.http
def refresh_watch(request):
    users_refreshed = []
    users_failed = {}

    for user_ref in db.get_all_users_iterator():
        try:
            user_data = user_ref.to_dict()

            if not user_data.get("authTokens"):
                logger.warning(
                    f"There is no tokens for user '{user_ref.id}'. Skipping..."
                )
                continue

            creds = oauth_utils.refresh_user_credentials(
                user_data["authTokens"], settings.OAUTH_SCOPES
            )
            db.set_user_auth_tokens(user_ref.id, creds)
            gmail = gmail_service.GmailService(
                gmail_service.build_user_gmail_service(creds)
            )
            watch_res = gmail.watch(settings.PUBSUB_TOPIC)

            with db.client.transaction() as transaction:
                db.update_user_last_watch(
                    transaction,
                    user_ref.id,
                    datetime.now(),
                    datetime.fromtimestamp(int(watch_res["expiration"][:-3])),
                    watch_res["historyId"],
                )

            users_refreshed.append(user_ref.id)
        except Exception as e:
            users_failed[user_ref.id] = {"errorMessage": str(e)}

    return {"usersRefreshed": users_refreshed, "failed": users_failed}, 200
