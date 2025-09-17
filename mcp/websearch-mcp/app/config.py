from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_ignore_empty=True,
        extra="ignore"
    )

    DEFAULT_LANG: str = Field("ko")
    DEFAULT_REGION: str = Field("KR")
    TIMEOUT_SECONDS: int = Field(6)
    MAX_CONCURRENCY: int = Field(4)

    GOOGLE_SEARCH_API_KEY: str | None = None
    GOOGLE_CX_ID: str | None = None

    NAVER_CLIENT_ID: str | None = None
    NAVER_CLIENT_SECRET: str | None = None

    PROVIDER_WEIGHTS: dict[str, float] = Field(
        default_factory=lambda: {
            "google_cse": 1.0,
            "google_news_rss": 0.9,
            "naver_web": 0.9,
            "naver_news": 0.9,
            "naver_blog": 0.8,
        }
    )

    CHANNEL_PRIORITY: list[str] = Field(default_factory=lambda: ["news", "web", "blog"])
    ALLOW_SCRAPE: bool = Field(False)
    ENABLE_CACHE: bool = Field(False)




settings = Settings()  # eagerly load


