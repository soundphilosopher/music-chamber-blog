"""
Monthly Recap Generator for Music Chamber.

This mkdocs-gen-files script scans all weekly release list posts, collects
starred entries (top picks), and auto-generates monthly recap pages grouped
by year and month. Each recap links back to the original review.

Star notation in release headings:
    - Trailing `` *``  — noteworthy release (single star)
    - Trailing `` **`` — top-tier pick (double star)

Generated files are written to: ``posts/{year}/{month}/recap.md``
"""

import datetime
import markdown
import mkdocs_gen_files

from collections import defaultdict
from dataclasses import dataclass
from glob import glob
from pathlib import Path

from bs4 import BeautifulSoup
from bs4.element import NavigableString


RELEASES_GLOB = "docs/**/releases.md"
DOCS_ROOT = Path("docs")
EXCERPT_SEPARATOR_AFTER = 2  # Insert <!-- more --> after this many entries (0-based)
DEFAULT_AUTHOR = "chamberbot"


@dataclass
class StarredRelease:
    """A single starred release extracted from a weekly release list."""

    name: str
    file_path: str
    date: datetime.date
    anchor: str


def _parse_starred_releases(release_list_path: str) -> list[StarredRelease]:
    """Parse a release list Markdown file and extract all starred entries.

    Reads the file via mkdocs_gen_files, converts Markdown to HTML,
    and scans ``<h2>`` headings for trailing star notation.

    Args:
        release_list_path: Filesystem path to the releases.md file
            relative to the project root
            (e.g. ``docs/posts/2026/01/09/releases.md``).

    Returns:
        A list of StarredRelease objects found in the file.
    """
    mkdocs_path = Path(release_list_path).relative_to(DOCS_ROOT)

    with mkdocs_gen_files.open(str(mkdocs_path), "r") as f:
        md = markdown.Markdown(extensions=["meta", "toc"])
        html = md.convert(f.read())

    soup = BeautifulSoup(html, "html.parser")
    release_date = datetime.datetime.strptime(md.Meta["date"][0], "%Y-%m-%d").date()

    starred: list[StarredRelease] = []

    for h2 in soup.find_all("h2"):
        for child in h2.children:
            if isinstance(child, NavigableString) and (
                child.endswith(" *") or child.endswith(" **")
            ):
                starred.append(
                    StarredRelease(
                        name=child.rstrip(" *"),
                        file_path=str(mkdocs_path),
                        date=release_date,
                        anchor=h2.get("id", ""),
                    )
                )

    return starred


def _build_recap_markdown(
    year: int, month_name: str, releases: list[StarredRelease]
) -> str:
    """Build the Markdown content for a monthly recap page.

    Generates front-matter, a heading, and a Material card grid for each
    starred release with a link back to the original review.

    Args:
        year: The recap year (e.g. 2026).
        month_name: Full English month name (e.g. "January").
        releases: Starred releases to include, in chronological order.

    Returns:
        The complete Markdown string for the recap file.
    """
    month_number = f"{datetime.datetime.strptime(month_name, '%B').month:02d}"

    lines: list[str] = [
        "---",
        f"date: {year}-{month_number}-01",
        "draft: true",
        "categories:",
        "    - Autogen",
        "authors:",
        f"    - {DEFAULT_AUTHOR}",
        "---",
        "",
        f"# {month_name} {year} Recap",
        "",
    ]

    for index, release in enumerate(releases):
        # Navigate up to docs root from posts/YYYY/MM/, then back down
        release_link = f"../../../{release.file_path}#{release.anchor}"

        lines.extend([
            "<div class='grid cards' markdown>",
            "",
            f"-   ### {release.name}",
            "",
            "    ---",
            "",
            f"    [:octicons-arrow-right-24: Reference]({release_link})",
            "",
            "</div>",
            "",
        ])

        if index == EXCERPT_SEPARATOR_AFTER:
            lines.extend(["<!-- more -->", ""])

    return "\n".join(lines)


def generate_recaps() -> None:
    """Collect starred releases and write monthly recap files.

    Scans all release list posts matching ``RELEASES_GLOB``, groups starred
    entries by year and month, sorts them chronologically, and writes a
    recap Markdown file for each month that contains at least one starred
    release.
    """
    recaps: dict[int, dict[str, list[StarredRelease]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for path in sorted(glob(RELEASES_GLOB, recursive=True)):
        for release in _parse_starred_releases(path):
            month_name = release.date.strftime("%B")
            recaps[release.date.year][month_name].append(release)

    for year, months in sorted(recaps.items()):
        for month_name, releases in months.items():
            month_number = f"{datetime.datetime.strptime(month_name, '%B').month:02d}"
            output_path = f"posts/{year}/{month_number}/recap.md"

            releases.sort(key=lambda r: r.name)
            content = _build_recap_markdown(year, month_name, releases)

            with mkdocs_gen_files.open(output_path, "w") as f:
                f.write(content)


generate_recaps()
