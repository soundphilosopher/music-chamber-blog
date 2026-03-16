"""
Genre Filter Hook for Music Chamber.

An MkDocs ``on_post_page`` hook that injects a text input and
client-side JavaScript into the auto-generated genre overview page.

The input filters genre sections (``<h2>`` headings together with
their release lists and separators) as the user types.  Matching
TOC entries in the right sidebar are hidden/shown in sync.

A clear button (close-circle SVG loaded from
``docs/assets/icons/close-circle-outline.svg``) appears on the right
side of the input as soon as the user types something.  Clicking it
clears the input and resets all sections back to visible.

Filtering behaviour:
    - **≤ 1 character** — all genre sections are shown.
    - **≥ 2 characters** — only genre sections whose heading text
      contains the search term (case-insensitive) remain visible.
"""

import copy
import logging

from bs4 import BeautifulSoup, Tag
from mkdocs.structure.pages import Page
from mkdocs.config import Config

from utils.icons import CLOSE_CIRCLE_OUTLINE_TAG


log = logging.getLogger("mkdocs.hooks.add_genres_filter")


FILTER_SCRIPT = """\
<script>
(function () {
  var input    = document.getElementById("genre-filter-input");
  var clearBtn = document.getElementById("genre-filter-clear");
  if (!input) return;

  /* ── Clear-button hover effect ───────────────────────────────── */
  if (clearBtn) {
    var svg = clearBtn.querySelector("svg");
    clearBtn.addEventListener("mouseenter", function () {
      if (svg) svg.style.fill = "var(--md-default-fg-color)";
    });
    clearBtn.addEventListener("mouseleave", function () {
      if (svg) svg.style.fill = "var(--md-default-fg-color--light)";
    });
  }

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
  function applyFilter() {
    var term = input.value.trim().toLowerCase();

    /* Show / hide clear button */
    if (clearBtn) {
      clearBtn.style.display = input.value.length > 0 ? "" : "none";
    }

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
  }

  input.addEventListener("input", applyFilter);

  /* ── Clear button click ──────────────────────────────────────── */
  if (clearBtn) {
    clearBtn.addEventListener("click", function () {
      input.value = "";
      input.focus();
      applyFilter();
    });
  }
})();
</script>
"""


def on_post_page(output: str, page: Page, config: Config) -> str:
    """MkDocs hook: inject a client-side genre filter into the genres page.

    Only processes the auto-generated ``genres.md`` page.  Populates the
    ``<div id="genre-filter">`` placeholder emitted by the generator
    with a search input and clear button, and appends the filtering
    script.

    The clear-button icon is read from
    ``docs/assets/icons/close-circle-outline.svg`` at build time via
    BeautifulSoup so the hook always reflects the on-disk version of
    the icon.

    Args:
        output: The full rendered HTML output of the page.
        page:   The MkDocs Page object.
        config: The global MkDocs config dict.

    Returns:
        The modified HTML with the filter input, clear button, and
        script injected, including TOC synchronisation.
    """
    if page.file.src_path != "genres.md":
        return output

    soup = BeautifulSoup(output, "html.parser")

    placeholder = soup.find("div", id="genre-filter")
    if not placeholder:
        return output

    wrapper_tag: Tag = soup.new_tag("div", attrs={"id": "genre-filter-wrapper"})
    filter_input_tag: Tag = soup.new_tag("input", attrs={
        "id": "genre-filter-input",
        "type": "text",
        "placeholder": "🔍 Filter genres …",
        "onfocus": "this.style.borderColor='var(--md-primary-fg-color)'",
        "onblur": "this.style.borderColor='var(--md-default-fg-color--lighter)'"
    })
    clear_button_tag: Tag = soup.new_tag("button", attrs={
        "id": "genre-filter-clear",
        "type": "button",
        "aria-label": "Clear filter",
        "style": "display: none;"
    })
    clear_button_tag.append(copy.copy(CLOSE_CIRCLE_OUTLINE_TAG))

    wrapper_tag.append(filter_input_tag)
    wrapper_tag.append(clear_button_tag)

    placeholder.append(wrapper_tag)
    soup.append(BeautifulSoup(FILTER_SCRIPT, "html.parser"))

    return str(soup)
