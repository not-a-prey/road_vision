import os

STORE_HOST = os.environ.get("STORE_HOST") or "localhost"
STORE_PORT = os.environ.get("STORE_PORT") or 8000
ENABLE_CSV_FALLBACK = os.environ.get("ENABLE_CSV_FALLBACK", "false").lower() == "true"
