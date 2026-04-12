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
from IPython.lib.deepreload import original_import

import logging
import time

from dataclasses import dataclass
from typing import Any
from random import uniform

from bs4 import BeautifulSoup, Tag
from curl_cffi.requests import Session
from curl_cffi.requests.exceptions import RequestException
from markdown.extensions.toc import slugify
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


def _search_bandcamp(search_query: str, session: Session) -> list[Any]:
    """Query the Bandcamp fuzzy-search API for albums matching *search_query*.

    Filters raw results to only those whose ``type`` is ``"a"`` (album)
    and whose ``name`` slug-matches *search_query* exactly.  Retries up to
    :data:`MAX_RETRIES` times when the API responds with HTTP 429, and
    honours the ``Retry-After`` response header when present.

    Args:
        search_query: The album title to look up (without artist prefix).
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

    First checks whether any of the provided artist names is contained in
    the result's ``band_name`` field (case-insensitive).  If so, performs a
    sanity-check request to :data:`BANDCAMP_ALBUM_LOOKUP_URL` to confirm
    the album is still accessible.  Retries up to :data:`MAX_RETRIES` times
    on HTTP 429 and aborts immediately if all retries are exhausted.

    Args:
        artists: List of artist names to match against the result's band name.
        result: A raw Bandcamp search result dict (from :func:`_search_bandcamp`).
        session: A :class:`~curl_cffi.requests.Session` to reuse across calls.

    Returns:
        ``True`` if the album belongs to one of *artists* and is accessible,
        ``False`` otherwise.
    """
    normalized_artists = ["" .join([char.lower() for char in artist if char.isalnum()]) for artist in artists]
    normalized_title = "".join([char.lower() for char in title if char.isalnum()])
    original_bag = [f"{artist} - {normalized_title}" for artist in normalized_artists]

    normalized_artists_from_result = ["" .join([char.strip().lower() for char in band_name if char.isalnum()]) for band_name in result.get("band_name", "").split(",")]
    normalized_title_from_result = ["".join([char.lower() for char in title_part if char.isalnum()]) for title_part in result.get("name", "").split(" - ", 1)]
    result_bag = [f"{artist} - {normalized_title_from_result[-1]}" for artist in normalized_artists_from_result]
    if len(normalized_title_from_result) > 1:
        result_bag.append(f"{normalized_title_from_result[0]} - {normalized_title_from_result[1]}")

    # check if any of the artists in the original bag are in the result bag
    for release in original_bag:
        if release not in result_bag:
            log.debug(f"Release {release} not found in result bag {result_bag}")
            continue

        log.debug(f"Found release {release} in result bag {result_bag}")

        params = {
            "band_id": result.get("band_id"),
            "tralbum_id": result.get("id"),
            "tralbum_type": "a",
        }

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = session.get(BANDCAMP_ALBUM_LOOKUP_URL, params=params)
            except RequestException:
                # log.exception() already attaches the full traceback.
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
                    "(LOOKUP): Bandcamp returned HTTP %d for query %r with headers %s",
                    response.status_code, normalized_title, response.headers,
                )
                return False

            return len(response.json().get("tracks", [])) > 0

        # All retries exhausted due to rate-limiting — abort early instead of
        # retrying the identical request for remaining artists in the list.
        return False

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

    search_query = title if ", " in heading_text else heading_text

    results = _search_bandcamp(search_query=search_query, session=session)
    log.info("Found %d results for %s", len(results), heading_text)

    if len(results) == 1:
        result = results[0]
        log.info("Found Bandcamp album %r for %s", result.get("name"), heading_text)
        return BandcampInfo(
            album_id=result.get("id"),
            album_name=result.get("name"),
            band_id=result.get("band_id"),
            band_name=result.get("band_name"),
            album_url=result.get("url"),
        )

    for result in results:
        if _lookup_bandcamp_album(artists=artists, title=title, result=result, session=session):
            log.info("Found Bandcamp album %r for %s after lookup", result.get("name"), heading_text)
            return BandcampInfo(
                album_id=result.get("id"),
                album_name=result.get("name"),
                band_id=result.get("band_id"),
                band_name=result.get("band_name"),
                album_url=result.get("url"),
            )

    # Use %-style formatting for consistency with the rest of the module.
    log.debug("Cannot find Bandcamp album for %r", heading_text)
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

    embedding_failed = 0;
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
