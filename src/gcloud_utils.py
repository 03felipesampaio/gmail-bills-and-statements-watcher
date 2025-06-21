from google.cloud import secretmanager
import json

def get_client_credentials_from_secret_manager(secret_name: str) -> dict:
    """
    Fetches the OAuth client ID and client secret from Google Secret Manager.
    Returns the client configuration as a dictionary.
    """
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(
        request={"name": secret_name}
    )
    return json.loads(response.payload.data.decode("UTF-8"))