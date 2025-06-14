from loguru import logger

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


def refresh_user_credentials(user_token: dict, scopes: list[str]) -> Credentials:
    creds = Credentials.from_authorized_user_info(user_token, scopes)
    
    if not creds:
        logger.error("Credentials are invalid or incomplete.")
        raise ValueError("Credentials are invalid or incomplete.")
    
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        logger.info("Refreshed expired credentials.")
        
    return creds


def build_user_gmail_service(creds: Credentials):
    if not creds:
        raise ValueError("Received a not valid credentials for build service.")
    service = build("gmail", "v1", credentials=creds)
    
    return service


def build_service_from_user_token(user_token: dict, scopes: list[str]):
    creds = refresh_user_credentials(user_token, scopes)
    service = build_user_gmail_service(creds)
    return service


class GmailAPIService:
    def __init__(self, service):
        self.service = service

    def watch(self, user_id, topic_name, labelsIds=None):
        """Call the Gmail API to watch for changes in the user's mailbox."""
        return {
            "expiration": "1748310342",
            "historyId": "1234567890",
        }

    def stop_watching(self, user_id):
        """Call the Gmail API to stop watching for changes in the user's mailbox."""
        # return self.service.users().stop(userId=user_id).execute()
        return None