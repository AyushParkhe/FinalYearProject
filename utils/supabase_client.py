from supabase import create_client
from httpx import Timeout
import os

# Increase timeout to 60s to handle the 800+ entries without crashing
supabase = create_client(
    os.getenv("SUPABASE_URL"), 
    os.getenv("SUPABASE_SERVICE_KEY"),
    options={"timeout": Timeout(60.0)}
)