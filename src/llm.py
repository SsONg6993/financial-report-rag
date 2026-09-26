"""Grounded Ollama generation with a clean retrieval-only fallback."""

from dataclasses import dataclass

import requests


@dataclass(frozen=True, slots=True)
class GenerationResult:
    answer: str | None
    available: bool
    error: str | None = None


def generate_answer(question: str, chunks: list[dict], model: str,
                    base_url: str = "http://localhost:11434") -> GenerationResult:
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
            json={"model": model, "prompt": prompt, "stream": False}, timeout=180,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()
        if not answer:
            return GenerationResult(None, False, "Ollama returned an empty response.")
        return GenerationResult(answer, True)
    except (requests.RequestException, KeyError, ValueError):
        return GenerationResult(None, False, "Ollama is unavailable.")
