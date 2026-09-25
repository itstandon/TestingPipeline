import os
import random
import time
import requests

# The full list of models the pipeline generates test cases with
# (generate_testcases.py, run_metrics.py, etc. all iterate over this).
# Mix and match local Ollama models and Groq-hosted models freely --
# routing is decided by OLLAMA_MODELS below, not by this list.
MODELS = [
    "qwen2.5:3b",
    #"llama3.2:3b",
    "gemma3:4b",
    "openai/gpt-oss-120b",
]

# Which of the models above are LOCAL Ollama models. Anything in
# MODELS that is NOT in this set is routed to Groq instead (same
# backend the SOTA evaluator, LLM2_MODEL, already uses).
OLLAMA_MODELS = {
    "qwen2.5:3b",
    "gemma3:4b",
}

# The "SOTA" evaluator model used for compare_with_expert / any future
# LLM2-based judging, plus its API key.
# Configure via a .env file or exported shell variables:
#   LLM2_MODEL=openai/gpt-oss-120b
#   LLM2_API_KEY=gsk_...   (your Groq API key)
LLM2_MODEL = os.environ.get("LLM2_MODEL")
LLM2_API_KEY = os.environ.get("LLM2_API_KEY")

OPENAI_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

# Retry/backoff for Groq calls -- centralized here so EVERY caller
# (generate_testcases.py, run_metrics.py, compare_with_expert.py, ...)
# gets it automatically instead of each script needing its own copy.
# A single 429 used to immediately fall back to a mock response with
# no retry; now it backs off and retries first, same pattern
# compare_with_expert.py already used for its own evaluator calls.
GROQ_MAX_RETRIES = int(os.environ.get("GROQ_MAX_RETRIES", "5"))
GROQ_BACKOFF_BASE_SECONDS = float(os.environ.get("GROQ_BACKOFF_BASE_SECONDS", "5"))


def call_llm(prompt, model, timeout=1800):
    """
    Routes to the right backend based on `model`:
      - If `model` is in OLLAMA_MODELS, call the local Ollama server.
      - Otherwise (e.g. "openai/gpt-oss-120b", or LLM2_MODEL), call Groq,
        with retry/backoff on rate limits.
    Falls back to a mock response only after genuinely exhausting
    retries (or on non-retryable errors), so the pipeline can still be
    exercised end-to-end without live services during development/testing.
    """
    if model in OLLAMA_MODELS:
        return _call_ollama(prompt, model, timeout)
    return _call_openai(prompt, model, timeout)


def _call_openai(prompt, model, timeout=1800,
                  max_retries=GROQ_MAX_RETRIES,
                  backoff_base=GROQ_BACKOFF_BASE_SECONDS):
    if not LLM2_API_KEY or LLM2_API_KEY == "your_sota_api_key_here":
        print(f"  [Groq call skipped: LLM2_API_KEY is not set]. Using high-quality mock response for {model}.")
        return get_mock_response(prompt, model)

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                OPENAI_CHAT_URL,
                headers={
                    "Authorization": f"Bearer {LLM2_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=timeout,
            )

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_s = float(retry_after) if retry_after else backoff_base * (2 ** (attempt - 1))
                wait_s += random.uniform(0, 1)  # jitter, avoid thundering herd
                print(f"  [Rate limited] 429 from Groq for {model} (attempt {attempt}/{max_retries}); "
                      f"waiting {wait_s:.1f}s before retrying...")
                time.sleep(wait_s)
                last_error = "429 Too Many Requests"
                continue

            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

        except requests.exceptions.RequestException as e:
            last_error = str(e)
            wait_s = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 1)
            print(f"  [Groq call failed] attempt {attempt}/{max_retries} for {model}: {e}; "
                  f"waiting {wait_s:.1f}s before retrying...")
            time.sleep(wait_s)

    print(f"  All {max_retries} attempts to reach Groq failed for {model} ({last_error}). "
          f"Using high-quality mock response.")
    return get_mock_response(prompt, model)


def _call_ollama(prompt, model, timeout=1800):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_ctx": 8192,
                    "num_predict": 2048,
                }
            },
            timeout=timeout
        )
        response.raise_for_status()
        return response.json()["response"]
    except Exception as e:
        print(f"  [Ollama call failed: {e}]. Using high-quality mock response for {model}.")
        return get_mock_response(prompt, model)


def get_mock_response(prompt, model):
    return f"""<think>
Reasoning Process:
1. Fallback matched. Returning standard response.
</think>
### Subject Model ({model}) Response - Fallback
I am ready to proceed. Please provide the requirement and evaluation metrics."""