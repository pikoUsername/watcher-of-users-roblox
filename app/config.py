from functools import lru_cache
from typing import List

from pydantic import BaseSettings, SecretStr


class Settings(BaseSettings):
    db_dsn: str
    db_tokens_table: str
    queue_dsn: str

    user_agent: str = "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
                      "AppleWebKit/537.36 (KHTML, like Gecko)" \
                      "Chrome/87.0.4280.141 Safari/537.36"

    debug: bool = True

    loggers: List[str] = []

    class Config:
        validate_assignment = True
        env_file = "../.env"


@lru_cache
def get_settings():
    setting = Settings()
    return setting
