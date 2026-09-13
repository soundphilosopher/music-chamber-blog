"""
Markdown escaping utilities.
"""


def escape_link_text(text: str) -> str:
    """Escape a string so it is safe as Markdown link text.

    Release titles are interpolated into ``[title](target)`` links by the
    generators. A title containing an unbalanced bracket closes the link
    text early, which silently produces literal ``[...]`` output and an
    empty anchor instead of a working link.

    Args:
        text: Raw text to place inside the square brackets of a link
            (e.g. a release heading like ``"Leonardo Barbierato - ]ex(s)it(u)["``).

    Returns:
        The text with backslashes and square brackets backslash-escaped
            (e.g. ``"Leonardo Barbierato - \\]ex(s)it(u)\\["``).
    """
    for char in ("\\", "[", "]"):
        text = text.replace(char, f"\\{char}")

    return text
