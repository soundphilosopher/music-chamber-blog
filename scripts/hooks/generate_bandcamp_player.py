from curl_cffi import requests
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from markdown.extensions.toc import slugify


BANDCAMP_SEARCH_URL = "https://bandcamp.com/api/fuzzysearch/2/app_autocomplete"


def _bandcamp_search(query: str) -> list[dict]:
    """Search Bandcamp's fuzzy-search API and return a list of result dicts."""
    response = requests.get(
        BANDCAMP_SEARCH_URL,
        params={"q": query, "param_with_locations": "true"},
        impersonate="chrome",
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    return [item for item in results if item["type"] == "a"]


def on_page_content(html, page, config, files):
    if not page.file.src_path.endswith("releases.md"):
        return html

    if not page.meta.get("pin", False):
        return html

    soup = BeautifulSoup(html, "html.parser")

    for h2 in soup.find_all("h2"):
        description = h2.find_next("p")

        for child in h2.children:
            if isinstance(child, NavigableString):
                search_query = slugify(child, " ")

                try:
                    results = _bandcamp_search(search_query)

                    if results == []:
                        continue

                    album_id = results[0]["id"]
                    album_url = results[0]["url"]

                    if description:
                        div = soup.new_tag("div")
                        iframe = soup.new_tag("iframe", attrs={"style": "border: 0; width: 100%; height: 42px;", "src": f"https://bandcamp.com/EmbeddedPlayer/album={album_id}/size=small/bgcol=ffffff/linkcol=0687f5/transparent=true/", "seamless": ""})
                        a_tag = soup.new_tag("a", attrs={"href": album_url}, text=child)
                        iframe.append(a_tag)
                        div.append(iframe)

                        description.insert_after(div)
                except requests.RequestsError as e:
                    print(f"DEBUG: Error occurred while searching: {e}")
                    continue

    return str(soup)
