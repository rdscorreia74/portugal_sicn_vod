import os

BASE_URL = "https://sicnoticias.pt"
ALLOWED_DOMAIN = "sicnoticias.pt"

# Concurrency & Network settings
MAX_CONCURRENT_REQUESTS = 5
TIMEOUT = 15
MAX_DEPTH = 2

# Output settings
OUTPUT_DIR = "./output"
os.makedirs(OUTPUT_DIR, exist_ok=True)
