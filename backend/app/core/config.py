"""
CURATOR — Application Configuration
Centralised settings loaded from environment / .env file.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "CURATOR"
    app_env: Literal["development", "production"] = "development"
    app_debug: bool = True
    app_secret_key: str = "change-me"
    allowed_origins: list[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"]
    )

    # LLM Providers
    # "offline" = deterministic extractive answers without any external API
    # (used automatically when no API key is configured).
    active_llm: Literal["anthropic", "openai", "offline"] = "anthropic"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # Embeddings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_device: str = "cpu"

    # Vector Store
    vector_store: Literal["faiss", "pinecone"] = "faiss"
    faiss_index_path: str = "data/embeddings/curriculum.faiss"
    faiss_metadata_path: str = "data/embeddings/curriculum_metadata.json"

    pinecone_api_key: str = ""
    pinecone_env: str = ""
    pinecone_index: str = "curator-curriculum"

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "curator_password"
    neo4j_database: str = "neo4j"        # Community Edition supports only the default database

    # Curriculum data
    # "kusom": the imported 2025–2026 KUSOM timetables and objectives
    # (app/data/kusom/kusom_2025_2026.json); "placeholder": the hand-written
    # demonstration curriculum.  Falls back to placeholder if the file is absent.
    curriculum_source: Literal["kusom", "placeholder"] = "kusom"

    # Institution
    default_institution: str = "koc_university"
    default_language: Literal["en", "tr"] = "en"

    # RAG Pipeline
    rag_top_k_vector: int = 5
    rag_top_k_graph: int = 10
    rag_top_k_bm25: int = 5
    rag_fusion_top_k: int = 8
    rag_max_tokens: int = 1500
    rag_temperature: float = 0.1

    # MİMAR research prototype
    mimar_db_path: str = "data/mimar/mimar.sqlite3"
    mimar_admin_token: str = "dev-admin-token"   # override via MIMAR_ADMIN_TOKEN outside development


@lru_cache
def get_settings() -> Settings:
    return Settings()
