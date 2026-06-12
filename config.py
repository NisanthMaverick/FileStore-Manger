import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
MAIN_BOT_TOKEN = os.environ.get("MAIN_BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not API_ID or not API_HASH or not MAIN_BOT_TOKEN or not OWNER_ID or not DATABASE_URL:
    raise ValueError("Missing critical configuration in environment variables or .env file.")
