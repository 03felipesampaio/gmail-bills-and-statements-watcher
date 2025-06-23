from google.cloud import secretmanager
from google.cloud import storage
import base64
import json
import yaml

def get_secret_yaml(secret_name: str) -> dict:
    """
    Reads a secret value from Google Secret Manager, assuming it's a YAML file,
    and returns its content as a dictionary.
    """
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(request={"name": secret_name})
    return yaml.safe_load(response.payload.data.decode("UTF-8"))

def get_client_credentials_from_secret_manager(secret_name: str) -> dict:
    """
    Fetches the OAuth client ID and client secret from Google Secret Manager.
    Returns the client configuration as a dictionary.
    """
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(request={"name": secret_name})
    return json.loads(response.payload.data.decode("UTF-8"))


def decode_topic_message(topic_message_data: str) -> dict:
    message_content_json_str = base64.b64decode(
        topic_message_data["message"]["data"]
    ).decode("utf8")

    return json.loads(message_content_json_str)


def get_bucket(bucket_name) -> storage.Bucket:
    return storage.Client().bucket(bucket_name)