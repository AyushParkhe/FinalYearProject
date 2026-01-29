import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

HEADERS = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
}

def supabase_request(method, endpoint, json=None):
    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    response = requests.request(
        method,
        url,
        headers=HEADERS,
        json=json,
    )
    response.raise_for_status()
    return response.json() if response.text else None
