

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