import re
from bs4 import BeautifulSoup

def on_post_page(output, page, config):
    """
    Replace site: prefixed image sources with the absolute site URL.
    Runs after full page rendering (including blog excerpts on the index).
    """
    if "site:" not in output:
        return output

    soup = BeautifulSoup(output, "html.parser")

    for img in soup.find_all("img", src=re.compile(r'^site:')):
        img['src'] = f'{config["site_url"]}{img["src"][5:]}'

    return str(soup)
