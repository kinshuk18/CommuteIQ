"""
config.py — Centralised settings loaded from environment variables.
Uses pydantic-settings so values can come from .env, Docker, or K8s secrets.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parent.parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(_ROOT_ENV), ".env"], env_file_encoding="utf-8", extra="ignore"
    )

    # Postgres
    db_url: str = "host=localhost port=5434 dbname=commuteiq user=commuteiq password=commuteiq"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Kafka
    kafka_bootstrap: str = "localhost:9092"
    kafka_enabled: bool = True

    # LLM (OpenAI-compatible endpoint — default: Gemini)
    llm_provider: str = "openai_compat"
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_model: str = "gemini-3.8-flash"
    llm_api_key: str = ""
    llm_timeout: int = 5
    llm_max_retries: int = 0

    # Anthropic (optional fallback)
    anthropic_api_key: str = ""

    # Groq fallback
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # LLM Cache
    llm_cache_path: str = "llm_cache.sqlite"

    # Shared secret with gateway
    ai_shared_secret: str = "changeme-dev-secret"

    # MLflow
    mlflow_tracking_uri: str = "sqlite:///mlflow.db"
    mlflow_experiment_name: str = "runtime-regressor"

    # Vector store
    faiss_index_path: str = "faiss_index"
    vector_backend: str = "faiss"  # faiss | pinecone | weaviate

    # Pinecone (env-enabled)
    pinecone_api_key: str = ""
    pinecone_index_name: str = "commuteiq"

    # Weaviate
    weaviate_url: str = "http://localhost:8888"

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"

    # Service
    log_level: str = "INFO"
    max_input_length: int = 2000


settings = Settings()
