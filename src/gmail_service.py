from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

class GmailService:
    def __init__(self, service):
        self.service = service
        
    def watch(self, topic: str) -> dict:
        res = self.service.users().watch(userId="me", body={"topicName": topic}).execute()
        
        return res
        
    

def build_user_gmail_service(creds: Credentials):
    if not creds or not creds.valid:
        raise ValueError("Received a not valid credentials for build service.")
    
    service = build("gmail", "v1", credentials=creds)

    return service