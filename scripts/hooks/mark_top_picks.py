"""
Mark Top Picks Hook for Music Chamber.

An MkDocs ``on_page_content`` hook that transforms starred release headings
in weekly release list posts into styled Material card components.

Star notation in release headings:
    - Trailing `` *``  — wraps the entry in a ``top-list-rerun`` card (subtle highlight)
    - Trailing `` **`` — wraps the entry in a ``top-list-recap`` card (bold highlight)

The hook strips the star markers from headings after classification and
restructures the HTML so each starred entry (heading + description) is
enclosed in a Material grid card ``<div>``.
"""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

# Maps star suffixes to their corresponding CSS card class.
# Order matters: double-star must be checked before single-star,
# because " **" also ends with " *".
STAR_CLASSES: list[tuple[str, str]] = [
    (" **", "top-list-recap"),
    (" *", "top-list-rerun"),
]


def _strip_trailing_stars(heading: Tag) -> None:
    """Remove trailing star markers from the last text node in a heading.

    Iterates the heading's children in reverse to find the last
    ``NavigableString`` and strips any trailing `` *`` characters from it.

    Args:
        heading: A BeautifulSoup ``<h2>`` tag whose text content may
            end with star markers.
    """
    for child in reversed(heading.contents):
        if isinstance(child, NavigableString):
            child.replace_with(child.rstrip(" *"))
            return


def _wrap_in_card(
    heading: Tag, description: Tag, css_class: str, soup: BeautifulSoup
) -> None:
    """Wrap a heading and its description paragraph in a Material grid card.

    Constructs the following HTML structure and inserts it where the
    heading originally appeared::

        <div class="grid cards {css_class}">
          <ul>
            <li>
              <h2>…</h2>
              <hr>
              <p>…</p>
            </li>
          </ul>
        </div>

    Args:
        heading: The ``<h2>`` tag to move into the card.
        description: The ``<p>`` tag following the heading.
        css_class: CSS class applied alongside ``grid cards``
            (e.g. ``top-list-recap`` or ``top-list-rerun``).
        soup: The parent BeautifulSoup document (used to create new tags).
    """
    card_div = soup.new_tag("div", attrs={"class": f"grid cards {css_class}"})
    ul_tag = soup.new_tag("ul")
    li_tag = soup.new_tag("li")
    hr_tag = soup.new_tag("hr")

    genre = description.find_next_sibling("p", attrs={"class": "genre-tags"})

    heading.insert_before(card_div)

    li_tag.append(heading.extract())
    li_tag.append(hr_tag)
    li_tag.append(description.extract())

    if genre:
        li_tag.append(genre.extract())

    ul_tag.append(li_tag)
    card_div.append(ul_tag)


def on_page_content(html: str, page, config, files) -> str:
    """MkDocs hook: transform starred headings into Material card components.

    Only processes pages whose source path ends with ``releases.md``.
    For each ``<h2>`` heading, checks for star suffixes and wraps matching
    entries (heading + following paragraph) in styled card divs.

    Args:
        html: The rendered HTML content of the page.
        page: The MkDocs Page object.
        config: The global MkDocs config dict.
        files: The MkDocs Files collection.

    Returns:
        The modified HTML with starred entries wrapped in cards.
    """
    if not page.file.src_path.endswith("releases.md"):
        return html

    soup = BeautifulSoup(html, "html.parser")

    for h2 in soup.find_all("h2"):
        normalized_text = " ".join(h2.text.split())
        description = h2.find_next_sibling("p")

        if not description:
            continue

        for suffix, css_class in STAR_CLASSES:
            if normalized_text.endswith(suffix):
                _strip_trailing_stars(h2)
                _wrap_in_card(h2, description, css_class, soup)
                break

    return str(soup)
