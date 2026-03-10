"""
Genre Filter Hook for Music Chamber.

An MkDocs ``on_post_page`` hook that injects a text input, a mode
select, and client-side JavaScript into the auto-generated genre
overview page.

The input filters genre sections (``<h2>`` headings together with
their release lists and separators) as the user types.  A mode select
lets the user switch between two filter behaviours:

- **Genre** (default) — sections whose heading text matches the
  search term are shown; non-matching sections are hidden.
- **Release** — individual release list items that match the search
  term are shown; genres with no matching releases are hidden
  entirely.

Matching TOC entries in the right sidebar are hidden/shown in sync
for both modes.

A clear button (close-circle SVG loaded from
``docs/assets/icons/close-circle-outline.svg``) appears on the right
side of the input as soon as the user types something.  Clicking it
clears the input and resets all sections back to visible.

Filtering behaviour:
    - **≤ 1 character** — all genre sections are shown (both modes).
    - **≥ 2 characters, Genre mode** — only genre sections whose
      heading text contains the search term (case-insensitive) remain
      visible.
    - **≥ 2 characters, Release mode** — only release list items
      whose text contains the search term remain visible; genre
      sections with no visible releases are hidden.
"""

from __future__ import annotations

import copy

from pathlib import Path

from bs4 import BeautifulSoup, Tag
from mkdocs.structure.pages import Page
from mkdocs.config import Config

CLEAR_ICON_PATH = Path(__file__).resolve().parents[2] / "docs" / "assets" / "icons" / "close-circle-outline.svg"
CLEAR_ICON_TAG: Tag = BeautifulSoup(CLEAR_ICON_PATH.read_text(encoding="utf-8"), "html.parser")

FILTER_SCRIPT = """\
<script>
(function () {
  var input    = document.getElementById("genre-filter-input");
  var clearBtn = document.getElementById("genre-filter-clear");
  var select   = document.getElementById("genre-filter-mode");
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

  /* ── Mode-select focus/blur styling ──────────────────────────── */
  if (select) {
    select.addEventListener("focus", function () {
      select.style.borderColor = "var(--md-primary-fg-color)";
    });
    select.addEventListener("blur", function () {
      select.style.borderColor = "var(--md-default-fg-color--lighter)";
    });
  }

  var filterDiv = document.getElementById("genre-filter");
  var parent    = input.closest(".md-typeset") || (filterDiv && filterDiv.parentElement);

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
          elements:    [el],
          text:        el.textContent.toLowerCase(),
          releaseList: null
        };
        sections.push(current);
      } else if (current) {
        current.elements.push(el);
        if (el.tagName === "UL") {
          current.releaseList = el;
        }
      }
      /* Elements before the first h2 (h1, filter div) stay visible */
    }
    return sections;
  }

  var sections = collectSections();

  /* ── Placeholder text per mode ───────────────────────────────── */
  var placeholders = {
    genre:   "🔍 Filter genres …",
    release: "🔍 Filter releases …"
  };

  /* ── Filter logic ────────────────────────────────────────────── */
  function applyFilter() {
    var term = input.value.trim().toLowerCase();
    var mode = select ? select.value : "genre";

    /* Update placeholder to reflect active mode */
    if (placeholders[mode]) {
      input.setAttribute("placeholder", placeholders[mode]);
    }

    /* Show / hide clear button */
    if (clearBtn) {
      clearBtn.style.display = input.value.length > 0 ? "" : "none";
    }

    for (var i = 0; i < sections.length; i++) {
      var section = sections[i];
      var show;

      if (mode === "genre") {
        /* ── Genre mode: restore all release items, match genre heading ── */
        if (section.releaseList) {
          var items = section.releaseList.querySelectorAll("li");
          for (var m = 0; m < items.length; m++) {
            items[m].style.display = "";
          }
        }
        show = term.length <= 1 || section.text.indexOf(term) !== -1;

      } else {
        /* ── Release mode: filter individual release items ───────────── */
        if (term.length <= 1) {
          /* Term too short — show everything */
          if (section.releaseList) {
            var items = section.releaseList.querySelectorAll("li");
            for (var m = 0; m < items.length; m++) {
              items[m].style.display = "";
            }
          }
          show = true;
        } else {
          var anyMatch = false;
          if (section.releaseList) {
            var items = section.releaseList.querySelectorAll("li");
            for (var m = 0; m < items.length; m++) {
              var isMatch = items[m].textContent.toLowerCase().indexOf(term) !== -1;
              items[m].style.display = isMatch ? "" : "none";
              if (isMatch) { anyMatch = true; }
            }
          }
          show = anyMatch;
        }
      }

      var display = show ? "" : "none";
      for (var j = 0; j < section.elements.length; j++) {
        section.elements[j].style.display = display;
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

  if (select) {
    select.addEventListener("change", applyFilter);
  }

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
    with a search input, a mode select (genre / release), a clear button,
    and appends the filtering script.

    DOM structure injected inside ``<div id="genre-filter">``:

    .. code-block:: html

        <div id="genre-filter-wrapper">           <!-- flex row -->
          <div id="genre-filter-input-wrapper">   <!-- relative, flex: 1 -->
            <input id="genre-filter-input" …>
            <button id="genre-filter-clear" …>…</button>
          </div>
          <select id="genre-filter-mode">
            <option value="genre" selected>Genre</option>
            <option value="release">Release</option>
          </select>
        </div>

    The clear-button icon is read from
    ``docs/assets/icons/close-circle-outline.svg`` at build time via
    BeautifulSoup so the hook always reflects the on-disk version of
    the icon.

    Args:
        output: The full rendered HTML output of the page.
        page:   The MkDocs Page object.
        config: The global MkDocs config dict.

    Returns:
        The modified HTML with the filter input, mode select, clear
        button, and script injected, including TOC synchronisation.
    """
    if page.file.src_path != "genres.md":
        return output

    soup = BeautifulSoup(output, "html.parser")

    placeholder = soup.find("div", id="genre-filter")
    if not placeholder:
        return output

    # ── Outer flex row ────────────────────────────────────────────
    wrapper_tag: Tag = soup.new_tag("div", attrs={"id": "genre-filter-wrapper"})

    # ── Inner wrapper: input + absolutely-positioned clear button ─
    input_wrapper_tag: Tag = soup.new_tag("div", attrs={"id": "genre-filter-input-wrapper"})
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
    clear_button_tag.append(copy.copy(CLEAR_ICON_TAG))

    input_wrapper_tag.append(filter_input_tag)
    input_wrapper_tag.append(clear_button_tag)

    # ── Mode select (genre / release) ─────────────────────────────
    select_tag: Tag = soup.new_tag("select", attrs={
        "id": "genre-filter-mode",
        "aria-label": "Filter by",
    })
    genre_option: Tag = soup.new_tag("option", attrs={"value": "genre", "selected": ""})
    genre_option.string = "Genre"
    release_option: Tag = soup.new_tag("option", attrs={"value": "release"})
    release_option.string = "Release"
    select_tag.append(genre_option)
    select_tag.append(release_option)

    wrapper_tag.append(input_wrapper_tag)
    wrapper_tag.append(select_tag)

    placeholder.append(wrapper_tag)
    soup.append(BeautifulSoup(FILTER_SCRIPT, "html.parser"))

    return str(soup)
