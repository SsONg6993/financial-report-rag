"""Ollama HTTP call; connection failures let the UI show retrieval evidence alone."""

import requests


def generate_answer(question: str, chunks: list[dict], model: str,
                    base_url: str = "http://localhost:11434") -> str:
    evidence = "\n\n".join(
        f"[{index}] {chunk['section']} (score {chunk['score']:.3f})\n{chunk['text']}"
        for index, chunk in enumerate(chunks, 1)
    )
    prompt = (
        "Answer the question using only the supplied filing excerpts. "
        "If evidence is insufficient, say: 'I could not find enough evidence in the selected "
        "filing to answer this reliably.' Never invent financial numbers. "
        "Cite excerpt numbers and sections for claims.\n\n"
        f"Question: {question}\n\nExcerpts:\n{evidence}\n\nAnswer:"
    )
    response = requests.post(
        f"{base_url.rstrip('/')}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False}, timeout=180,
    )
    response.raise_for_status()
    return response.json()["response"].strip()
