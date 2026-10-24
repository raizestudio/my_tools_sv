from supabase import Client, create_client

from config import Settings

settings = Settings()

supabase_client: Client = create_client(settings.supabase_url, settings.supabase_key)
