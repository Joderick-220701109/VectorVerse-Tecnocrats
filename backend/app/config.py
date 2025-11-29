import os
from dataclasses import dataclass

from dotenv import load_dotenv, find_dotenv

# Load environment variables from nearest .env (project root when running from backend/)
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path=dotenv_path)
else:
    load_dotenv()


@dataclass
class Config:
    """
    Application configuration loaded from environment variables (.env)
    """

    # === Database ===
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_NAME: str = os.getenv("DB_NAME", "RAG_Bot")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_PORT: int = int(os.getenv("DB_PORT", "5432"))

    # === File Storage ===
    UPLOAD_FOLDER: str = os.getenv(
        "UPLOAD_FOLDER",
        os.path.join(os.getcwd(), "data", "uploads")
    )
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "1024"))

    # === Chunking / Retrieval ===
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "450"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "75"))
    MAX_CONTEXT_CHUNKS: int = int(os.getenv("MAX_CONTEXT_CHUNKS", "8"))
    DEFAULT_TOP_K: int = int(os.getenv("DEFAULT_TOP_K", "5"))

    # === Gemini / LLM ===
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    GEMINI_RESPONSE_MIME_TYPE: str = os.getenv(
        "GEMINI_RESPONSE_MIME_TYPE",
        "application/json"
    )

    # === Embedding Models ===
    TEXT_EMBEDDING_MODEL: str = os.getenv("TEXT_EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    IMAGE_EMBEDDING_MODEL: str = os.getenv("IMAGE_EMBEDDING_MODEL", "laion/CLIP-ViT-H-14-laion2B-s32B-b79K")
    TEXT_EMBEDDING_DIM: int = int(os.getenv("TEXT_EMBEDDING_DIM", "1024"))
    IMAGE_EMBEDDING_DIM: int = int(os.getenv("IMAGE_EMBEDDING_DIM", "1024"))
    USE_PGVECTOR: bool = os.getenv("USE_PGVECTOR", "true").lower() in ("true", "1", "yes")

    # === Processing Controls ===
    ENABLE_IMAGE_EMBEDDING: bool = os.getenv("ENABLE_IMAGE_EMBEDDING", "true").lower() in ("true", "1", "yes")
    MAX_PAGES_PER_DOC: int | None = (
        int(os.getenv("MAX_PAGES_PER_DOC")) if os.getenv("MAX_PAGES_PER_DOC") else None
    )

    # === Auth ===
    AUTH_SECRET: str = os.getenv("AUTH_SECRET", "change-this-secret")
    AUTH_TOKEN_MAX_AGE: int = int(os.getenv("AUTH_TOKEN_MAX_AGE", "604800"))
