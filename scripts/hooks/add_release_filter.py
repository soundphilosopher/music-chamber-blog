import logging

from bs4 import BeautifulSoup, Tag
from mkdocs.config import Config
from mkdocs.structure.pages import Page
from markdown.extensions.toc import slugify

from utils.genres import GENRE_TAG_PREFIX, GENRE_TAG_PATTERN, normalize_genre_names


log = logging.getLogger("mkdocs.hooks.add_release_filter")


def on_post_page(output: str, page: Page, config: Config) -> str:
    src = page.file.src_path
    if not (src.endswith("releases.md") and src.startswith("posts")):
        return output

    soup = BeautifulSoup(output, "html.parser")

    heading = soup.find(name="h1")
    if not heading:
        return output

    genre_bucket: dict[str, list[str]] = {}

    for p in soup.find_all(name="p"):
        if not GENRE_TAG_PATTERN.match(p.get_text()):
            continue

        release = p.find_previous(name="h2")
        if not release:
            continue

        genre_text = p.get_text().removeprefix(GENRE_TAG_PREFIX).strip()
        genre_names = [name.strip().lower() for name in genre_text.split(",")]
        genre_names_normalized = normalize_genre_names(genre_names)

        for genre in genre_names_normalized:
            if genre:
                if genre not in genre_bucket:
                    genre_bucket[genre] = []
                genre_bucket[genre].append(release.get_text().rstrip(" *"))

    # print(f"DEBUG: path={src}, genres={genre_bucket.keys()}")

    filter_wrapper_div: Tag = soup.new_tag(name="div", id="genre-filter-wrapper")
    filter_select_tag: Tag = soup.new_tag(name="select", attrs={"id": "genre-filter-select", "aria-label": "Filter by", "multiple": ""})
    for genre in genre_bucket.keys():
        filter_option_tag: Tag = soup.new_tag(name="option", attrs={"value": slugify(genre, "-")})
        filter_option_tag.string = genre
        filter_select_tag.append(filter_option_tag)

    filter_wrapper_div.append(filter_select_tag)
    heading.insert_after(filter_wrapper_div)

    return str(soup)
