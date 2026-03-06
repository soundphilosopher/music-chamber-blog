"""Import images from a title/URL list file and write a MkDocs Markdown cache.

Reads a plain-text file where every non-empty line contains an image title and
a remote URL separated by " | ", downloads each image via ``curl_cffi``
(impersonating a real Chrome browser to bypass CDN fraud rules / rate-limit
fingerprinting), and appends the resulting Markdown entries to a cache file
consumed by MkDocs.

The script is resilient to transient network failures and CDN rate-limits: each
download is retried up to ``--retries`` times with exponential back-off, and a
configurable ``--delay`` is inserted between consecutive requests.

List file format (one entry per line)::

    Album cover  | https://cdn.example.com/cover.jpg
    Artist photo | https://cdn.example.com/photo.webp

Usage::

    python scripts/import_images_from_list.py path/to/list.txt
    python scripts/import_images_from_list.py path/to/list.txt --delay 2 --retries 5
"""

import argparse
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from curl_cffi import requests as curl_requests
from markdown.extensions.toc import slugify

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Directory where downloaded image files are saved.
IMAGES_BASE_PATH = Path("docs/assets/images")

# Markdown cache file that is appended to after each successful run.
CACHE_PATH = Path(".cache/images.md")

# Default seconds to wait between consecutive HTTP requests.
DEFAULT_DELAY: float = 1.0

# Default maximum number of download attempts per image.
DEFAULT_RETRIES: int = 3

# Multiplier applied to the wait time after each failed attempt.
BACKOFF_FACTOR: float = 2.0

# HTTP status codes that are worth retrying (rate-limit / transient server errors).
RETRYABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})

log = logging.getLogger("scripts.import_images")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Image:
    """A single image entry parsed from the input list file.

    Attributes:
        title: Human-readable label used as the Markdown alt-text and heading.
        url:   Remote URL from which the image is downloaded.
        path:  Local filesystem path where the downloaded file is saved.
               ``None`` until the download succeeds.
    """

    title: str
    url: str
    path: Path | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_directories() -> None:
    """Create required output directories if they do not already exist."""
    IMAGES_BASE_PATH.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _parse_extension(content_type: str) -> str:
    """Derive a file extension from a raw ``Content-Type`` header value.

    Strips optional parameters such as ``; charset=utf-8`` before extracting
    the MIME sub-type so that ``image/jpeg; charset=utf-8`` correctly returns
    ``"jpeg"`` rather than ``"jpeg; charset=utf-8"``.

    Args:
        content_type: The raw ``Content-Type`` header string.

    Returns:
        The file extension derived from the MIME sub-type (e.g. ``"jpeg"``).
        Falls back to ``"bin"`` when the header is absent or unrecognisable.
    """
    mime = content_type.split(";")[0].strip()   # drop params like charset
    parts = mime.split("/")
    if len(parts) == 2 and parts[1]:
        return parts[1]
    return "bin"


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def _build_images(path: Path) -> list[Image]:
    """Parse the input list file into a list of :class:`Image` objects.

    Each non-empty line must follow the format::

        Title | https://example.com/image.jpg

    Lines that do not conform to this format are skipped with a warning rather
    than crashing the whole run. ``maxsplit=1`` ensures that a URL which
    itself contains `` | `` is never mistakenly split.

    Args:
        path: Filesystem path to the list file.

    Returns:
        A list of :class:`Image` instances ready for downloading.
    """
    images: list[Image] = []
    with open(path, "r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            parts = line.split(" | ", maxsplit=1)
            if len(parts) != 2:
                log.warning("Skipping malformed line %d: %r", lineno, line)
                continue
            title, url = parts
            images.append(Image(title=title.strip(), url=url.strip()))
    return images


def _download_image(
    session: curl_requests.Session,
    image: Image,
    *,
    retries: int = DEFAULT_RETRIES,
    delay: float = DEFAULT_DELAY,
) -> Image:
    """Download a single image and save it to :data:`IMAGES_BASE_PATH`.

    Uses exponential back-off when the server signals rate-limiting (HTTP 429)
    or returns a transient server error (5xx). Network-level failures (e.g.
    DNS errors, connection timeouts) are also retried.

    A Unix timestamp is appended to the filename to avoid collisions when the
    same list is processed more than once.

    Args:
        session: A ``curl_cffi`` session with Chrome impersonation already set.
        image:   The :class:`Image` instance containing the title and source URL.
        retries: Maximum number of download attempts before giving up.
        delay:   Base delay in seconds between attempts (doubles on each retry).

    Returns:
        The same *image* instance. ``image.path`` is populated on success and
        remains ``None`` on failure.
    """
    timestamp = int(time.time())
    backoff = delay

    for attempt in range(1, retries + 1):
        try:
            log.debug("Downloading %s (attempt %d/%d)", image.url, attempt, retries)
            response = session.get(image.url)
            response.raise_for_status()
        except Exception as exc:
            status: int | None = getattr(getattr(exc, "response", None), "status_code", None)
            if attempt < retries and (status is None or status in RETRYABLE_STATUSES):
                log.warning(
                    "Attempt %d/%d failed for '%s' (%s). Retrying in %.1fs…",
                    attempt, retries, image.title, exc, backoff,
                )
                time.sleep(backoff)
                backoff *= BACKOFF_FACTOR
                continue
            log.error("Failed to download image for '%s': %s", image.title, exc)
            return image

        extension = _parse_extension(response.headers.get("Content-Type", ""))
        image_name = f"{slugify(image.title, '_')}-{timestamp}.{extension}"
        image.path = IMAGES_BASE_PATH / image_name

        with open(image.path, "wb") as f:
            f.write(response.content)

        log.info("Saved '%s' → %s", image.title, image.path)
        return image

    return image  # all retries exhausted


def _write_images_to_cache(images: list[Image]) -> None:
    """Append successfully downloaded images to the Markdown cache file.

    Each image produces a Markdown image tag, a level-2 heading, and a
    horizontal rule, matching the expected MkDocs page layout. Entries whose
    download failed (``image.path is None``) are silently skipped.

    Args:
        images: The list of :class:`Image` objects returned by the pipeline.
    """
    written = 0
    with open(CACHE_PATH, "a", encoding="utf-8") as cache:
        for image in images:
            if image.path is None:
                continue
            cache.write(
                f"![{image.title}](site:assets/images/{image.path.name}){{ .top-list-image }}\n\n"
            )
            cache.write(f"## {image.title}\n\n")
            cache.write("---\n\n")
            written += 1

    log.info("Wrote %d/%d image entries to %s.", written, len(images), CACHE_PATH)


def main(path: Path, *, delay: float = DEFAULT_DELAY, retries: int = DEFAULT_RETRIES) -> None:
    """Orchestrate the full image import pipeline.

    1. Ensures :data:`IMAGES_BASE_PATH` and the parent of :data:`CACHE_PATH` exist.
    2. Parses the input list file into :class:`Image` objects.
    3. Downloads each image through a shared ``curl_cffi`` Chrome session,
       inserting a *delay* between requests to respect CDN rate limits.
    4. Appends successful entries to the Markdown cache.

    Args:
        path:    Path to the input list file.
        delay:   Seconds to wait between consecutive HTTP requests.
        retries: Maximum download attempts per image.
    """
    _ensure_directories()

    images = _build_images(path)
    log.info("Found %d image(s) to process.", len(images))

    with curl_requests.Session(impersonate="chrome") as session:
        for idx, image in enumerate(images):
            images[idx] = _download_image(session, image, retries=retries, delay=delay)
            # Pause between requests — skip the delay after the very last one.
            if idx < len(images) - 1:
                time.sleep(delay)

    _write_images_to_cache(images)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(
        description=(
            "Download images from a title|URL list and write MkDocs Markdown cache entries."
        ),
    )
    parser.add_argument(
        "list_file",
        type=Path,
        help="Path to the list file. Each line must be: Title | https://url.to/image",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        metavar="SECONDS",
        help=(
            f"Seconds to wait between requests (default: {DEFAULT_DELAY}). "
            "Increase this value when hitting CDN rate limits."
        ),
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        metavar="N",
        help=f"Maximum download attempts per image (default: {DEFAULT_RETRIES}).",
    )
    args = parser.parse_args()

    main(args.list_file, delay=args.delay, retries=args.retries)
