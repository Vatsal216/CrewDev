from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # API Keys (all optional — multi-provider)
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    azure_api_key: str = ""
    azure_api_base: str = ""
    azure_api_version: str = ""
    ollama_base_url: str = ""
    ollama_api_key: str = ""
    voyage_api_key: str = ""
    tavily_api_key: str = ""

    # App
    app_secret: str = ""

    # Database
    database_url: str = "postgresql+asyncpg://crewdev:crewdev@localhost/crewdev"
    redis_url: str = "redis://localhost:6379"

    # Paths
    chroma_path: str = "./chroma_db"
    workspace_path: str = "./workspace"

    # Models
    llm_model: str = "claude-sonnet-4-6"
    embed_model: str = "voyage-3"

    # Agent config
    max_validation_iter: int = 3
    max_agent_iter: int = 5
    short_term_history_k: int = 20
    max_request_tokens: int = 200_000

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Ensure paths exist
Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
Path(settings.workspace_path).mkdir(parents=True, exist_ok=True)
