"""
Release Count Hook for Music Chamber.

An MkDocs ``on_post_page`` hook that appends a release count badge to the
sidebar navigation of weekly release list posts.

For every page whose source path ends with ``releases.md``, the hook:

1. Counts the ``<h2>`` headings inside the article (each heading
   represents one release).
2. Locates the first section-level navigation list in the sidebar.
3. Appends a new nav item that displays a music-box icon followed by
   the text *"N releases"*.
"""

import copy
import logging

from bs4 import BeautifulSoup, Tag
from mkdocs.config import Config
from mkdocs.structure.pages import Page

from utils.icons import MUSIC_BOX_OUTLINE_TAG


log = logging.getLogger("mkdocs.hooks.add_release_count")


def _build_release_count_item(count: int, soup: BeautifulSoup) -> Tag:
    """Build a ``<li>`` nav item that shows the release count with an icon.

    Constructs the following HTML fragment::

        <li class="md-nav__item">
          <div class="md-nav__link">
            <svg>…</svg>
            <span class="md-ellipsis">N releases</span>
          </div>
        </li>

    Args:
        count: Number of releases to display.
        soup:  The parent BeautifulSoup document (used to create new tags).

    Returns:
        A ``<li>`` tag ready to be appended to a ``md-nav__list``.
    """
    li = soup.new_tag("li", attrs={"class": "md-nav__item"})
    div = soup.new_tag("div", attrs={"class": "md-nav__link"})
    span = soup.new_tag("span", attrs={"class": "md-ellipsis"}, string=f"{count} releases")

    div.append(copy.copy(MUSIC_BOX_OUTLINE_TAG))
    div.append(span)
    li.append(div)
    return li


def on_post_page(output: str, page: Page, config: Config) -> str:
    """MkDocs hook: append a release count to the sidebar navigation.

    Only processes pages whose source path ends with ``releases.md``.

    Args:
        output: The fully rendered HTML of the page.
        page:   The MkDocs Page object.
        config: The global MkDocs config dict.

    Returns:
        The modified HTML with the release count appended to the nav,
        or the original HTML if the page is not a releases page.
    """
    src = page.file.src_path
    if not (src.endswith("releases.md") and src.startswith("posts")):
        return output

    soup = BeautifulSoup(output, "html.parser")

    article = soup.find("article", class_="md-content__inner md-typeset")
    if article is None:
        return output

    releases = article.find_all("h2")

    meta = soup.find("li", class_="md-nav__item md-nav__item--section")
    if meta is None:
        return str(soup)

    metalist = meta.find_next("ul", class_="md-nav__list")
    if metalist is None:
        return str(soup)

    metalist.append(_build_release_count_item(len(releases), soup))

    return str(soup)
