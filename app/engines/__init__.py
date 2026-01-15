from dotenv import load_dotenv, find_dotenv

path = find_dotenv(usecwd=True) or find_dotenv()
load_dotenv(path, override=True)

# Optional: package-level state (NO self here)
_STATE = {
    "stage": "greeting",
}