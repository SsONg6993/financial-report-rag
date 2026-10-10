"""Grounded Ollama generation with a clean retrieval-only fallback."""

import time
from dataclasses import dataclass
from urllib.parse import urlparse

import requests


@dataclass(frozen=True, slots=True)
class GenerationResult:
    answer: str | None
    available: bool
    error: str | None = None
    error_code: str | None = None


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
    readiness_timeout: float = 5.0,
    inference_timeout: float = 120.0,
    readiness_retries: int = 1,
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
            "remote_llm_disabled",
        )
    endpoint = base_url.rstrip("/")
    tags = None
    for attempt in range(max(0, min(readiness_retries, 3)) + 1):
        try:
            tags = requests.get(
                f"{endpoint}/api/tags", timeout=(2, max(1.0, readiness_timeout))
            )
            tags.raise_for_status()
            break
        except requests.ConnectionError:
            if attempt >= readiness_retries:
                return GenerationResult(
                    None,
                    False,
                    f"Ollama service is not running at {base_url}. Start it with `ollama serve`.",
                    "ollama_service_not_running",
                )
            time.sleep(0.2 * (attempt + 1))
        except requests.Timeout:
            return GenerationResult(
                None,
                False,
                f"Ollama readiness check timed out at {base_url}; the service may still be loading.",
                "ollama_loading",
            )
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in {429, 503}:
                return GenerationResult(
                    None,
                    False,
                    f"Ollama model '{model}' is still loading. Retry shortly.",
                    "ollama_loading",
                )
            return GenerationResult(
                None,
                False,
                f"Ollama service at {base_url} returned an invalid status response.",
                "ollama_invalid_response",
            )
        except (requests.RequestException, KeyError, TypeError, ValueError):
            return GenerationResult(
                None,
                False,
                f"Ollama service at {base_url} returned an invalid status response.",
                "ollama_invalid_response",
            )
    try:
        models = tags.json().get("models", []) if tags is not None else []
        installed = {
            name
            for item in models
            for name in (item.get("name"), item.get("model"))
            if isinstance(name, str)
        }
    except requests.Timeout:
        # Kept for defensive compatibility with unusual response wrappers.
        return GenerationResult(None, False, "Ollama status timed out.", "ollama_loading")
    except (KeyError, TypeError, ValueError):
        return GenerationResult(
            None,
            False,
            f"Ollama service at {base_url} returned an invalid status response.",
            "ollama_invalid_response",
        )
    if model not in installed:
        return GenerationResult(
            None,
            False,
            f"Ollama model '{model}' is not installed locally. Model download requires explicit approval.",
            "ollama_model_missing",
        )
    prompt = (
        "You are ThesisLens in General mode. Answer the user's general question "
        "clearly and distinguish established facts, uncertainty, and opinion. "
        "Do not invent current news, private data, sources, or financial evidence. "
        "Do not claim access to accounts, files, or live information.\n\n"
        f"User question: {question}\n\nAnswer:"
    )
    response = None
    try:
        for attempt in range(2):
            try:
                response = requests.post(
                    f"{endpoint}/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                    timeout=(2, max(5.0, inference_timeout)),
                )
                response.raise_for_status()
                break
            except requests.ConnectionError:
                if attempt:
                    raise
                time.sleep(0.2)
        if response is None:
            raise requests.ConnectionError("No Ollama response")
        answer = response.json().get("response", "").strip()
        if not answer:
            return GenerationResult(None, False, "The configured LLM returned no text.")
        return GenerationResult(answer, True)
    except requests.ConnectionError:
        return GenerationResult(
            None,
            False,
            f"Ollama service stopped responding at {base_url}.",
            "ollama_service_not_running",
        )
    except requests.Timeout:
        return GenerationResult(
            None,
            False,
            f"Ollama model '{model}' timed out before producing a response.",
            "ollama_timeout",
        )
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in {429, 503}:
            return GenerationResult(
                None,
                False,
                f"Ollama model '{model}' is still loading. Retry shortly.",
                "ollama_loading",
            )
        return GenerationResult(
            None,
            False,
            f"Ollama model '{model}' returned an invalid response.",
            "ollama_invalid_response",
        )
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return GenerationResult(
            None,
            False,
            f"Ollama model '{model}' returned an invalid response.",
            "ollama_invalid_response",
        )
