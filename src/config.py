"""Environment-backed configuration with conservative local-first defaults."""

import os
from dataclasses import dataclass


def _boolean(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return (
        default
        if value is None
        else value.strip().lower() in {"1", "true", "yes", "on"}
    )


@dataclass(frozen=True, slots=True)
class AppConfig:
    sec_user_agent: str
    embedding_model: str
    qdrant_path: str
    ollama_base_url: str
    ollama_model: str
    ollama_readiness_timeout: float
    ollama_inference_timeout: float
    ollama_readiness_retries: int
    allow_remote_llm: bool
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
            ollama_base_url=os.getenv(
                "OLLAMA_BASE_URL", os.getenv("OLLAMA_URL", "http://localhost:11434")
            ),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:4b"),
            ollama_readiness_timeout=float(
                os.getenv("OLLAMA_READINESS_TIMEOUT_SECONDS", "5")
            ),
            ollama_inference_timeout=float(
                os.getenv("OLLAMA_INFERENCE_TIMEOUT_SECONDS", "120")
            ),
            ollama_readiness_retries=max(
                0, min(int(os.getenv("OLLAMA_READINESS_RETRIES", "1")), 3)
            ),
            allow_remote_llm=_boolean("ALLOW_REMOTE_LLM"),
            enable_jev=_boolean("ENABLE_JEV"),
            typesafe_api_key=os.getenv("TYPESAFE_API_KEY", "").strip(),
            jev_model=os.getenv("JEV_MODEL", "jev-latest"),
            jev_confidence_threshold=float(
                os.getenv("JEV_CONFIDENCE_THRESHOLD", "0.70")
            ),
            chunk_size=int(os.getenv("CHUNK_SIZE", "1600")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
        )
