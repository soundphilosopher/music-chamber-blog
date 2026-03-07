"""Import a list of music releases and generate a MkDocs blog post.

The script reads a raw text file containing one "Artist - Title" entry per
line, sorts the releases alphabetically by artist, and writes a Markdown blog
post (including MkDocs front matter) to the configured posts directory.

If a releases post already exists at the target path, any existing reviews
and genres are carried over into the newly generated post. New releases not
yet present in the existing file are always added to the Friday collection.

Usage:
    python import_releases.py <date> <path>

Args:
    date: Publication date for the post in ISO 8601 format (e.g. 2026-03-06).
    path: Path to the raw releases text file.

Example:
    python import_releases.py 2026-03-06 scripts/raw/releases.txt
"""

import argparse
import logging
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path

import markdown
from bs4 import BeautifulSoup

import mkdocs_gen_files

# Root path for MkDocs blog posts. All generated files are placed here.
POSTS_PATH = Path("docs/posts")

# Prefix used to identify and parse genre tags in the Markdown source.
GENRE_TAG_PREFIX = "::genre::"

# Compiled pattern to match lines that start with the genre tag prefix.
GENRE_TAG_PATTERN = re.compile(rf"^{re.escape(GENRE_TAG_PREFIX)}")


log = logging.getLogger("scripts.import_releases")


@dataclass
class Release:
    """Represents a single music release.

    Attributes:
        artist: The name of the artist or band.
        title: The title of the release.
        review: The review text for the release. Defaults to "tbd".
        genres: A list of genre strings associated with the release.
    """

    artist: str
    title: str
    review: str
    genres: list[str]


class ReleaseCollectionType(Enum):
    """Categorises a group of releases by when they were published."""

    FRIDAY = "Releases! Releases! Releases!"
    EARLIER = "Earlier the week ..."


@dataclass
class ReleaseCollection:
    """A named group of releases sharing the same publication category.

    Attributes:
        type: The category of the collection (Friday or earlier in the week).
        releases: The list of Release objects belonging to this collection.
    """

    type: ReleaseCollectionType
    releases: list[Release]


def _parse_existing_collections(path: Path) -> list[ReleaseCollection]:
    """Parse an existing releases Markdown file into a list of ReleaseCollections.

    Each top-level heading (H1) is mapped to a ReleaseCollectionType by its
    text value. H2 headings underneath are parsed as individual releases,
    carrying their review text and genre tags along.

    If the file does not exist, an empty list is returned.

    The function expects each release to be structured in Markdown as:

        # <ReleaseCollectionType value>

        ## Artist - Title
        Review text
        ::genre::Genre1, Genre2

    Args:
        path: Path to an existing releases Markdown post to read from.

    Returns:
        A list of ReleaseCollection objects found in the file, preserving
        their document order. Returns an empty list when the file does not
        exist.
    """
    if not path.exists():
        log.debug(f"No existing releases file found at {path}.")
        return []

    collections: list[ReleaseCollection] = []
    current_type: ReleaseCollectionType | None = None
    current_releases: list[Release] = []

    with open(path) as f:
        soup = BeautifulSoup(markdown.markdown(f.read()), "html.parser")

    for tag in soup.find_all(["h1", "h2"]):
        if tag.name == "h1":
            # Flush the previous collection before starting a new one.
            if current_type is not None:
                collections.append(
                    ReleaseCollection(type=current_type, releases=current_releases)
                )
            try:
                current_type = ReleaseCollectionType(tag.get_text())
            except ValueError:
                log.debug(f"Unknown collection heading: '{tag.get_text()}', skipping.")
                current_type = None
            current_releases = []

        elif tag.name == "h2" and current_type is not None:
            parts = tag.get_text().split(" - ", 1)
            if len(parts) != 2:
                log.debug(f"Skipping malformed release heading: '{tag.get_text()}'")
                continue

            artist, title = parts
            review = "tbd"
            genres: list[str] = []

            review_tag = tag.find_next_sibling("p")
            if review_tag:
                review = review_tag.get_text()
                log.debug(f"review={review}")

                genres_tag = review_tag.find_next_sibling("p", string=GENRE_TAG_PATTERN)
                if genres_tag:
                    genres = [
                        g.strip()
                        for g in genres_tag.get_text()
                        .removeprefix(GENRE_TAG_PREFIX)
                        .split(",")
                    ]
                    log.debug(f"genres={genres}")

            current_releases.append(
                Release(
                    artist=artist.strip(),
                    title=title.strip(),
                    review=review,
                    genres=genres,
                )
            )

    # Flush the last collection.
    if current_type is not None:
        collections.append(ReleaseCollection(type=current_type, releases=current_releases))

    log.debug(f"Parsed {len(collections)} existing collection(s) from {path}.")
    return collections


def _sort_to_collections(
    incoming: list[Release],
    existing: list[ReleaseCollection],
) -> list[ReleaseCollection]:
    """Distribute incoming releases across collections.

    Each incoming release is looked up in the existing collections by a
    case-insensitive artist + title comparison (trailing " *" markers on
    existing titles are ignored during comparison). A release that is already
    present is kept in its original collection and carries over its review and
    genres. A release that is not yet present is added to the FRIDAY
    collection.

    Releases that exist in the current Markdown but are absent from the
    incoming list are not carried forward — the incoming list is authoritative.

    Every collection is sorted alphabetically by artist after merging.

    Args:
        incoming: Releases read from the raw input file.
        existing: Collections parsed from the current releases Markdown file.
            Pass an empty list when no Markdown file exists yet.

    Returns:
        A list of ReleaseCollection objects in ReleaseCollectionType
        definition order (FRIDAY first, then EARLIER).
    """
    result: dict[ReleaseCollectionType, ReleaseCollection] = {
        ct: ReleaseCollection(type=ct, releases=[]) for ct in ReleaseCollectionType
    }

    if not existing:
        # No existing file — all incoming releases go straight to FRIDAY.
        result[ReleaseCollectionType.FRIDAY].releases = list(incoming)
        return list(result.values())

    # Build a flat lookup: normalised (artist, title) → (collection_type, Release).
    existing_lookup: dict[tuple[str, str], tuple[ReleaseCollectionType, Release]] = {}
    for collection in existing:
        for release in collection.releases:
            key = (
                release.artist.casefold(),
                # Strip trailing asterisk markers before comparing.
                release.title.casefold().rstrip("* "),
            )
            existing_lookup[key] = (collection.type, release)

    for incoming_release in incoming:
        key = (incoming_release.artist.casefold(), incoming_release.title.casefold())
        if key in existing_lookup:
            collection_type, existing_release = existing_lookup[key]
            result[collection_type].releases.append(existing_release)
            log.debug(
                f"Kept '{existing_release.artist} - {existing_release.title}'"
                f" in {collection_type.name}."
            )
        else:
            result[ReleaseCollectionType.FRIDAY].releases.append(incoming_release)
            log.debug(
                f"New release '{incoming_release.artist} - {incoming_release.title}'"
                f" added to FRIDAY."
            )

    for collection in result.values():
        collection.releases.sort(key=lambda r: r.artist.casefold())

    return list(result.values())


def _build_release_list(path: Path) -> list[Release]:
    """Read and parse the raw releases file into a list of Release objects.

    Each non-empty line in the file must follow the format "Artist - Title".
    Leading and trailing whitespace around both the artist and title are
    stripped automatically. Review defaults to "tbd" and genres to an empty
    list; these are populated later by _sort_to_collections() if available.

    Args:
        path: Path to the raw releases text file.

    Returns:
        A list of Release objects parsed from the given path.

    Raises:
        FileNotFoundError: If the given path does not exist.
        ValueError: If a line does not contain the expected " - " separator.
    """
    releases = []
    with open(path) as f:
        for line in f.read().strip().split("\n"):
            artist, title = line.split(" - ", 1)
            if any(
                r.artist.casefold() == artist.strip().casefold()
                and r.title.casefold() == title.strip().casefold()
                for r in releases
            ):
                continue

            releases.append(
                Release(artist=artist.strip(), title=title.strip(), review="tbd", genres=[])
            )

    releases.sort(key=lambda r: r.artist.casefold())
    return releases


def _create_release_content(
    release_date: date, collections: list[ReleaseCollection]
) -> str:
    """Build the Markdown content for the releases post, including front matter.

    The generated post includes MkDocs-compatible YAML front matter (date,
    draft status, and category) followed by a section per collection. Each
    section starts with an H1 heading matching the collection's type value,
    followed by one H2 block per release. A horizontal rule separates
    consecutive collection sections. The ``<!-- more -->`` excerpt marker is
    inserted after the third release of the FRIDAY collection.

    Args:
        release_date: The publication date used in the front matter.
        collections: The list of ReleaseCollection objects to render.

    Returns:
        A string containing the full Markdown content of the post.
    """
    content = [
        "---",
        f"date: {release_date.isoformat()}",
        "pin: true",
        "bandcamp: false",
        "draft: true",
        "categories:",
        "  - Releases",
        "---",
        "",
    ]

    for col_index, collection in enumerate(collections):
        if col_index > 0:
            content.append("---")
            content.append("")

        content.append(f"# {collection.type.value}")
        content.append("")

        for rel_index, release in enumerate(collection.releases):
            if collection.type == ReleaseCollectionType.FRIDAY and rel_index == 3:
                content.append("<!-- more -->")
                content.append("")

            content.append(f"## {release.artist} - {release.title}")
            content.append("")
            content.append(release.review)
            content.append("")
            # Use the GENRE_TAG_PREFIX constant to keep the tag format consistent.
            content.append(f"{GENRE_TAG_PREFIX}{', '.join(release.genres)}")
            content.append("")

    return "\n".join(content)


def main(release_date: date, path: Path) -> None:
    """Main entry point: build, sort, and write the releases Markdown post.

    Reads releases from the raw input file, collects any existing collections
    from the current releases Markdown, merges them, and writes the result to
    the appropriate path inside the MkDocs docs directory.

    The output path follows the pattern:
        docs/posts/<year>/<month>/<day>/releases.md

    Args:
        release_date: The publication date, used both in the front matter and
            to determine the output file path.
        path: Path to the raw releases text file.
    """
    # 1. Collect all releases from the txt file.
    incoming_releases = _build_release_list(path)
    log.debug(f"incoming_releases={incoming_releases}")

    if not incoming_releases:
        log.info("No releases found, exiting.")
        return

    # Build the full output path, e.g. docs/posts/2026/03/06/releases.md
    release_list_path = (
        POSTS_PATH
        / str(release_date.year)
        / f"{release_date.month:02d}"
        / f"{release_date.day:02d}"
        / "releases.md"
    )
    log.debug(f"release_list_path={release_list_path}")

    # 2. Collect all releases from the current release markdown (if it exists).
    existing_collections = _parse_existing_collections(release_list_path)
    log.debug(f"existing_collections={existing_collections}")

    # 3. Sort releases into collections.
    collections = _sort_to_collections(incoming_releases, existing_collections)
    log.debug(f"collections={collections}")

    # 4. Use the collections to create the release markdown.
    content = _create_release_content(release_date, collections)
    log.debug(f"content={content}")

    # MkDocs expects paths relative to the docs/ root (i.e. POSTS_PATH.parts[0])
    mkdocs_file_path = release_list_path.relative_to(POSTS_PATH.parts[0])
    log.debug(f"mkdocs_file_path={mkdocs_file_path}")

    with mkdocs_gen_files.open(mkdocs_file_path, "w") as f:
        f.write(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a MkDocs releases post from a raw text file."
    )
    parser.add_argument(
        "--date",
        "-d",
        type=date.fromisoformat,
        help="Publication date in ISO 8601 format (e.g. 2026-03-06).",
        required=True,
    )
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        help="Path to the raw releases text file.",
        required=True,
    )
    args = parser.parse_args()
    log.debug(f"args={args}")

    main(args.date, args.file)
