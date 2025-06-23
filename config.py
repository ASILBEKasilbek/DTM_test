import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_PATH = "users.db"
WEBSITE_URL = "http://3.112.252.179:80" 