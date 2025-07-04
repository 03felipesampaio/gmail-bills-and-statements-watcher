from . import models

class MessageFullWrapper:
    def __init__(self, message: models.MessageFull):
        self.message = message
        self.headers = self._load_headers_dict()

    def _load_headers_dict(self):
        """
        Returns the headers of the message as a dictionary.
        """
        headers = getattr(self.message, "payload", {}).get("headers", [])
        return {h["name"]: h["value"] for h in headers if "name" in h and "value" in h}

    def __getitem__(self, item):
        # Virtualize access to certain keys from Conditions
        if item == "from_":
            # Access the "From" header
            return self.headers.get("From")
        elif item == "to":
            # Access the "To" header
            return self.headers.get("To")
        elif item == "subject":
            # Access the "Subject" header
            return self.headers.get("Subject")
        
        return self.message[item]

    def __setitem__(self, key, value):
        self.message[key] = value

    def __repr__(self):
        return f"MessageFullWrapper({self.message})"