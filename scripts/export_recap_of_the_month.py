"""Export the recap picks of a month into a plain text file.

The script scans every weekly ``releases.md`` post of the given month and
collects all release headings that carry a trailing star marker:

    - Trailing `` **`` -- top pick
    - Trailing `` *``  -- pick

The result is written as a text file with one section per pick type. Each
release is followed by its fully expanded genres (comma separated). Releases
are sorted by name, ignoring case. A section without any release is left out. An existing output file is overwritten.

Usage:
    python scripts/export_recap_of_the_month.py --month <YYYY-MM> [--output <path>]

Args:
    month: Month to export in YYYY-MM format (e.g. 2026-09).
    output: Output file path. Defaults to scripts/raw/recap.txt.

Example:
    python scripts/export_recap_of_the_month.py --month 2026-09
"""

import argparse
import logging
import re

from dataclasses import dataclass, field
from pathlib import Path

from utils.genres import GENRE_TAG_PREFIX, normalize_genre_names


logging.basicConfig(level=logging.INFO)
log = logging.getLogger("scripts.export_recap_of_the_month")

# Root path for MkDocs blog posts. Weekly posts live in POSTS_PATH/YYYY/MM/DD/.
POSTS_PATH = Path("docs/posts")

# Default location of the exported recap file.
EXPORT_PATH = Path("scripts/raw")

# Name of the weekly release list inside each post folder.
RELEASES_FILE = "releases.md"

# Expected format of the month argument.
MONTH_PATTERN = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")

# Release headings are level 3 headings (``### Artist - Title``).
HEADING_PREFIX = "### "

# Star suffixes marking recap picks. Order matters: " **" also ends with " *",
# so the double star has to be checked first.
TOP_PICK_SUFFIX = " **"
PICK_SUFFIX = " *"


@dataclass
class Pick:
    """A starred release of a weekly post.

    Attributes:
        name: Release heading without the star marker (``"Artist - Title"``).
        genres: Expanded genre names (e.g. ``["Post Punk", "Shoegaze"]``).
    """

    name: str
    genres: list[str] = field(default_factory=list)


def parse_month(value: str) -> tuple[str, str]:
    """Split a ``YYYY-MM`` string into year and month folder names.

    Args:
        value: Month in YYYY-MM format (e.g. ``"2026-09"``).

    Returns:
        A ``(year, month)`` tuple of zero padded strings (e.g. ``("2026", "09")``).

    Raises:
        argparse.ArgumentTypeError: If the value is not in YYYY-MM format.
    """
    match = MONTH_PATTERN.match(value)
    if not match:
        raise argparse.ArgumentTypeError(f"Month must be in YYYY-MM format, got '{value}'")

    return match.group(1), match.group(2)


def month_arg(value: str) -> str:
    """Argparse type that validates a ``YYYY-MM`` month and returns it unchanged."""
    parse_month(value)

    return value


def collect_picks(releases_path: Path) -> tuple[list[Pick], list[Pick]]:
    """Collect the starred releases of one weekly releases post.

    Args:
        releases_path: Path to a ``releases.md`` file.

    Returns:
        A ``(top_picks, picks)`` tuple of picks in file order, with the star
        marker removed from the name (e.g. ``"Elipsis - Elipsis"``) and the
        genres of the release expanded (e.g. ``["Psychedelic Rock"]``).
    """
    top_picks: list[Pick] = []
    picks: list[Pick] = []
    current: Pick | None = None

    for line in releases_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(HEADING_PREFIX):
            heading = line.rstrip()
            current = None
            if heading.endswith(TOP_PICK_SUFFIX):
                current = Pick(heading.removeprefix(HEADING_PREFIX).removesuffix(TOP_PICK_SUFFIX).rstrip())
                top_picks.append(current)
            elif heading.endswith(PICK_SUFFIX):
                current = Pick(heading.removeprefix(HEADING_PREFIX).removesuffix(PICK_SUFFIX).rstrip())
                picks.append(current)
        elif current is not None and line.startswith(GENRE_TAG_PREFIX):
            tags = line.removeprefix(GENRE_TAG_PREFIX).split(",")
            current.genres = normalize_genre_names([tag.strip().lower() for tag in tags if tag.strip()])

    return top_picks, picks


def render_section(title: str, picks: list[Pick]) -> str:
    """Render one section: a title line followed by every pick and its genres.

    Args:
        title: Section title without the surrounding ``###`` markers.
        picks: Picks to list. Releases are separated by a blank line.

    Returns:
        The section text without a trailing newline.
    """
    entries: list[str] = []
    for pick in picks:
        lines = [f"- {pick.name}"]
        if pick.genres:
            lines.append(f"  {', '.join(pick.genres)}")
        entries.append("\n".join(lines))

    return f"### {title} ###\n" + "\n\n".join(entries)


def build_recap(top_picks: list[Pick], picks: list[Pick]) -> str:
    """Render the recap text. Sections without releases are left out.

    Args:
        top_picks: Releases marked with ``**``.
        picks: Releases marked with ``*``.

    Returns:
        The recap text (empty if there are no picks at all).
    """
    sections: list[str] = []

    if top_picks:
        sections.append(render_section("top picks", top_picks))
    if picks:
        sections.append(render_section("picks", picks))

    return "\n\n".join(sections) + "\n" if sections else ""


def export_recap_of_the_month(month: str, output_file: Path) -> None:
    """Export all recap picks of a month into a text file.

    Each section is sorted by release name (artist first), ignoring case.
    An existing output file is overwritten.

    Args:
        month: Month in YYYY-MM format (e.g. ``"2026-09"``).
        output_file: Path of the text file to write.
    """
    year, month_number = parse_month(month)
    month_path = POSTS_PATH / year / month_number
    log.info(f"Exporting recap for {month} to {output_file}")

    release_files = sorted(month_path.glob(f"*/{RELEASES_FILE}"))
    if not release_files:
        log.warning(f"No {RELEASES_FILE} files found in {month_path}")

    top_picks: list[Pick] = []
    picks: list[Pick] = []
    for release_file in release_files:
        week_top_picks, week_picks = collect_picks(release_file)
        top_picks.extend(week_top_picks)
        picks.extend(week_picks)

    top_picks.sort(key=lambda pick: pick.name.casefold())
    picks.sort(key=lambda pick: pick.name.casefold())

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(build_recap(top_picks, picks), encoding="utf-8")
    log.info(f"Wrote {len(top_picks)} top picks and {len(picks)} picks from {len(release_files)} posts")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export recap of the month")
    parser.add_argument("--month", type=month_arg, required=True, help="Month in YYYY-MM format")
    parser.add_argument("--output", type=Path, default=EXPORT_PATH / "recap.txt", help="Output file path")
    args = parser.parse_args()

    export_recap_of_the_month(args.month, args.output)
