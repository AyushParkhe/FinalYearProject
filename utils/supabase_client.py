import os
from supabase import create_client, ClientOptions
from dotenv import load_dotenv

# Ensure environment variables are loaded immediately 
load_dotenv()

# Use the official ClientOptions class to set the 60-second timeout
opts = ClientOptions(postgrest_client_timeout=60.0)

# Create the stateless HTTP client
supabase = create_client(
    os.getenv("SUPABASE_URL"), 
    os.getenv("SUPABASE_SERVICE_KEY"),
    options=opts
)