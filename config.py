from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # APP
    app_name: str = "JMPT"
    app_version: str = "0.0.1"

    # DB
    db_user: str = "jmpt"
    db_password: str = "jmpt"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "jmpt"
    db_test_name: str = "jmpt_test"

    @property
    def db_url(self) -> str:
        return f"postgres://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def db_url_test(self) -> str:
        return f"postgres://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_test_name}"

    models: list[str] = [
        # "core",
        "url_shtnr",
        "secret",
        "webhook",
    ]

    model_config = ConfigDict(env_file=".env")
