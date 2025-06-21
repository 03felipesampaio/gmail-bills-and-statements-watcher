import os
from pathlib import Path
from loguru import logger

import functions_framework


from . import setup_env

settings = setup_env.load_and_validate_environment(
    Path(os.getenv("YAML_CONFIG_PATH", "./env.yaml"))
)

@functions_framework.http
def oauth_callback_function(request):
    """Cloud function to handle OAuth flow to get app permissions
    for gmail accounts.
    """
    logger.info("OAuth callback Cloud Function triggered.")
    request_args = request.args
    auth_code = request_args.get("code")