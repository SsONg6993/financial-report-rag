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
    exception_type: str | None = None


def _response_text(response: requests.Response) -> str | None:
    """Return Ollama text only when the response has the documented shape."""
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    value = payload.get("response")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _installed_models(response: requests.Response) -> set[str]:
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise TypeError("Invalid Ollama model-list response")
    return {
        name
        for item in payload["models"]
        if isinstance(item, dict)
        for name in (item.get("name"), item.get("model"))
        if isinstance(name, str)
    }


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
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "30s",
            },
            timeout=180,
        )
        response.raise_for_status()
        answer = _response_text(response)
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
        except requests.ConnectionError as exc:
            if attempt >= readiness_retries:
                return GenerationResult(
                    None,
                    False,
                    f"Ollama service is not running at {base_url}. Start it with `ollama serve`.",
                    "ollama_service_not_running",
                    type(exc).__name__,
                )
            time.sleep(0.2 * (attempt + 1))
        except requests.Timeout as exc:
            return GenerationResult(
                None,
                False,
                f"Ollama readiness check timed out at {base_url}; the service may still be loading.",
                "ollama_loading",
                type(exc).__name__,
            )
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in {429, 503}:
                return GenerationResult(
                    None,
                    False,
                    f"Ollama model '{model}' is still loading. Retry shortly.",
                    "ollama_loading",
                    type(exc).__name__,
                )
            return GenerationResult(
                None,
                False,
                f"Ollama service at {base_url} returned an invalid status response.",
                "ollama_invalid_response",
                type(exc).__name__,
            )
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            return GenerationResult(
                None,
                False,
                f"Ollama service at {base_url} returned an invalid status response.",
                "ollama_invalid_response",
                type(exc).__name__,
            )
    try:
        installed = _installed_models(tags) if tags is not None else set()
    except requests.Timeout as exc:
        # Kept for defensive compatibility with unusual response wrappers.
        return GenerationResult(
            None,
            False,
            "Ollama status timed out.",
            "ollama_loading",
            type(exc).__name__,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return GenerationResult(
            None,
            False,
            f"Ollama service at {base_url} returned an invalid status response.",
            "ollama_invalid_response",
            type(exc).__name__,
        )
    if model not in installed:
        return GenerationResult(
            None,
            False,
            f"Ollama model '{model}' is not installed locally. Model download requires explicit approval.",
            "ollama_model_missing",
            "ConfigurationError",
        )
    prompt = (
        "You are ThesisLens in General mode. Answer the user's question directly and "
        "concisely by default. Expand only when the question needs detail. Distinguish "
        "established facts, uncertainty, and opinion without repeating generic disclaimers. "
        "Do not invent current news, private data, sources, or financial evidence. "
        "Do not claim access to accounts, files, or live information. Do not add citations, "
        "source lists, or claims of verification because no sources were retrieved for this "
        "General-mode request.\n\n"
        f"User question: {question}\n\nAnswer:"
    )
    response = None
    try:
        for attempt in range(2):
            try:
                response = requests.post(
                    f"{endpoint}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "keep_alive": "30s",
                    },
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
        answer = _response_text(response)
        if not answer:
            return GenerationResult(
                None,
                False,
                "The configured Ollama model returned an invalid or empty response. Retry the request.",
                "ollama_invalid_response",
                "InvalidResponse",
            )
        return GenerationResult(answer, True)
    except requests.ConnectionError as exc:
        return GenerationResult(
            None,
            False,
            f"Ollama service stopped responding at {base_url}.",
            "ollama_service_not_running",
            type(exc).__name__,
        )
    except requests.Timeout as exc:
        return GenerationResult(
            None,
            False,
            f"Ollama model '{model}' timed out before producing a response.",
            "ollama_timeout",
            type(exc).__name__,
        )
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in {429, 503}:
            return GenerationResult(
                None,
                False,
                f"Ollama model '{model}' is still loading. Retry shortly.",
                "ollama_loading",
                type(exc).__name__,
            )
        return GenerationResult(
            None,
            False,
            f"Ollama model '{model}' returned an invalid response.",
            "ollama_invalid_response",
            type(exc).__name__,
        )
    except requests.RequestException as exc:
        return GenerationResult(
            None,
            False,
            f"Ollama model '{model}' encountered a temporary inference error. Retry the request.",
            "ollama_temporary_error",
            type(exc).__name__,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return GenerationResult(
            None,
            False,
            f"Ollama model '{model}' returned an invalid response.",
            "ollama_invalid_response",
            type(exc).__name__,
        )
