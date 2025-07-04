# local_auth_script.py (Seu script Python local para iniciar o fluxo)
import json
import yaml # type: ignore
from pathlib import Path
from google.cloud import secretmanager
from google_auth_oauthlib.flow import Flow # type: ignore

# --- Configuration (same as your project) ---
ENV_VARS_YAML_PATH = Path("./env.yaml")
if ENV_VARS_YAML_PATH.exists():
    ENV_VARS = yaml.safe_load(ENV_VARS_YAML_PATH.open(encoding="utf8"))
else:
    raise FileNotFoundError("Failed to find YAML file with variables")


# --- Helper Function (same as your project) ---
def get_client_credentials_from_secret_manager() -> dict:
    """
    Fetches the OAuth client ID and client secret from Google Secret Manager.
    Returns the client configuration as a dictionary.
    """
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(
        request={"name": ENV_VARS["APP_CLIENT_ID_SECRET"]}
    )
    return json.loads(response.payload.data.decode("UTF-8"))


# --- Script to Initiate the Flow ---
if __name__ == "__main__":
    print("Generating OAuth authorization URL for your Cloud Function...")

    client_config = get_client_credentials_from_secret_manager()

    # O URI de redirecionamento para a sua Cloud Function é pego do seu env.yaml local
    # IMPORTANTE: Este valor deve ser o URL público exato da sua Cloud Function implantada.
    CLOUD_FUNCTION_REDIRECT_URI = ENV_VARS["APP_OAUTH_FUNCTION_URI"]

    flow = Flow.from_client_config(
        client_config, scopes=ENV_VARS["OAUTH_SCOPES"], redirect_uri=CLOUD_FUNCTION_REDIRECT_URI
    )

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
    )

    print(
        "\n--------------------------------------------------------------------------------------------------"
    )
    print(
        "Please copy the URL below and paste it into your browser to authorize your application:"
    )
    print(authorization_url)
    print(
        "--------------------------------------------------------------------------------------------------"
    )
    print(
        "\nAfter authorization, Google will redirect to your Cloud Function, which will process and save the token."
    )
    print("Check your Cloud Function logs and Firestore to confirm success.")
