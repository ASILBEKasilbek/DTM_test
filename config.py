import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_PATH = "users.db"
WEBSITE_URL = "http://3.112.252.179:80" 
# WEBSITE_URL = "http://127.0.0.1:8000" 
ADMIN_IDS = ["5306481482","5287450751"]
MANDATORY_CHANNELS = ['@tayorlov_uz']  