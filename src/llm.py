"""Grounded Ollama generation with a clean retrieval-only fallback."""

from dataclasses import dataclass
from urllib.parse import urlparse

import requests


@dataclass(frozen=True, slots=True)
class GenerationResult:
    answer: str | None
    available: bool
    error: str | None = None


def generate_answer(
    question: str,
    chunks: list[dict],
    model: str,
    base_url: str = "http://localhost:11434",
) -> GenerationResult:
    evidence = "\n\n".join(
        f"[{index}] {chunk.get('section', 'Unknown')} "
        f"(chunk {chunk.get('chunk_id', 'unknown')})\n{chunk.get('text', '')}"
        for index, chunk in enumerate(chunks, 1)
    )
    prompt = (
        "You are an evidence-grounded financial research assistant. Use only supplied evidence "
        "for filing claims and values. Never fabricate a value. Distinguish revenue from deferred "
        "revenue and net income from revenue. Tables may be imperfectly serialized. Separate "
        "historical facts from forward-looking statements. Use calculated tool values instead of "
        "doing arithmetic. If evidence is genuinely insufficient, say so. Cite excerpt number, "
        "section, and chunk ID.\n\n"
        f"Question: {question}\n\nEvidence:\n{evidence}\n\nAnswer:"
    )
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=180,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()
        if not answer:
            return GenerationResult(None, False, "Ollama returned an empty response.")
        return GenerationResult(answer, True)
    except (requests.RequestException, KeyError, ValueError):
        return GenerationResult(None, False, "Ollama is unavailable.")


def generate_general_answer(
    question: str,
    model: str,
    base_url: str = "http://localhost:11434",
    allow_remote: bool = False,
) -> GenerationResult:
    """Use configured Ollama only; remote endpoints require explicit opt-in."""
    parsed = urlparse(base_url)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if not local and not allow_remote:
        return GenerationResult(
            None,
            False,
            "Remote LLM use is disabled. Set ALLOW_REMOTE_LLM=true only after "
            "reviewing the provider's data-handling policy.",
        )
    prompt = (
        "You are ThesisLens in General mode. Answer the user's general question "
        "clearly and distinguish established facts, uncertainty, and opinion. "
        "Do not invent current news, private data, sources, or financial evidence. "
        "Do not claim access to accounts, files, or live information.\n\n"
        f"User question: {question}\n\nAnswer:"
    )
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=(2, 120),
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()
        if not answer:
            return GenerationResult(None, False, "The configured LLM returned no text.")
        return GenerationResult(answer, True)
    except (requests.RequestException, KeyError, ValueError):
        return GenerationResult(
            None,
            False,
            "General AI is not configured or the configured Ollama service is unavailable.",
        )
