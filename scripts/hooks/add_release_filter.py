import logging

from bs4 import BeautifulSoup
from mkdocs.config import Config
from mkdocs.structure.pages import Page

from utils.genres import GENRE_TAG_PREFIX, GENRE_TAG_PATTERN, normalize_genre_names


log = logging.getLogger("mkdocs.hooks.add_release_filter")


def on_post_page(output: str, page: Page, config: Config) -> str:
    src = page.file.src_path
    if not (src.endswith("releases.md") and src.startswith("posts")):
        return output

    soup = BeautifulSoup(output, "html.parser")

    genre_bucket: dict[str, list[str]] = {}
    genres: list[tuple[str, str]] = []

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
                genres.append((genre, release.get_text().rstrip(" *")))

    for g, r in genres:
        if g not in genre_bucket:
            genre_bucket[g] = []
        genre_bucket[g].append(r)

    print(f"DEBUG: path={src}, genres={genre_bucket.keys()}")

    return str(soup)
