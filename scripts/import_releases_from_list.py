"""Import a list of music releases and generate a MkDocs blog post.

The script reads a raw text file containing one "Artist - Title" entry per
line, sorts the releases alphabetically by artist, and writes a Markdown blog
post (including MkDocs front matter) to the configured posts directory.

If a releases post already exists at the target path, any existing reviews
and genres are carried over into the newly generated post.

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


def _add_reviews_and_genres(path: Path, releases: list[Release]) -> list[Release]:
    """Enrich releases with existing reviews and genres from a Markdown file.

    If the file at the given path does not exist (e.g. on the first run),
    the releases are returned unchanged. Otherwise the file is parsed and
    each release whose artist and title match an existing heading has its
    review and genres updated in-place.

    The function expects each release to be structured in Markdown as:

        ## Artist - Title
        Review text
        ::genre::Genre1, Genre2

    Args:
        path: Path to an existing releases Markdown post to read from.
        releases: The list of Release objects to enrich.

    Returns:
        The same list of Release objects, with review and genres updated
        in-place where matches were found.
    """
    if not path.exists():
        log.debug(f"No existing releases file found at {path}, skipping enrichment.")
        return releases

    with open(path) as f:
        md = markdown.markdown(f.read())
        soup = BeautifulSoup(md, "html.parser")

        for h2 in soup.find_all("h2"):
            artist, title = h2.text.split(" - ")

            # Look for a release matching this heading; skip if not found.
            release = next(
                (r for r in releases if r.artist == artist and r.title == title),
                None,
            )
            if not release:
                continue

            # Use get_text() instead of .string so that inline markup
            # (e.g. bold or italic) inside the review paragraph is handled.
            review = h2.find_next_sibling("p")
            if not review:
                continue

            release.review = review.get_text()
            log.debug(f"review={release.review}")

            # The genre paragraph immediately follows the review paragraph
            # and starts with the GENRE_TAG_PREFIX.
            genres = review.find_next_sibling("p", string=GENRE_TAG_PATTERN)
            if not genres:
                continue

            release.genres = [
                g.strip()
                for g in genres.get_text().removeprefix(GENRE_TAG_PREFIX).split(",")
            ]
            log.debug(f"genres={release.genres}")

    return releases


def _build_release_list(path: Path) -> list[Release]:
    """Read and parse the raw releases file into a list of Release objects.

    Each non-empty line in the file must follow the format "Artist - Title".
    Leading and trailing whitespace around both the artist and title are
    stripped automatically. Review defaults to "tbd" and genres to an empty
    list; these are populated later by _add_reviews_and_genres() if available.

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
            artist, title = line.split(" - ")
            releases.append(
                Release(artist=artist.strip(), title=title.strip(), review="tbd", genres=[])
            )
    return releases


def _create_release_content(release_date: date, releases: list[Release]) -> str:
    """Build the Markdown content for the releases post, including front matter.

    The generated post includes MkDocs-compatible YAML front matter (date,
    draft status, and category) followed by a heading and one section per
    release. Each release section contains the review text and a genre tag
    line. A footer section for earlier-in-the-week entries is appended at
    the end.

    Args:
        release_date: The publication date used in the front matter.
        releases: The list of releases to include in the post.

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
        "# Releases! Releases! Releases!",
        "",
    ]

    for release in releases:
        content.append(f"## {release.artist} - {release.title}")
        content.append("")
        content.append(release.review)
        content.append("")
        # Use the GENRE_TAG_PREFIX constant to keep the tag format consistent.
        content.append(f"{GENRE_TAG_PREFIX}{', '.join(release.genres)}")
        content.append("")

    content.append("---")
    content.append("")
    content.append("# Earlier the week ...")
    content.append("")

    return "\n".join(content)


def main(release_date: date, path: Path) -> None:
    """Main entry point: build, sort, and write the releases Markdown post.

    Reads releases from the raw input file, sorts them case-insensitively by
    artist name, enriches them with any existing reviews and genres, generates
    the Markdown content, and writes the result to the appropriate path inside
    the MkDocs docs directory.

    The output path follows the pattern:
        docs/posts/<year>/<month>/<day>/releases.md

    Args:
        release_date: The publication date, used both in the front matter and
            to determine the output file path.
        path: Path to the raw releases text file.
    """
    releases = _build_release_list(path)

    if not releases:
        log.debug("No releases found, exiting.")
        return

    # Sort case-insensitively; casefold() handles Unicode better than lower()
    releases.sort(key=lambda r: r.artist.casefold())
    log.debug(f"releases={releases}")

    # Build the full output path, e.g. docs/posts/2026/03/06/releases.md
    release_list_path = (
        POSTS_PATH
        / str(release_date.year)
        / f"{release_date.month:02d}"
        / f"{release_date.day:02d}"
        / "releases.md"
    )
    log.debug(f"release_list_path={release_list_path}")

    # Carry over any reviews and genres already written in the existing file.
    releases = _add_reviews_and_genres(release_list_path, releases)
    log.debug(f"releases={releases}")

    content = _create_release_content(release_date, releases)
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
        "date",
        type=date.fromisoformat,
        help="Publication date in ISO 8601 format (e.g. 2026-03-06).",
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Path to the raw releases text file.",
    )
    args = parser.parse_args()
    log.debug(f"args={args}")

    main(args.date, args.path)
