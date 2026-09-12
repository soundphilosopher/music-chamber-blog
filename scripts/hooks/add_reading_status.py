import logging

from bs4 import BeautifulSoup
from mkdocs.config import Config
from mkdocs.structure.pages import Page


log = logging.getLogger("mkdocs.hooks.add_reading_status")


SCRIPT = """
<script>
(function () {
    var wrapper = document.querySelector(".scroll-bar-wrapper");
    var scrollBar = wrapper ? wrapper.querySelector(".scroll-bar") : null;

    function indicateScrollBar() {
        var distanceFromPageTop = window.pageYOffset || document.documentElement.scrollTop;
        var height = document.documentElement.scrollHeight - window.innerHeight;
        var scrolled = height > 0 ? (distanceFromPageTop / height) * 100 : 0;

        if (wrapper) {
            wrapper.classList.toggle("visible", distanceFromPageTop > 0);
        }
        if (scrollBar) {
            scrollBar.style.width = scrolled + "%";
        }
    }

    window.addEventListener("scroll", indicateScrollBar);
    indicateScrollBar();
})();
</script>
"""

def on_post_page(output: str, page: Page, config: Config) -> str:
    """MkDocs hook: inject a scroll-progress bar into release list pages.

    Only processes pages whose source path ends with ``releases.md``
    inside ``posts/``. Inserts a progress-bar element directly after the
    page header and appends the tracking script to the body.

    Args:
        output: The fully rendered HTML of the page.
        page:   The MkDocs Page object.
        config: The global MkDocs config dict.

    Returns:
        The modified HTML, or the original when the page does not
        qualify or has no ``<header>``.
    """
    src = page.file.src_path
    if not (src.endswith("releases.md") and src.startswith("posts")):
        return output

    soup = BeautifulSoup(output, "html.parser")

    header = soup.find("header")
    if not header:
        return output

    wrapper = soup.new_tag("div", attrs={"class": "scroll-bar-wrapper"})
    scrollbar = soup.new_tag("div", attrs={"class": "scroll-bar"})
    wrapper.append(scrollbar)

    header.insert_after(wrapper)

    body = soup.find("body")
    if body:
        body.append(BeautifulSoup(SCRIPT, "html.parser"))

    return str(soup)
