"""
llm.py - Talks to the Large Language Model (the "brain" of the agent).

Supports two FREE providers (choose with the LLM_PROVIDER environment variable):
  - "gemini" (default): Google Gemini. Get a key at https://aistudio.google.com/apikey
  - "groq":             Groq.          Get a key at https://console.groq.com/keys

The API key is ALWAYS read from an environment variable (or Streamlit secrets).
It is never written in the code.

We call the providers with plain HTTP (the `requests` library), so there is no
extra SDK to install.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

import requests

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "groq": "openai/gpt-oss-120b",
}

REQUEST_TIMEOUT = 60  # seconds to wait for the LLM

# ---------------------------------------------------------------------------
# Prompt design  (CHANGE THIS to make the project your own - see README)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a careful Python debugging assistant inside a self-healing loop.
You receive a Python script and the error it produced when it was run.
Your job: return a FIXED version of the whole script.

Rules:
1. Make the SMALLEST change that fixes the error. Keep the original logic, names and style.
2. Keep every print statement, so the output stays the same.
3. If the error is an infinite loop / timeout, find the loop that never ends and fix its condition.
4. If an `assert` fails, the program's logic is wrong: fix the logic, NEVER delete or weaken the assert.
5. If a module is missing and it is a typo of a standard module (e.g. `maths` -> `math`), fix the typo.
   If it is a real third-party package, say so in the explanation (the user must `pip install` it).
6. Never add dangerous code: no os.system, subprocess, file deletion, network access, eval or exec.
7. The script must run without user input (no input()).

Reply in EXACTLY this format and nothing else:
EXPLANATION: <one or two short sentences saying what was wrong and what you changed>
```python
<the complete fixed script>
```"""


def build_user_prompt(code: str, error: str, history: list[str] | None = None) -> str:
    """Build the message we send to the LLM for one fix attempt."""
    parts = [
        "Here is the script:",
        f"```python\n{code}\n```",
        "When I ran it, it failed with:",
        f"```\n{error.strip()[:4000]}\n```",
    ]
    if history:
        # Telling the model what it already tried helps stop it repeating itself.
        parts.append("Fixes already tried in earlier attempts (do not repeat a fix that failed):")
        parts.extend(f"- {h}" for h in history[-4:])
    parts.append("Return the fixed script in the required format.")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Parsing the LLM's answer
# ---------------------------------------------------------------------------

_CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


@dataclass
class Fix:
    code: str
    explanation: str


class LLMError(Exception):
    """Raised when the LLM call fails (no key, network problem, bad reply)."""


def parse_response(text: str) -> Fix:
    """Pull the explanation and the code block out of the LLM's reply."""
    blocks = _CODE_BLOCK.findall(text or "")
    if not blocks:
        raise LLMError("The AI did not return a code block. Raw reply:\n" + (text or "")[:500])
    code = max(blocks, key=len).strip("\n") + "\n"   # longest block = the script

    m = re.search(r"EXPLANATION:\s*(.+?)(?:```|$)", text, re.DOTALL | re.IGNORECASE)
    explanation = m.group(1).strip() if m else text.split("```")[0].strip()
    return Fix(code=code, explanation=explanation or "(no explanation given)")


# ---------------------------------------------------------------------------
# Provider calls
# ---------------------------------------------------------------------------

def get_provider() -> str:
    return os.getenv("LLM_PROVIDER", "gemini").strip().lower()


def get_model(provider: str) -> str:
    return os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODELS.get(provider, "")


def get_api_key(provider: str) -> str | None:
    env_name = {"gemini": "GEMINI_API_KEY", "groq": "GROQ_API_KEY"}.get(provider)
    return os.getenv(env_name) if env_name else None


def is_configured() -> bool:
    return bool(get_api_key(get_provider()))


def _call_gemini(system: str, user: str, model: str, key: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"temperature": 0.2},
    }
    r = requests.post(url, params={"key": key}, json=body, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise LLMError(f"Gemini error {r.status_code}: {r.text[:300]}")
    try:
        parts = r.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Unexpected Gemini reply: {r.text[:300]}") from exc


def _call_groq(system: str, user: str, model: str, key: str) -> str:
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code != 200:
        raise LLMError(f"Groq error {r.status_code}: {r.text[:300]}")
    try:
        return r.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"Unexpected Groq reply: {r.text[:300]}") from exc


def ask_llm_for_fix(code: str, error: str, history: list[str] | None = None) -> Fix:
    """The one function the agent uses: give code + error, get back a Fix."""
    provider = get_provider()
    key = get_api_key(provider)
    if not key:
        raise LLMError(
            f"No API key found for provider '{provider}'. "
            "Set GEMINI_API_KEY (or GROQ_API_KEY with LLM_PROVIDER=groq)."
        )
    model = get_model(provider)
    user = build_user_prompt(code, error, history)
    try:
        if provider == "gemini":
            text = _call_gemini(SYSTEM_PROMPT, user, model, key)
        elif provider == "groq":
            text = _call_groq(SYSTEM_PROMPT, user, model, key)
        else:
            raise LLMError(f"Unknown LLM_PROVIDER '{provider}'. Use 'gemini' or 'groq'.")
    except requests.RequestException as exc:
        raise LLMError(f"Could not reach the AI service: {exc}") from exc
    return parse_response(text)
