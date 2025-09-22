from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# 필요한 환경변수 지정.
# 환경변수 주입은 실행처(server) 에서 mcp.json 에 명시
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_ignore_empty=True,
        extra="ignore"
    )

    EXAMPLE_CONFIG: str = Field("example")




settings = Settings()  # eagerly load


