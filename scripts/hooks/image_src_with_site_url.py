"""
Image Source Rewriter Hook for Music Chamber.

An MkDocs ``on_post_page`` hook that replaces ``site:`` prefixed image
sources with absolute URLs based on the configured ``site_url``.

This allows Markdown authors to write portable image paths like::

    ![Album Cover](site:assets/images/cover.jpeg)

which get rewritten at build time to::

    <img src="https://example.github.io/music-chamber-blog/assets/images/cover.jpeg">

The hook runs in the ``on_post_page`` phase (after full page rendering)
so that it also catches images rendered inside blog excerpts on the index
page, where relative paths would otherwise break.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

SITE_PREFIX = "site:"
SITE_PREFIX_LENGTH = len(SITE_PREFIX)
SITE_PREFIX_PATTERN = re.compile(rf"^{re.escape(SITE_PREFIX)}")


def on_post_page(output: str, page, config: dict) -> str:
    """MkDocs hook: rewrite ``site:`` image sources to absolute URLs.

    Performs a fast early-exit check on the raw HTML string before
    parsing with BeautifulSoup.

    Args:
        output: The fully rendered HTML of the page.
        page: The MkDocs Page object.
        config: The global MkDocs config dict (must contain ``site_url``).

    Returns:
        The modified HTML with ``site:`` image sources resolved to
        absolute URLs, or the original HTML unchanged if no
        ``site:`` prefix was found.
    """
    if SITE_PREFIX not in output:
        return output

    soup = BeautifulSoup(output, "html.parser")

    for img in soup.find_all("img", src=SITE_PREFIX_PATTERN):
        img["src"] = f'{config["site_url"]}{img["src"][SITE_PREFIX_LENGTH:]}'

    return str(soup)
