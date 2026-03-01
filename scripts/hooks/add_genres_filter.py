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

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup
from mkdocs.structure.pages import Page
from mkdocs.config import Config

CLEAR_ICON_PATH = Path("assets", "icons", "close-circle-outline.svg")

FILTER_INPUT_TEMPLATE = """\
<div id="genre-filter-wrapper" style="\
position:relative;\
width:100%;\
">\
<input\
  type="text"\
  id="genre-filter-input"\
  placeholder="🔍 Filter genres …"\
  style="\
    width:100%;\
    padding:.6rem 2.4rem .6rem 1rem;\
    font-size:.85rem;\
    border:1px solid var(--md-default-fg-color--lighter);\
    border-radius:.3rem;\
    background:var(--md-default-bg-color);\
    color:var(--md-default-fg-color);\
    outline:none;\
    transition:border-color .2s;\
    box-sizing:border-box;\
  "\
  onfocus="this.style.borderColor='var(--md-primary-fg-color)'"\
  onblur="this.style.borderColor='var(--md-default-fg-color--lighter)'"\
/>\
<button id="genre-filter-clear" type="button" aria-label="Clear filter"\
  style="\
    display:none;\
    position:absolute;\
    right:.45rem;\
    top:50%;\
    transform:translateY(-50%);\
    background:none;\
    border:none;\
    cursor:pointer;\
    padding:0;\
    line-height:0;\
  ">\
  {clear_icon}\
</button>\
</div>\
"""

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


def _load_clear_icon(docs_dir: str) -> str:
    """Read the close-circle SVG from disk and apply inline styles.

    Parses the SVG with BeautifulSoup so we can inject size, fill and
    transition styles directly onto the ``<svg>`` element.

    Args:
        docs_dir: Absolute path to the MkDocs ``docs/`` directory.

    Returns:
        The SVG markup as a string with inline styles applied.
    """
    svg_path = Path(docs_dir) / CLEAR_ICON_PATH
    svg_soup = BeautifulSoup(svg_path.read_text(encoding="utf-8"), "html.parser")
    svg_tag = svg_soup.find("svg")
    svg_tag["style"] = (
        "width:1.15rem;"
        "height:1.15rem;"
        "fill:var(--md-default-fg-color--light);"
        "transition:fill .15s"
    )
    return str(svg_tag)


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

    clear_icon = _load_clear_icon(config["docs_dir"])
    filter_html = FILTER_INPUT_TEMPLATE.format(clear_icon=clear_icon)

    placeholder.append(BeautifulSoup(filter_html, "html.parser"))
    soup.append(BeautifulSoup(FILTER_SCRIPT, "html.parser"))

    return str(soup)
