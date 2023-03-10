import os

from dotenv import load_dotenv
from jupyter_server.auth import passwd

load_dotenv()

PROJECT_NAME = os.environ.get("PROJECT_NAME", "ml-workstation-ecs")
STAGE = os.environ.get("STAGE", "prod")

_plaintext_password = os.environ.get("JUPYTER_LAB_PASSWORD") or exit(
    "Please provide a password for the Jupyter Lab instance"
)

JUPYTER_LAB_PASSWORD = passwd(_plaintext_password)
