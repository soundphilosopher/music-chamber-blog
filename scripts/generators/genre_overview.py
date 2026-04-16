"""
Genre Overview Generator for Music Chamber.

This mkdocs-gen-files script scans all Markdown files under the docs
directory for ``::genre::`` tags, collects the tagged releases, and
generates a ``genres.md`` page listing every genre with links back to
the individual release reviews.

Genre tag syntax (placed as a paragraph after a release description)::

    ::genre:: Death Metal, Post Rock, Ambient

Multiple genres are comma-separated. Each tagged release is linked
via its ``<h2>`` heading anchor in the source file.

Generated file: ``genres.md``
"""

import markdown
import mkdocs_gen_files

from dataclasses import dataclass, field
from glob import glob
from pathlib import Path

from utils.genres import normalize_genre_names, GENRE_TAG_PREFIX, GENRE_TAG_PATTERN

from bs4 import BeautifulSoup


DOCS_ROOT = Path("docs")
DOCS_GLOB = "docs/**/*.md"


@dataclass
class ReleaseAnchor:
    """A link reference to a specific release heading in a source file."""

    title: str
    anchor_id: str
    file_path: str


@dataclass
class Genre:
    """A music genre with all its associated release anchors."""

    name: str
    releases: list[ReleaseAnchor] = field(default_factory=list)


def _parse_genre_tags(file_path: str) -> list[tuple[str, ReleaseAnchor]]:
    """Parse a Markdown file and extract genre-tagged releases.

    Looks for paragraphs matching the ``::genre::`` prefix, walks
    backwards in the DOM to find the associated ``<h2>`` release heading,
    and returns ``(genre_name, anchor)`` pairs.

    Args:
        file_path: Path to the Markdown file relative to the project
            root (e.g. ``docs/posts/2026/01/09/releases.md``).

    Returns:
        A list of ``(genre_name, ReleaseAnchor)`` tuples for every
        genre tag found in the file.
    """
    with open(file_path, "r") as f:
        md = markdown.Markdown(extensions=["meta", "toc"])
        html = md.convert(f.read())

    soup = BeautifulSoup(html, "html.parser")
    relative_path = str(Path(file_path).relative_to(DOCS_ROOT))
    results: list[tuple[str, ReleaseAnchor]] = []

    # exclude drafts from genre overview
    draft = getattr(md, "Meta", {}).get("draft", [])
    if "true" in draft:
        return results

    for genre_tag in soup.find_all(name="p"):
        if not GENRE_TAG_PATTERN.match(genre_tag.get_text()):
            continue

        description = genre_tag.find_previous_sibling("p")
        if not description:
            continue

        heading = description.find_previous_sibling("h2")
        if not heading:
            continue

        anchor = ReleaseAnchor(
            title=heading.get_text().rstrip(" *"),
            anchor_id=str(heading.get("id", "")),
            file_path=relative_path,
        )

        genre_text = genre_tag.get_text().removeprefix(GENRE_TAG_PREFIX).strip()
        genre_names = [name.strip().lower() for name in genre_text.split(",")]
        genre_names_normalized = normalize_genre_names(genre_names)


        for name in genre_names_normalized:
            if name:
                results.append((name, anchor))

    return results



def _collect_genres(glob_pattern: str) -> list[Genre]:
    """Scan all Markdown files and group releases by genre.

    Args:
        glob_pattern: Glob pattern for source files
            (e.g. ``docs/**/*.md``).

    Returns:
        An alphabetically sorted list of Genre objects, each containing
        all release anchors tagged with that genre.
    """
    genres_by_name: dict[str, Genre] = {}

    for path in sorted(glob(glob_pattern, recursive=True)):
        for genre_name, anchor in _parse_genre_tags(path):
            if genre_name not in genres_by_name:
                genres_by_name[genre_name] = Genre(name=genre_name)
            genres_by_name[genre_name].releases.append(anchor)

    return sorted(genres_by_name.values(), key=lambda g: g.name)


def _build_genres_markdown(genres: list[Genre]) -> str:
    """Build the Markdown content for the genre overview page.

    Args:
        genres: Alphabetically sorted list of Genre objects to render.

    Returns:
        The complete Markdown string for the genres page.
    """
    lines: list[str] = [
        "# Genres",
        "",
        '<div id="genre-filter"></div>',
        "",
    ]

    for genre in genres:
        lines.append(f"## {genre.name} ({len(genre.releases)})")
        lines.append("")

        genre.releases.sort(key=lambda r: r.title.lower())

        for release in genre.releases:
            lines.append(
                f"- [{release.title}]({release.file_path}#{release.anchor_id})"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def generate_genre_overview() -> None:
    """Main entry point: collect genre tags and write the overview page.

    Scans all Markdown files matching ``DOCS_GLOB``, groups tagged
    releases by genre, and writes the result to ``genres.md``.
    """
    genres = _collect_genres(DOCS_GLOB)
    content = _build_genres_markdown(genres)

    with mkdocs_gen_files.open("genres.md", "w") as f:
        f.write(content)


generate_genre_overview()
