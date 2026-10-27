import tomllib
from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


def get_project_version() -> str:
    pyproject_path = Path(__file__).resolve().parent / "pyproject.toml"

    if not pyproject_path.exists():
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            return (
                data.get("project", {}).get("version")
                or data.get("tool", {}).get("poetry", {}).get("version")
                or "0.0.0-dev"
            )
    except Exception:
        return "0.0.0-dev"


class Settings(BaseSettings):
    # APP
    app_name: str = "0w_sv"
    app_version: str = get_project_version()
    host_port: int = 8000

    # DB
    host_db_port: int = 5432
    db_user: str = "jmpt"
    db_password: str = "jmpt"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "jmpt"
    db_test_name: str = "jmpt_test"

    # CACHE
    host_cache_port: int = 6379
    cache_host: str = "localhost"
    cache_port: int = 6379
    cache_db: int = 0
    cache_password: str = ""
    cache_default_ttl: int = 300

    # RABBITMQ
    host_rabbitmq_port: int = 5672
    host_rabbitmq_mgmt_port: int = 15672
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "admin"
    rabbitmq_password: str = "admin"
    rabbitmq_queue_name: str = "jmpt_queue"
    rabbitmq_mgmt_port: int = 15672

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
