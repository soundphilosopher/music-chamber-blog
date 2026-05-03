"""
Add Bandcamp Player Hook for Music Chamber.

An MkDocs ``on_page_content`` hook that embeds a Bandcamp mini-player
beneath every release heading on *pinned* release-list pages.

For each ``<h2>`` heading the hook:

1. Derives a search query from the ``Artist - Title`` heading text.
2. Queries the Bandcamp fuzzy-search API for a matching album.
3. Injects an ``<iframe>`` embed player (wrapped in a
   ``<p class="bandcamp-player">``) into the description paragraph
   that follows the heading.

Only pages whose source path ends with ``releases.md`` **and** whose
front-matter contains ``bandcamp: true`` are processed — regular
weekly posts are left untouched.
"""

import logging
import time

from dataclasses import dataclass
from typing import Any
from random import uniform
from difflib import SequenceMatcher

from bs4 import BeautifulSoup, Tag
from curl_cffi.requests import Session
from curl_cffi.requests.exceptions import RequestException
from mkdocs.config import Config
from mkdocs.structure import files, pages


# No f-string needed — the logger name is a plain string literal.
log = logging.getLogger("mkdocs.hooks.add_bandcamp_player")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BANDCAMP_FUZZY_SEARCH_URL = "https://bandcamp.com/api/fuzzysearch/2/app_autocomplete"
"""Bandcamp autocomplete endpoint used to look up albums by name."""

BANDCAMP_ALBUM_LOOKUP_URL = "https://bandcamp.com/api/mobile/25/tralbum_details"
"""Bandcamp endpoint used to look up album details by ID."""

EMBED_PLAYER_BASE_URL = "https://bandcamp.com/EmbeddedPlayer"
"""Base URL for constructing Bandcamp ``<iframe>`` embed sources."""

REQUEST_DELAY_SECONDS: float = round(uniform(0.8, 1.5), 2)
"""Polite delay between consecutive API requests to avoid rate-limiting."""

MAX_RETRIES: int = 3
"""Maximum number of retry attempts when Bandcamp responds with HTTP 429."""

PLAYER_BG_COLOR_LIGHT = "ffffff"
"""Hex background color passed to the Bandcamp embed player for light mode."""

PLAYER_LINK_COLOR_LIGHT = "0687f5"
"""Hex link color passed to the Bandcamp embed player for light mode."""

PLAYER_BG_COLOR_DARK = "333333"
"""Hex background color passed to the Bandcamp embed player for dark mode."""

PLAYER_LINK_COLOR_DARK = "0f91ff"
"""Hex link color passed to the Bandcamp embed player for dark mode."""

# ---------------------------------------------------------------------------
# Matching tunables
# ---------------------------------------------------------------------------

_SUBSTR_MIN_LEN: int = 4
"""Minimum character length before substring matching is attempted.
Prevents single-syllable names like ``"da"`` from matching ``"dadada"``."""

_SUBSTR_MIN_RATIO: float = 0.65
"""Minimum ratio of shorter/longer string length for a substring match.
Ensures the substring covers a meaningful portion of the candidate
(e.g. ``"jinsookim"`` / ``"jinsookimjskm"`` ≈ 0.69 — passes;
``"da"`` / ``"dadada"`` ≈ 0.33 — rejected)."""


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass
class BandcampInfo:
    """Minimal metadata for a Bandcamp album returned by the fuzzy-search API.

    Attributes:
        album_id: Bandcamp-internal numeric album identifier.
        album_name: Human-readable album title.
        band_id: Bandcamp-internal numeric band/artist identifier.
        band_name: Human-readable artist / band name.
        album_url: Canonical URL of the album page on Bandcamp.
    """

    album_id: str
    album_name: str
    band_id: str
    band_name: str
    album_url: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Return *text* lowercased with every non-alphanumeric character removed."""
    return "".join(c.lower() for c in text if c.isalnum())


def _split_artist_string(raw: str) -> list[str]:
    """Split *raw* on common multi-artist separators and return normalised names.

    Deliberately does **not** split on ``"and"`` because that word appears
    inside many legitimate band names (e.g. *Of Monsters and Men*).
    The ``"and"`` connector case is handled by the combined-string check
    in :func:`_lookup_bandcamp_album`.
    """
    for sep in (" vs. ", " vs ", " feat. ", " feat ", " ft. ", " ft ", "&", "+", "/"):
        raw = raw.replace(sep, ",")
    return [_normalize(p) for p in raw.split(",") if p.strip()]


def _artist_match(query: str, candidate: str) -> bool:
    """Return ``True`` when *query* and *candidate* refer to the same artist.

    Three checks in order:

    1. Exact normalised equality.
    2. Substring — the shorter string must be at least :data:`_SUBSTR_MIN_LEN`
       characters long **and** cover at least :data:`_SUBSTR_MIN_RATIO` of the
       longer string's length.  This catches ``"Jin Soo Kim"`` inside
       ``"Jin Soo Kim (JSKM)"`` while rejecting ``"da"`` inside ``"dadada"``.
    3. :class:`~difflib.SequenceMatcher` similarity ≥ 0.85 for minor
       spelling variations.
    """
    if not query or not candidate:
        return False
    if query == candidate:
        return True
    shorter, longer = (
        (query, candidate) if len(query) <= len(candidate) else (candidate, query)
    )
    if (
        len(shorter) >= _SUBSTR_MIN_LEN
        and shorter in longer
        and len(shorter) / len(longer) >= _SUBSTR_MIN_RATIO
    ):
        return True
    return SequenceMatcher(None, query, candidate).ratio() >= 0.85


def _search_bandcamp(search_query: str, session: Session) -> list[Any]:
    """Query the Bandcamp fuzzy-search API for albums matching *search_query*.

    Filters raw results to only those whose ``type`` is ``"a"`` (album).
    Retries up to :data:`MAX_RETRIES` times when the API responds with
    HTTP 429, and honours the ``Retry-After`` response header when present.

    Args:
        search_query: The search string sent to the Bandcamp autocomplete API.
        session: A :class:`~curl_cffi.requests.Session` to reuse across calls.

    Returns:
        A (possibly empty) list of raw Bandcamp result dicts.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(
                BANDCAMP_FUZZY_SEARCH_URL,
                params={"q": search_query, "param_with_locations": "true"},
                impersonate="chrome",
            )
            log.debug("(SEARCH): response=%s", response)
        except RequestException:
            log.exception("(SEARCH): Bandcamp request failed for query %r", search_query)
            return []

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait = float(retry_after) + REQUEST_DELAY_SECONDS if retry_after else REQUEST_DELAY_SECONDS
            log.debug(
                "(SEARCH): Bandcamp rate limit hit for query %r (attempt %d/%d), retrying in %.1fs",
                search_query, attempt, MAX_RETRIES, wait,
            )
            time.sleep(wait)
            continue

        # Polite delay — only for non-429 paths so we don't double-sleep.
        time.sleep(REQUEST_DELAY_SECONDS)

        if response.status_code != 200:
            log.warning(
                "(SEARCH): Bandcamp returned HTTP %d for query %r with headers %s",
                response.status_code, search_query, response.headers,
            )
            return []

        return [
            r for r in response.json().get("results", [])
            if r.get("type") == "a"
        ]

    return []


def _lookup_bandcamp_album(artists: list[str], title: str, result: Any, session: Session) -> bool:
    """Verify that *result* is an album by one of *artists* via the Bandcamp mobile API.

    Matching runs through a **title check** and a **three-pass artist check**
    before the network sanity call is ever made.

    **Title check**
        The normalised query title must equal, substring-match (with length
        ratio guard), or be similar (≥ 0.85 via
        :class:`~difflib.SequenceMatcher`) to the album title extracted from
        the result's ``name`` field.

    **Artist check — Pass 1 (band_name, split + full)**
        ``band_name`` is split on common separators; the full unsplit
        normalised ``band_name`` is also included as a candidate.  Any one
        query artist matching any one candidate is sufficient.  The full form
        handles names where ``&`` is part of the name rather than a separator
        (e.g. *Prince Daddy & the Hyena*).

    **Artist check — Pass 2 (band_name, combined)**
        For multi-artist queries, all query artists must appear as substrings
        of the raw (un-split) ``band_name``.  Handles ``"and"`` connectors
        that are unsafe to split on globally.

    **Artist check — Pass 3 (label-release fallback)**
        Only entered when Passes 1 and 2 both fail (``band_name`` is likely a
        record-label name rather than the artist).  The ``name`` field must
        follow the ``"Artist - Album"`` format, the artist segment must differ
        from the title segment (prevents self-titled albums from creating a
        false loop), and **all** query artists must be matched from the
        name-prefix.  Accepting only a partial match here is what lets
        unrelated results slip through.

    Args:
        artists: List of artist names parsed from the heading.
        title: Album title parsed from the heading.
        result: A raw Bandcamp search result dict (from :func:`_search_bandcamp`).
        session: A :class:`~curl_cffi.requests.Session` to reuse across calls.

    Returns:
        ``True`` if the result matches and the album is accessible,
        ``False`` otherwise.
    """
    # ------------------------------------------------------------------ #
    # Normalise query side                                                 #
    # ------------------------------------------------------------------ #
    normalized_query_artists: list[str] = [_normalize(a) for a in artists]
    normalized_query_title: str = _normalize(title)

    # ------------------------------------------------------------------ #
    # Collect from result                                                  #
    # ------------------------------------------------------------------ #

    # Build result_artists from two sources so that & inside a band name
    # (e.g. "Prince Daddy & the Hyena") and & as a separator between
    # multiple artists (e.g. "Joseph Branciforte & Jozef Dumoulin") are
    # both handled:
    #   • split form  → individual artist names when & is a separator
    #   • full form   → whole normalised name when & is part of the name
    band_name_raw: str = result.get("band_name", "")
    result_artists: list[str] = _split_artist_string(band_name_raw)
    _full_band: str = _normalize(band_name_raw)
    if _full_band not in result_artists:
        result_artists = result_artists + [_full_band]

    # The name field is split here for both the title check and the
    # label-release fallback (Pass 3).
    result_name_raw: str = result.get("name", "")
    result_name_parts: list[str] = result_name_raw.split(" - ", 1)
    result_name_title: str = _normalize(result_name_parts[-1])

    # ------------------------------------------------------------------ #
    # Title check                                                          #
    # ------------------------------------------------------------------ #
    _shorter_t, _longer_t = (
        (normalized_query_title, result_name_title)
        if len(normalized_query_title) <= len(result_name_title)
        else (result_name_title, normalized_query_title)
    )
    _title_substr_ok: bool = (
        len(_shorter_t) >= _SUBSTR_MIN_LEN
        and _shorter_t in _longer_t
        and len(_shorter_t) / len(_longer_t) >= _SUBSTR_MIN_RATIO
    )
    title_matched: bool = (
        normalized_query_title == result_name_title
        or _title_substr_ok
        or SequenceMatcher(None, normalized_query_title, result_name_title).ratio() >= 0.95
    )

    if not title_matched:
        log.debug(
            "(LOOKUP): Title mismatch — query=%r, result_name=%r",
            normalized_query_title, result_name_title,
        )
        return False

    # ------------------------------------------------------------------ #
    # Artist check — three independent passes                              #
    # ------------------------------------------------------------------ #

    # Pass 1: split + full band_name — any one query artist suffices.
    band_name_match: bool = any(
        any(_artist_match(qa, ra) for ra in result_artists)
        for qa in normalized_query_artists
    )

    # Pass 2: raw combined band_name — for multi-artist releases whose
    # artists are joined by "and" or similar connectors that are unsafe to
    # split on globally (e.g. "Of Monsters and Men & Someone Else").
    # Requires ALL query artists to be substrings of the combined string.
    combined_band_match: bool = False
    if not band_name_match and len(normalized_query_artists) > 1:
        combined_band = _normalize(band_name_raw)
        combined_band_match = all(
            len(qa) >= _SUBSTR_MIN_LEN and qa in combined_band
            for qa in normalized_query_artists
        )

    # Pass 3: label-release fallback — artists extracted from the left
    # segment of a "Artist - Album" name field, used only when band_name
    # matched nothing (i.e. it is likely a record label).
    #
    # Two guards prevent the false positives that motivated removing this
    # pass earlier:
    #   • artist segment ≠ title segment  →  rejects self-titled albums
    #     like "Evil Warriors - Evil Warriors" where the name-prefix
    #     "evilwarriors" would otherwise match the query artist.
    #   • all()  →  a partial match (one of four artists) is not enough;
    #     only a full listing of all credited artists in the name field
    #     is accepted.
    label_release_match: bool = False
    if not band_name_match and not combined_band_match and len(result_name_parts) > 1:
        result_name_artists: list[str] = _split_artist_string(result_name_parts[0])
        name_prefix_normalized: str = _normalize(result_name_parts[0])

        artist_segment_differs_from_title: bool = name_prefix_normalized != result_name_title

        if artist_segment_differs_from_title and result_name_artists:
            label_release_match = all(
                any(_artist_match(qa, ra) for ra in result_name_artists)
                for qa in normalized_query_artists
            )

    artist_matched: bool = band_name_match or combined_band_match or label_release_match

    if not artist_matched:
        log.debug(
            "(LOOKUP): Artist mismatch — query_artists=%r, band_name=%r",
            normalized_query_artists, band_name_raw,
        )
        return False

    log.debug(
        "(LOOKUP): Candidate accepted — query=%r / %r, band=%r, name=%r",
        artists, title, band_name_raw, result_name_raw,
    )

    # ------------------------------------------------------------------ #
    # API sanity check — only reached when title and artist both match     #
    # ------------------------------------------------------------------ #
    params = {
        "band_id": result.get("band_id"),
        "tralbum_id": result.get("id"),
        "tralbum_type": "a",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(BANDCAMP_ALBUM_LOOKUP_URL, params=params)
        except RequestException:
            log.exception("(LOOKUP): Failed to lookup Bandcamp album %r", result.get("id"))
            return False

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait = float(retry_after) + REQUEST_DELAY_SECONDS if retry_after else REQUEST_DELAY_SECONDS
            log.debug(
                "(LOOKUP): Bandcamp rate limit hit for album %r (attempt %d/%d), retrying in %.1fs",
                result.get("id"), attempt, MAX_RETRIES, wait,
            )
            time.sleep(wait)
            continue

        if response.status_code != 200:
            log.warning(
                "(LOOKUP): Bandcamp returned HTTP %d for album %r with headers %s",
                response.status_code, result.get("id"), response.headers,
            )
            return False

        return len(response.json().get("tracks", [])) > 0

    # All retries exhausted due to rate-limiting.
    return False


def _collect_bandcamp_information(h2: Tag, session: Session) -> BandcampInfo | None:
    """Resolve a Bandcamp album for the release described by *h2*.

    Parses the heading text as ``"Artist[, Artist2] - Title"``, searches
    Bandcamp for the album title, and verifies each candidate result against
    the parsed artist list.

    Args:
        h2: The ``<h2>`` tag whose text contains the ``Artist - Title`` string.
        session: A :class:`~curl_cffi.requests.Session` to reuse across calls.

    Returns:
        A :class:`BandcampInfo` instance for the first matching album, or
        ``None`` if no match is found.
    """
    heading_text = h2.get_text(strip=True)
    artists, title = heading_text.split(" - ", 1)
    artists = [a.strip() for a in artists.split(",")]

    # Multi-artist releases are searched by title only because Bandcamp
    # may credit them under a combined name that differs from the heading.
    # Single-artist releases use the full "Artist - Title" heading so the
    # search is already targeted.
    search_query = title if len(artists) > 1 else heading_text
    results = _search_bandcamp(search_query=search_query, session=session)
    log.debug("Found %d results for %r", len(results), search_query)

    for result in results:
        if _lookup_bandcamp_album(artists=artists, title=title, result=result, session=session):
            log.debug(
                "(COLLECT): Matched %r for heading %r",
                result.get("name"), heading_text,
            )
            return BandcampInfo(
                album_id=result.get("id"),
                album_name=result.get("name"),
                band_id=result.get("band_id"),
                band_name=result.get("band_name"),
                album_url=result.get("url"),
            )

    log.debug("(COLLECT): Cannot find Bandcamp album for %r", heading_text)
    return None


def _build_player_embed(info: BandcampInfo, soup: BeautifulSoup) -> Tag:
    """Create the ``<p class="bandcamp-player">`` element for *info*.

    The returned structure looks like::

        <p class="bandcamp-player">
          <iframe class="bandcamp-player--light" ... seamless>
            <a href="...">Album Name by Band Name</a>
          </iframe>
          <iframe class="bandcamp-player--dark" ... seamless>
            <a href="...">Album Name by Band Name</a>
          </iframe>
        </p>

    Args:
        info: Album metadata used to populate the embed URL and
            fallback link.
        soup: The parent BeautifulSoup document (used to create new tags).

    Returns:
        A ``<p>`` :class:`Tag` ready to be appended into the DOM.
    """
    player_map = {
        "bandcamp-player--light": (
            f"{EMBED_PLAYER_BASE_URL}"
            f"/album={info.album_id}"
            f"/size=small"
            f"/bgcol={PLAYER_BG_COLOR_LIGHT}"
            f"/linkcol={PLAYER_LINK_COLOR_LIGHT}"
            f"/transparent=true/"
        ),
        "bandcamp-player--dark": (
            f"{EMBED_PLAYER_BASE_URL}"
            f"/album={info.album_id}"
            f"/size=small"
            f"/bgcol={PLAYER_BG_COLOR_DARK}"
            f"/linkcol={PLAYER_LINK_COLOR_DARK}"
            f"/transparent=true/"
        ),
    }

    p_tag = soup.new_tag("p", attrs={"class": "bandcamp-player"})

    for player_class, embed_src in player_map.items():
        iframe = soup.new_tag(
            "iframe",
            attrs={
                "class": player_class,
                "src": embed_src,
                "loading": "lazy",
                "seamless": "",
            }
        )
        fallback_link = soup.new_tag(
            "a",
            href=info.album_url,
            string=f"{info.album_name} by {info.band_name}",
        )
        iframe.append(fallback_link)
        p_tag.append(iframe)

    return p_tag


# ---------------------------------------------------------------------------
# MkDocs hook entry point
# ---------------------------------------------------------------------------


def on_page_content(html: str, page: pages.Page, config: Config, files: files.Files) -> str:
    """MkDocs hook: embed Bandcamp players on release-list pages.

    Skips pages that are not ``releases.md`` inside the ``posts/``
    directory tree, or whose front-matter does not set ``bandcamp: true``.

    For every ``<h2>`` on a qualifying page the hook queries Bandcamp,
    and — when a match is found — appends an embedded mini-player to the
    first ``<p>`` sibling (the release description).

    Args:
        html: The rendered HTML content of the page.
        page: The MkDocs Page object.
        config: The global MkDocs config dict.
        files: The MkDocs Files collection.

    Returns:
        The (potentially modified) HTML string.
    """
    src = page.file.src_path

    if not (src.endswith("releases.md") and src.startswith("posts")):
        return html

    if not page.meta.get("bandcamp", False):
        return html

    log.info("Embedding Bandcamp players for pinned page: %s", src)
    soup = BeautifulSoup(html, "html.parser")
    headings = soup.find_all("h2")

    if not headings:
        return html

    embedding_failed = 0
    embedding_total = len(headings)

    # Reuse a single session for all requests on this page to benefit
    # from HTTP keep-alive and reduced TLS handshake overhead.
    with Session() as session:
        for h2 in headings:
            bandcamp_info = _collect_bandcamp_information(h2, session)
            if bandcamp_info is None:
                embedding_failed += 1
                continue

            description = h2.find_next_sibling("p")
            if description is None:
                log.warning(
                    "No <p> sibling found for heading %r - skipping player",
                    h2.get_text(strip=True),
                )
                continue

            player = _build_player_embed(bandcamp_info, soup)
            description.append(player)

    print(f"\n\n  Bandcamp player embedded: {embedding_total - embedding_failed}/{embedding_total}\n\n")

    return str(soup)
