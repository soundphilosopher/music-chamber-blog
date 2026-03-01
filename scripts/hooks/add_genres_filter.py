"""
Genre Filter Hook for Music Chamber.

An MkDocs ``on_post_page`` hook that injects a text input and
client-side JavaScript into the auto-generated genre overview page.

The input filters genre sections (``<h2>`` headings together with
their release lists and separators) as the user types.  Matching
TOC entries in the right sidebar are hidden/shown in sync.

Filtering behaviour:
    - **≤ 1 character** — all genre sections are shown.
    - **≥ 2 characters** — only genre sections whose heading text
      contains the search term (case-insensitive) remain visible.
"""

from __future__ import annotations

from bs4 import BeautifulSoup
from mkdocs.structure.pages import Page
from mkdocs.config import Config

FILTER_INPUT = (
    '<input'
    '  type="text"'
    '  id="genre-filter-input"'
    '  placeholder="🔍 Filter genres …"'
    '  style="'
    "    width: 100%;"
    "    padding: .6rem 1rem;"
    "    font-size: .85rem;"
    "    border: 1px solid var(--md-default-fg-color--lighter);"
    "    border-radius: .3rem;"
    "    background: var(--md-default-bg-color);"
    "    color: var(--md-default-fg-color);"
    "    outline: none;"
    "    transition: border-color .2s;"
    '"'
    '  onfocus="this.style.borderColor=\'var(--md-primary-fg-color)\'"'
    '  onblur="this.style.borderColor=\'var(--md-default-fg-color--lighter)\'"'
    "/>"
)

FILTER_SCRIPT = """\
<script>
(function () {
  var input = document.getElementById("genre-filter-input");
  if (!input) return;

  var parent = input.closest(".md-typeset") || input.parentElement.parentElement;

  /* ── Collect genre sections ──────────────────────────────────── */
  function collectSections() {
    var sections = [];
    var current  = null;
    var children = Array.prototype.slice.call(parent.children);

    for (var i = 0; i < children.length; i++) {
      var el = children[i];

      if (el.id === "genre-filter") continue;

      if (el.tagName === "H2") {
        current = {
          elements: [el],
          text: el.textContent.toLowerCase()
        };
        sections.push(current);
      } else if (current) {
        current.elements.push(el);
      }
      /* Elements before the first h2 (h1, filter div) stay visible */
    }
    return sections;
  }

  var sections = collectSections();

  /* ── Filter logic ────────────────────────────────────────────── */
  input.addEventListener("input", function () {
    var term = this.value.trim().toLowerCase();

    for (var i = 0; i < sections.length; i++) {
      var show    = term.length <= 1 || sections[i].text.indexOf(term) !== -1;
      var display = show ? "" : "none";

      for (var j = 0; j < sections[i].elements.length; j++) {
        sections[i].elements[j].style.display = display;
      }
    }

    /* ── Sync TOC sidebar ──────────────────────────────────────── */
    var tocLinks = document.querySelectorAll(
      ".md-sidebar--secondary .md-nav__link"
    );
    for (var k = 0; k < tocLinks.length; k++) {
      var link = tocLinks[k];
      var href = link.getAttribute("href") || "";
      if (href.indexOf("#") !== 0) continue;
      var targetId = href.substring(1);
      var targetEl = document.getElementById(targetId);
      if (!targetEl) continue;
      link.parentElement.style.display = targetEl.style.display;
    }
  });
})();
</script>
"""


def on_post_page(output: str, page: Page, config: Config) -> str:
    """MkDocs hook: inject a client-side genre filter into the genres page.

    Only processes the auto-generated ``genres.md`` page.  Populates the
    ``<div id="genre-filter">`` placeholder emitted by the generator
    with a search input, and appends the filtering script.

    Args:
        output: The full rendered HTML output of the page.
        page:   The MkDocs Page object.
        config: The global MkDocs config dict.

    Returns:
        The modified HTML with the filter input and script injected,
        including TOC synchronisation.
    """
    if page.file.src_path != "genres.md":
        return output

    soup = BeautifulSoup(output, "html.parser")

    placeholder = soup.find("div", id="genre-filter")
    if not placeholder:
        return output

    placeholder.append(BeautifulSoup(FILTER_INPUT, "html.parser"))
    soup.append(BeautifulSoup(FILTER_SCRIPT, "html.parser"))

    return str(soup)
