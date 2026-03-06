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
front-matter contains ``pin: true`` are processed — regular (non-pinned)
weekly posts are left untouched.
"""

from __future__ import annotations

import logging
from threading import Lock
import time

from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag
from curl_cffi.requests import Session
from curl_cffi.requests.exceptions import RequestException
from markdown.extensions.toc import slugify
from mkdocs.config import Config
from mkdocs.structure import files, pages

log = logging.getLogger(f"mkdocs.hooks.add_bandcamp_player")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BANDCAMP_FUZZY_SEARCH_URL = "https://bandcamp.com/api/fuzzysearch/2/app_autocomplete"
"""Bandcamp autocomplete endpoint used to look up albums by name."""

BANDCAMP_ALBUM_LOOKUP_URL = "https://bandcamp.com/api/mobile/25/tralbum_details"
"""Bandcamp endpoint used to look up album details by ID."""

EMBED_PLAYER_BASE_URL = "https://bandcamp.com/EmbeddedPlayer"
"""Base URL for constructing Bandcamp ``<iframe>`` embed sources."""

REQUEST_DELAY_SECONDS: float = 0.5
"""Polite delay between consecutive API requests to avoid rate-limiting."""

PLAYER_BG_COLOR_LIGHT = "ffffff"
"""Hex background color passed to the Bandcamp embed player for light mode."""

PLAYER_LINK_COLOR_LIGHT = "0687f5"
"""Hex link color passed to the Bandcamp embed player for light mode."""

PLAYER_BG_COLOR_DARK = "333333"
"""Hex background color passed to the Bandcamp embed player for light mode."""

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


def _normalize_release_name(original_name: str) -> str | None:
    """Turn an ``Artist(s) - Title`` heading into a search-friendly query.

    Multi-artist headings (comma-separated) are reduced to the **first**
    listed artist so the Bandcamp search has a better chance of returning
    a single, relevant result.

    Args:
        original_name: The raw heading text, expected in
            ``Artist - Album Title`` format.

    Returns:
        A slugified, lower-case search string, or ``None`` if the heading
        does not contain the expected ``" - "`` separator.
    """
    parts = original_name.split(" - ", maxsplit=1)
    if len(parts) != 2:
        log.warning("Heading does not match 'Artist - Title' pattern: %r", original_name)
        return None

    artists, title = parts
    artist = artists.split(",")[0].strip()
    return slugify(f"{artist} {title}", " ")


def _lookup_bandcamp_album(album_id: str, band_id: str, session: Session) -> bool:
    """Query Bandcamp for album details by ID.

    Args:
        album_id: The Bandcamp-internal numeric album identifier.
        session: A reusable :class:`curl_cffi.requests.Session` (keeps
            the underlying connection alive across calls).

    Returns:
        ``True`` if the album exists and has tracks, ``False`` otherwise.
    """
    params = {"band_id": band_id, "tralbum_id": album_id, "tralbum_type": "a"}

    try:
        response = session.get(BANDCAMP_ALBUM_LOOKUP_URL, params=params)
    except Exception as e:
        log.exception("Failed to lookup Bandcamp album %r: %r", album_id, e)
        return False

    if response.status_code != 200:
        return False

    return len(response.json().get("tracks", [])) > 0


def _collect_bandcamp_information(
    h2: Tag, session: Session
) -> BandcampInfo | None:
    """Query Bandcamp for album metadata that matches *h2*.

    Sends a single fuzzy-search request and returns the **first** result
    whose type is ``"a"`` (album).  A short delay is applied after each
    request to be respectful of the Bandcamp API.

    Args:
        h2: A BeautifulSoup ``<h2>`` tag whose text content is an
            ``Artist - Title`` string.
        session: A reusable :class:`curl_cffi.requests.Session` (keeps
            the underlying connection alive across calls).

    Returns:
        A :class:`BandcampInfo` instance for the first matching album,
        or ``None`` if the search yields no album results, the heading
        text cannot be parsed, or the request fails.
    """
    heading_text = h2.get_text(strip=True)
    search_query = _normalize_release_name(heading_text)
    if search_query is None:
        return None

    try:
        response = session.get(
            BANDCAMP_FUZZY_SEARCH_URL,
            params={"q": search_query, "param_with_locations": "true"},
            impersonate="chrome",
        )
        log.debug(f"response={response}")
    except RequestException:
        log.exception("Bandcamp request failed for query %r", search_query)
        return None
    finally:
        # Always pause — even on failure — to stay within rate limits.
        time.sleep(REQUEST_DELAY_SECONDS)

    if response.status_code != 200:
        log.warning(
            "Bandcamp returned HTTP %d for query %r",
            response.status_code,
            search_query,
        )
        return None

    for result in response.json().get("results", []):
        if result.get("type") == "a":
            if not _lookup_bandcamp_album(result.get("id"), result.get("band_id"), session):
                log.debug("Bandcamp album %r has no tracks, skipping", result.get("id"))
                continue

            info = BandcampInfo(
                album_id=result.get("id"),
                album_name=result.get("name"),
                band_id=result.get("band_id"),
                band_name=result.get("band_name"),
                album_url=result.get("url"),
            )
            log.debug("Matched %r -> %s", search_query, info.album_url)
            return info

    log.debug("No Bandcamp album found for query %r", search_query)
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
    """MkDocs hook: embed Bandcamp players on pinned release-list pages.

    Skips pages that are not ``releases.md`` inside the ``posts/``
    directory tree, or whose front-matter does not set ``pin: true``.

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

    # Reuse a single session for all requests on this page to benefit
    # from HTTP keep-alive and reduced TLS handshake overhead.
    with Session() as session:
        for h2 in headings:
            bandcamp_info = _collect_bandcamp_information(h2, session)
            if bandcamp_info is None:
                continue

            description = h2.find_next_sibling("p")
            if description is None:
                log.debug(
                    "No <p> sibling found for heading %r - skipping player",
                    h2.get_text(strip=True),
                )
                continue

            player = _build_player_embed(bandcamp_info, soup)
            description.append(player)

    return str(soup)
