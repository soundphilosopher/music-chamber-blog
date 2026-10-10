"""Shared loader for the statistics notebooks.

Parses the weekly ``releases.md`` posts into plain records (one per release)
so the notebooks only deal with pandas and plots. The star markers and genre
expansion follow ``scripts/export_recap_of_the_month.py``.
"""

import re
import sys

from pathlib import Path

# Make ``utils.genres`` importable (the same way the scripts import it).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from utils.genres import GENRE_TAG_PREFIX, normalize_genre_names  # noqa: E402

POSTS_PATH = ROOT / "docs" / "posts"
HEADING_PREFIX = "### "
SECTION_PREFIX = "## "

# Hidden non-breaking spaces occur in some headings; fold them into plain spaces.
_SPACES = re.compile(r"[\s ]+")


def _tier(heading: str) -> tuple[str, str]:
    """Split a heading into its name and pick tier (``top``, ``pick`` or ``none``)."""
    if heading.endswith(" **"):
        return heading.removesuffix(" **").rstrip(), "top"
    if heading.endswith(" *"):
        return heading.removesuffix(" *").rstrip(), "pick"
    return heading, "none"


def load_releases(month: str | None = None) -> list[dict]:
    """Load every release of one month (``YYYY-MM``) or of all posts.

    Returns:
        One dict per release with ``week`` (the post's Friday date), ``month``,
        ``section`` (``Friday`` or ``Earlier``), ``artist``, ``title``, ``name``,
        ``tier`` and ``genres`` (expanded names).
    """
    records: list[dict] = []
    for path in sorted(POSTS_PATH.glob("*/*/*/releases.md")):
        year, mon, day = path.parts[-4:-1]
        if month and f"{year}-{mon}" != month:
            continue

        section = ""
        current: dict | None = None
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith(SECTION_PREFIX):
                section = "Friday" if "Friday" in line else "Earlier"
            elif line.startswith(HEADING_PREFIX):
                name, tier = _tier(_SPACES.sub(" ", line.removeprefix(HEADING_PREFIX)).strip())
                artist, _, title = name.partition(" - ")
                current = {
                    "week": f"{year}-{mon}-{day}", "month": f"{year}-{mon}", "section": section,
                    "artist": artist, "title": title, "name": name, "tier": tier, "genres": [],
                }
                records.append(current)
            elif current is not None and line.startswith(GENRE_TAG_PREFIX):
                tags = [t.strip().lower() for t in line.removeprefix(GENRE_TAG_PREFIX).split(",") if t.strip()]
                current["genres"] = normalize_genre_names(tags)

    return records


_RECAP_ENTRY = re.compile(r"^\s*## (\d+)\. (.+?)\s*$", re.MULTILINE)


def name_key(name: str) -> str:
    """Comparable form of a ``Artist - Title`` name (case, spacing and star marks removed)."""
    return _SPACES.sub(" ", name).strip().removesuffix("*").strip().casefold()


def load_recaps() -> list[dict]:
    """Load the valid ``top-of-the-month.md`` recaps of every month.

    A recap is valid when it lists real ranked releases (``## 1. Artist - Title``).
    The scaffolded placeholder (``Lorem - Ipsum``, no ranks) is skipped.

    Returns:
        One dict per recap entry with ``month``, ``rank`` and ``name``.
    """
    records: list[dict] = []
    for path in sorted(POSTS_PATH.glob("*/*/top-of-the-month.md")):
        year, mon = path.parts[-3:-1]
        for rank, name in _RECAP_ENTRY.findall(path.read_text(encoding="utf-8")):
            if name.startswith("Lorem - Ipsum"):
                continue
            records.append({"month": f"{year}-{mon}", "rank": int(rank), "name": _SPACES.sub(" ", name)})

    return records


_LIFETIME_ENTRY = re.compile(r"^\s*## (?!\d+\. )(.+?)\s*$", re.MULTILINE)


def load_yearly_recaps() -> list[dict]:
    """Load the yearly ``top-25-recap-<YEAR>.md`` lists as ``year``/``rank``/``name`` records."""
    records: list[dict] = []
    for path in sorted(POSTS_PATH.glob("*/*/top-25-recap-*.md")):
        year = path.stem.removeprefix("top-25-recap-")
        for rank, name in _RECAP_ENTRY.findall(path.read_text(encoding="utf-8")):
            records.append({"year": year, "rank": int(rank), "name": _SPACES.sub(" ", name)})

    return records


def load_lifetime() -> list[dict]:
    """Load the unranked ``top-25-lifetime.md`` list as ``position``/``name`` records.

    The list is shown in file order, so ``position`` is just the order of appearance.
    """
    records: list[dict] = []
    for path in sorted(POSTS_PATH.glob("*/*/top-25-lifetime.md")):
        for position, name in enumerate(_LIFETIME_ENTRY.findall(path.read_text(encoding="utf-8")), start=1):
            records.append({"position": position, "name": _SPACES.sub(" ", name)})

    return records
