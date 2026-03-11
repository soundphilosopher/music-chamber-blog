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
        # Default — find <p> whose text starts with the prefix, remove it.
        TagRule(prefix="::genre::"),

        # parent — search every <li class="song-entry"> in the DOM; if one
        # contains a <span class="label"> with the prefix anywhere inside,
        # remove the whole <li>.
        #
        #   <li class="song-entry">        ← removed
        #     <a>
        #       <span class="label">::song::Title</span>
        #     </a>
        #   </li>
        TagRule(
            prefix="::song::",
            html_element=TagSelector("span", attrs={"class": "label"}),
            parent=TagSelector("li", attrs={"class": "song-entry"}),
        ),

        # child — search every <li class="track"> in the DOM; if one
        # contains a <span> with the prefix anywhere inside, remove
        # just that <span>.
        #
        #   <li class="track">             ← kept
        #     <a>
        #       <span>::note::…</span>     ← removed
        #     </a>
        #   </li>
        TagRule(
            prefix="::note::",
            html_element=TagSelector("li", attrs={"class": "track"}),
            child=TagSelector("span"),
        ),
    )

``parent`` and ``child`` are mutually exclusive — set at most one per rule.

Both modes use the same **top-down** strategy: the outer element is
located first, then :py:meth:`bs4.Tag.find` descends into it to confirm
the prefix is present.  This avoids any reliance on ``find_parent`` and
works regardless of how deeply the prefix-carrying tag is nested.
"""

import re

from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Tag selector — BS4-style element specification
# ---------------------------------------------------------------------------

@dataclass
class TagSelector:
    """A BeautifulSoup-style element specification used inside :class:`TagRule`.

    Mirrors the ``name`` / ``attrs`` arguments accepted by BeautifulSoup's
    ``find`` and ``find_all`` methods, so you can narrow a match to a
    specific tag name, CSS class, ``id``, or any other HTML attribute.

    Attributes:
        name: The HTML tag name to match (e.g. ``"p"``, ``"span"``,
            ``"li"``).
        attrs: An optional mapping of attribute filters understood by
            BeautifulSoup (e.g. ``{"class": "song-entry", "id": "main"}``).
            A ``class`` value may be a list to require multiple classes.
            Defaults to an empty dict — match *any* element with the given
            tag name.

    Examples::

        TagSelector("p")
        TagSelector("span", attrs={"class": "genre-tag"})
        TagSelector("li",   attrs={"class": ["nav-item", "active"]})
        TagSelector("div",  attrs={"id": "sidebar"})
    """

    name: str
    attrs: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Tag rule definition
# ---------------------------------------------------------------------------

@dataclass
class TagRule:
    """A single cleanup rule that targets a specific tag prefix.

    Attributes:
        prefix: The literal prefix string that marks the tag in the
            Markdown source (e.g. ``"::genre::"``).
        html_element: A :class:`TagSelector` describing the HTML element
            that directly carries the prefix text once rendered.  In
            *parent* mode this is the inner element searched for *inside*
            the parent container.  In *child* mode it is the outer
            container that is scanned.  Defaults to a plain ``<p>``.
        parent: When set, the DOM is searched for every element matching
            this selector.  If a matching ``html_element`` with the prefix
            text is found anywhere inside, the **parent element** (the
            outer one) is removed.  Mutually exclusive with *child*.
        child: When set, the DOM is searched for every element matching
            ``html_element``.  If a matching descendant with the prefix
            text is found anywhere inside, that **child element** (the
            inner one) is removed.  Mutually exclusive with *parent*.
        pattern: A compiled regex anchored to the start of the element's
            text.  Derived automatically from *prefix*; not intended to
            be set manually.
    """

    prefix: str
    html_element: TagSelector = field(default_factory=lambda: TagSelector("p"))
    parent: TagSelector | None = None
    child: TagSelector | None = None
    pattern: re.Pattern[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.parent is not None and self.child is not None:
            raise ValueError(
                f"TagRule '{self.prefix}': 'parent' and 'child' are mutually "
                "exclusive — set at most one per rule."
            )
        self.pattern = re.compile(rf"^\s*{re.escape(self.prefix)}")


# ---------------------------------------------------------------------------
# Tag rule registry — extend this tuple to clean up additional tags
# ---------------------------------------------------------------------------

TAG_RULES: tuple[TagRule, ...] = (
    TagRule(prefix="::genre::"),
    TagRule(
        prefix="Privacy Policy",
        html_element=TagSelector("span", attrs={"class": "md-ellipsis"}),
        parent=TagSelector("li", attrs={"class": "md-nav__item"}),
    ),
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


def _apply_parent_rule(soup: BeautifulSoup, rule: TagRule) -> None:
    """Remove outer *parent* elements that contain a matching inner element.

    Searches the DOM top-down: every element matching ``rule.parent`` is
    visited, and :py:meth:`bs4.Tag.find` descends into it looking for a
    ``rule.html_element`` whose text matches the prefix.  When the inner
    element is found the entire parent container is decomposed.

    Example — ``html_element=TagSelector("span")``,
    ``parent=TagSelector("li", attrs={"class": "list-item"})``::

        <li class="list-item">   ← decomposed
          <a>
            <span>My text</span> ← found by find(), confirms the match
          </a>
        </li>

    Args:
        soup: The parsed HTML document (modified in place).
        rule: The :class:`TagRule` whose ``parent`` field is not ``None``.
    """
    if not rule.parent:
        return

    for container in soup.find_all(rule.parent.name, attrs=rule.parent.attrs):
        match = container.find(
            name=rule.html_element.name,
            attrs=rule.html_element.attrs,
        )
        if match is not None and rule.pattern.match(match.text):
            container.decompose()


def _apply_child_rule(soup: BeautifulSoup, rule: TagRule) -> None:
    """Remove inner *child* elements found inside a matching outer element.

    Searches the DOM top-down: every element matching ``rule.html_element``
    is visited, and :py:meth:`bs4.Tag.find` descends into it looking for a
    ``rule.child`` whose text matches the prefix.  When the inner element
    is found it alone is decomposed, leaving the outer container intact.

    Example — ``html_element=TagSelector("li")``,
    ``child=TagSelector("span")``::

        <li>                     ← kept
          <a>
            <span>My text</span> ← found by find(), decomposed
          </a>
        </li>

    Args:
        soup: The parsed HTML document (modified in place).
        rule: The :class:`TagRule` whose ``child`` field is not ``None``.
    """
    if not rule.child:
        return

    for container in soup.find_all(
        rule.html_element.name, attrs=rule.html_element.attrs
    ):
        match = container.find(
            name=rule.child.name,
            attrs=rule.child.attrs,
        )
        if match is not None and rule.pattern.match(match.text):
            match.decompose()


def _apply_default_rule(soup: BeautifulSoup, rule: TagRule) -> None:
    """Remove elements that directly carry the prefix text.

    Uses ``string=rule.pattern`` in ``find_all`` so only elements whose
    entire text content matches the prefix are selected.  The element
    itself is decomposed with no further traversal.

    Args:
        soup: The parsed HTML document (modified in place).
        rule: The :class:`TagRule` with neither ``parent`` nor ``child``
            set.
    """
    for element in soup.find_all(
        name=rule.html_element.name,
        attrs=rule.html_element.attrs,
    ):
        if rule.pattern.match(element.text):
            element.decompose()


def _remove_matching_elements(
    soup: BeautifulSoup, rules: tuple[TagRule, ...]
) -> None:
    """Remove all HTML elements that match the configured tag rules.

    Dispatches each rule to the appropriate helper based on which
    traversal mode is active:

    * ``rule.parent`` set → :func:`_apply_parent_rule` (top-down, removes
      outer container)
    * ``rule.child`` set → :func:`_apply_child_rule` (top-down, removes
      inner descendant)
    * neither set → :func:`_apply_default_rule` (direct text match,
      removes the element itself)

    *soup* is modified in place.

    Args:
        soup: The parsed HTML document.
        rules: The tag rules to apply.
    """
    for rule in rules:
        if rule.parent is not None:
            _apply_parent_rule(soup, rule)
        elif rule.child is not None:
            _apply_child_rule(soup, rule)
        else:
            _apply_default_rule(soup, rule)


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
