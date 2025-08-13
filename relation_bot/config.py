import os
from dotenv import load_dotenv


load_dotenv(dotenv_path="/home/namu101/msga/env")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash-lite"

DATA_DIR = "/home/namu101/msga/data"

RELATION_BOT_DATABASE = os.path.join(DATA_DIR, 'relation_bot.db')
MAIN_DATABASE = os.path.join(DATA_DIR, 'sh_navigator.db')

NETWORK_SERVER_URL = "http://146.190.98.230:8002"