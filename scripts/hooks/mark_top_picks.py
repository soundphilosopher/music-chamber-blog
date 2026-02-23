from bs4 import BeautifulSoup
from bs4.element import NavigableString


def _strip_trailing_stars(h2):
    for child in reversed(h2.contents):
            if isinstance(child, NavigableString):
                child.replace_with(child.rstrip(" *"))
                return

def on_page_content(html, page, config, files):
    if not page.file.src_path.endswith("releases.md"):
        return html

    soup = BeautifulSoup(html, "html.parser")

    for h2 in soup.find_all("h2"):
        h2_text = " ".join(h2.text.split())
        p = h2.find_next("p")

        if p:
            if h2_text.endswith(" **"):
                _strip_trailing_stars(h2)
                recap_tag = soup.new_tag("div", attrs={"class": "grid cards top-list-recap"})
                ul_tag = soup.new_tag("ul")
                li_tag = soup.new_tag("li")
                hr_tag = soup.new_tag("hr")

                h2.insert_before(recap_tag)

                li_tag.append(h2.extract())
                li_tag.append(hr_tag)
                li_tag.append(p.extract())

                ul_tag.append(li_tag)
                recap_tag.append(ul_tag)

            elif h2_text.endswith(" *"):
                _strip_trailing_stars(h2)
                rerun_tag = soup.new_tag("div", attrs={"class": "grid cards top-list-rerun"})
                ul_tag = soup.new_tag("ul")
                li_tag = soup.new_tag("li")
                hr_tag = soup.new_tag("hr")

                h2.insert_before(rerun_tag)

                li_tag.append(h2.extract())
                li_tag.append(hr_tag)
                li_tag.append(p.extract())

                ul_tag.append(li_tag)
                rerun_tag.append(ul_tag)

    return str(soup)
