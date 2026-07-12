from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Serviços Externos
    ollama_url: str = "http://ollama_ia:11434"
    qdrant_url: str = "http://qdrant_vector_db_ia:6333"
    database_url: str = "postgresql+asyncpg://admin:senha_segura_db@postgres_db_ia:5432/painel_rag"
    redis_url: str = "redis://redis_cache_ia:6379"

    # LLM
    llm_model: str = "llama3"
    embedding_model: str = "nomic-embed-text"

    # SuperAdmin
    superadmin_email: str = "admin@camara.gov.br"
    superadmin_password: str = "Admin@2024"
    superadmin_nome: str = "Super Administrador"

    # JWT
    jwt_secret: str = "troque-por-uma-chave-segura"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    jwt_algorithm: str = "HS256"

    # Qdrant
    qdrant_collection: str = "camara_documentos"

    # Upload
    max_upload_size_mb: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
