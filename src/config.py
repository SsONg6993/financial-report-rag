"""Environment-backed configuration with conservative local-first defaults."""

import os
from dataclasses import dataclass


def _boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AppConfig:
    sec_user_agent: str
    embedding_model: str
    qdrant_path: str
    ollama_base_url: str
    ollama_model: str
    enable_jev: bool
    typesafe_api_key: str
    jev_model: str
    jev_confidence_threshold: float
    chunk_size: int
    chunk_overlap: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            sec_user_agent=os.getenv("SEC_USER_AGENT", "").strip(),
            embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
            qdrant_path=os.getenv("QDRANT_PATH", "data/vector_store"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", os.getenv("OLLAMA_URL", "http://localhost:11434")),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:4b"),
            enable_jev=_boolean("ENABLE_JEV"),
            typesafe_api_key=os.getenv("TYPESAFE_API_KEY", "").strip(),
            jev_model=os.getenv("JEV_MODEL", "jev-latest"),
            jev_confidence_threshold=float(os.getenv("JEV_CONFIDENCE_THRESHOLD", "0.70")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "1600")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
        )
