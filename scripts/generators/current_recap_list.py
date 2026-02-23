import mkdocs_gen_files
import markdown
import os
import datetime
import time

from glob import glob
from bs4 import BeautifulSoup
from bs4.element import NavigableString
# from markdown.extensions.toc import slugify
from pymdownx.slugs import slugify

processiog_data = {}
current_date = datetime.datetime.now()
current_month = current_date.strftime("%B")

for release_list_path in glob("docs/**/releases.md", recursive=True):
    mkdocs_release_list_path = os.path.relpath(release_list_path, "docs")

    with mkdocs_gen_files.open(mkdocs_release_list_path, "r") as f:
        md = markdown.Markdown(extensions=["meta", "toc"])
        html = md.convert(f.read())
        soup = BeautifulSoup(html, "html.parser")

        release_list_date = datetime.datetime.strptime(md.Meta["date"][0], "%Y-%m-%d")
        release_list_year = release_list_date.year
        release_list_month_name = release_list_date.strftime("%B")

        if release_list_year not in processiog_data:
            processiog_data[release_list_year] = {}

        if release_list_month_name not in processiog_data[release_list_year]:
            processiog_data[release_list_year][release_list_month_name] = []

        for h2 in soup.find_all("h2"):
            for child in h2.children:
                if isinstance(child, NavigableString):
                    if child.endswith(" *") or child.endswith(" **"):
                        processiog_data[release_list_year][release_list_month_name].append({
                            "release_name": child.rstrip(" *"),
                            "file_path": mkdocs_release_list_path,
                            "release_date": release_list_date,
                            "anchor_name": h2.get("id")
                        })

for year, month_list in processiog_data.items():
    for month, releases in month_list.items():
        month_number = "%02d" % time.strptime(month, "%B").tm_mon
        with mkdocs_gen_files.open(f"posts/{year}/{month_number}/recap.md", "w") as f:
            f.write("---\n")
            f.write(f"date: {year}-{month_number}-01\n")
            f.write("pin: false\n")
            f.write("draft: true\n")
            f.write("authors:\n")
            f.write("    - vuellosoph\n")
            f.write("---\n\n")

            f.write(f"# {month} {year} Recap\n\n")

            for index, release in enumerate(releases):
                release_path_link = f"../../../{release['file_path']}#{release['anchor_name']}"
                f.write("<div class='grid cards' markdown>\n\n")
                f.write(f"-   ### {release['release_name']}\n\n")
                f.write(f"    ---\n\n")
                f.write(f"    [:octicons-arrow-right-24: Reference]({release_path_link})\n\n")
                f.write("</div>\n\n")

                if index == 2:
                    f.write("<!-- more -->\n\n")
