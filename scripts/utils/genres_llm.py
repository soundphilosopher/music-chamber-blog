"""
LLM-backed genre normalizer with a persistent JSON cache.

Collect all unique raw genre strings from your markdown files, pass them
to ``normalize_with_cache()``, and the results are stored in
``genre_cache.json`` next to this file so the LLM is only called for
genres it has never seen before.

Pick ONE backend below and uncomment it, then add the matching package
to pyproject.toml:
  - Ollama (local, free):  ollama
  - Claude API (cloud):    anthropic
"""

import json
import re
import ollama

from pathlib import Path
from utils.genres import _SPELLING_MAP

# ── Shared ──────────────────────────────────────────────────────────────────

CACHE_FILE = Path(__file__).parent / "genre_cache.json"


def _build_prompt(raw_genres: list[str]) -> str:
    known = "\n".join(f"  {k} → {v}" for k, v in _SPELLING_MAP.items())
    return (
        "You are a music genre expert. Normalize each genre tag in the input list.\n"
        "Rules:\n"
        "  - Use the known mappings table below as your reference — apply them to any matching word within a genre string\n"
        "  - When a known abbreviation appears as a word in a multi-word genre, expand it (e.g. 'alt folk' → 'Alternative Folk', 'psych rock' → 'Psychedelic Rock')\n"
        "  - Use Title Case for all other words\n"
        "  - Every key in the input list MUST appear in the output — do not skip any\n"
        "  - Respond with a single JSON object only. No markdown, no explanation.\n"
        "\n"
        "Known mappings:\n"
        f"{known}\n"
        "\n"
        f"Input: {json.dumps(raw_genres)}"
    )


def _extract_json(text: str) -> dict[str, str]:
    """Parse JSON from the model response, stripping any markdown code fences."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)


def _ask_llm(raw_genres: list[str]) -> dict[str, str]:
    response = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": _build_prompt(raw_genres)}],
        format="json",  # enforces structured JSON output — no fences needed
    )
    content = response.message.content or ""
    return json.loads(content)



# ── Cache layer ──────────────────────────────────────────────────────────────

def normalize_with_cache(raw_genres: list[str]) -> dict[str, str]:
    """Return a raw → normalized mapping, only calling the LLM for unseen genres.

    Args:
        raw_genres: Lowercased genre strings as they appear in the markdown
            files (e.g. ``["osdm", "death metal", "lofi hip hop"]``).

    Returns:
        A dict mapping every input to its canonical form.
        Any genre the LLM failed to return is kept as-is.
    """
    cache: dict[str, str] = {}
    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))

    unknown = [g for g in raw_genres if g not in cache]

    if unknown:
        llm_result = _ask_llm(unknown)

        # Fallback: keep any genre the model silently dropped
        for genre in unknown:
            cache[genre] = llm_result.get(genre, genre)

        CACHE_FILE.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return {g: cache[g] for g in raw_genres}
