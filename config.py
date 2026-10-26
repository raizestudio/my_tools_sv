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

    # CACHE
    cache_host: str = "localhost"
    cache_port: int = 6379
    cache_db: int = 0
    cache_password: str = ""
    cache_default_ttl: int = 300

    # RABBITMQ
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "admin"
    rabbitmq_password: str = "admin"
    rabbitmq_queue_name: str = "jmpt_queue"

    @property
    def db_url(self) -> str:
        return f"postgres://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def db_url_test(self) -> str:
        return f"postgres://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_test_name}"

    @property
    def rabbitmq_url(self) -> str:
        return f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}@{self.rabbitmq_host}:{self.rabbitmq_port}/%2F"

    @property
    def valkey_url(self) -> str:
        return f"redis://{self.cache_host}:{self.cache_port}/{self.cache_db}"

    models: list[str] = [
        # "core",
        "url_shtnr",
        "secret",
        "webhook",
    ]

    model_config = ConfigDict(env_file=".env")
