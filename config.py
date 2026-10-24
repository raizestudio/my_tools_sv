# from typing import List

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # APP
    app_name: str = "JMPT"
    app_version: str = "0.0.1"

    supabase_url: str = ""
    supabase_key: str = ""

    model_config = ConfigDict(env_file=".env")
