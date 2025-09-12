from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )
    OPENAI_API_KEY: str
    MODEL_NAME: str
    BASE_URL: str | None = None


settings = Settings() 