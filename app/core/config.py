from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from typing import Literal
class Settings(BaseSettings):
    APP_NAME: str = "MyApp"
    DATA_BASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/invdb"
    ENV : Literal["DEV", "PROD"] = "dev"

    API_KEY: SecretStr | None = None
    model_config = SettingsConfigDict(env_file=".env",
    case_sensitive = True,
    extra = "ignore"
    )

settings = Settings()

