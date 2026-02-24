"""
Cleanup Tags Hook for Music Chamber.

An MkDocs ``on_post_page`` hook that strips custom inline tags from
the rendered HTML before it is written to disk.

Tags follow the ``::prefix::value`` convention used throughout the
Music Chamber Markdown sources.  For example, a genre annotation::

    ::genre::Ambient, Cinematic Synth

is rendered by MkDocs as a plain ``<p>`` element.  This hook locates
those elements and removes them so they never appear in the published
page.

**Extending with new tag types**

To clean up an additional tag prefix, add a new :class:`TagRule` entry
to the :data:`TAG_RULES` tuple::

    TAG_RULES: tuple[TagRule, ...] = (
        TagRule(prefix="::genre::"),
        TagRule(prefix="::mood::"),
        TagRule(prefix="::label::", html_element="span"),
    )

Each rule specifies the prefix to match and, optionally, the HTML
element type to search (defaults to ``"p"``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Tag rule definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TagRule:
    """A single cleanup rule that targets a specific tag prefix.

    Attributes:
        prefix: The literal prefix string that marks the tag in the
            Markdown source (e.g. ``"::genre::"``).
        html_element: The HTML element name that wraps the tag once
            rendered (default ``"p"``).
        pattern: A compiled regex anchored to the start of the
            element's text.  Derived automatically from *prefix*;
            not intended to be set manually.
    """

    prefix: str
    html_element: str = "p"
    pattern: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "pattern", re.compile(rf"^{re.escape(self.prefix)}")
        )


# ---------------------------------------------------------------------------
# Tag rule registry — extend this tuple to clean up additional tags
# ---------------------------------------------------------------------------

TAG_RULES: tuple[TagRule, ...] = (
    TagRule(prefix="::genre::"),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _contains_any_prefix(html: str, rules: tuple[TagRule, ...]) -> bool:
    """Fast plain-text check for the presence of at least one tag prefix.

    Avoids the cost of HTML parsing when the page contains none of the
    configured prefixes.

    Args:
        html: The raw HTML string of the page.
        rules: The tag rules to check against.

    Returns:
        ``True`` if *html* contains at least one prefix, ``False``
        otherwise.
    """
    return any(rule.prefix in html for rule in rules)


def _remove_matching_elements(
    soup: BeautifulSoup, rules: tuple[TagRule, ...]
) -> None:
    """Remove all HTML elements that match the configured tag rules.

    Iterates over every rule and decomposes (removes from the tree)
    each element whose text matches the rule's pattern.  The *soup*
    is modified in place.

    Args:
        soup: The parsed HTML document.
        rules: The tag rules to apply.
    """
    for rule in rules:
        for element in soup.find_all(rule.html_element, string=rule.pattern):
            element.decompose()


# ---------------------------------------------------------------------------
# MkDocs hook entry point
# ---------------------------------------------------------------------------

def on_post_page(output: str, page, config: dict) -> str:
    """MkDocs hook: strip custom inline tags from the rendered page.

    Performs a fast early-exit check on the raw HTML string before
    parsing with BeautifulSoup.  When at least one tag prefix is
    detected, the page is parsed once and all matching elements are
    removed in a single pass.

    Args:
        output: The fully rendered HTML of the page.
        page: The MkDocs Page object.
        config: The global MkDocs config dict.

    Returns:
        The cleaned HTML with all matched tag elements removed, or
        the original HTML unchanged when no prefixes were found.
    """
    if not _contains_any_prefix(output, TAG_RULES):
        return output

    soup = BeautifulSoup(output, "html.parser")
    _remove_matching_elements(soup, TAG_RULES)

    return str(soup)
