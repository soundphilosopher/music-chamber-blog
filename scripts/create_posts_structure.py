import argparse
import calendar
import mkdocs_gen_files

from datetime import date
from pathlib import Path

POSTS_BASE = Path("docs/posts")


def _get_last_day_of_month(year: int, month: int) -> date:
    last_day_num = calendar.monthrange(year, month)[1]
    return date(year, month, last_day_num)


def _get_fridays_in_month(year: int, month: int) -> list[int]:
    first_weekday, days_in_month = calendar.monthrange(year, month)
    # weekday(): 0=Mon ... 4=Fri. Find the day number of the first Friday.
    first_friday = (4 - first_weekday) % 7 + 1
    return list(range(first_friday, days_in_month + 1, 7))


def _create_monthly_recap(year: int, month: int) -> None:
    file_path = POSTS_BASE / f"{year}" / f"{month:02d}" / "top-of-the-month.md"
    if file_path.exists():
        return

    last_day = _get_last_day_of_month(year, month)
    month_name = last_day.strftime("%B")

    content = "\n".join([
        "---",
        f"date: {last_day}",
        "draft: true",
        "categories:",
        "  - Top Lists",
        "  - Recap",
        "---",
        "",
        f"# Top 15 - {month_name} {year}",
        "",
        '<div class="grid cards" align="center" markdown>',
        "",
        "-   ![Some Image](https://picsum.photos/350){ .top-list-image }",
        "",
        "    ## Lorem - Ipsum",
        "",
        "</div>",
        "",
    ])

    mkdocs_path = file_path.relative_to(Path("docs"))
    with mkdocs_gen_files.open(mkdocs_path, "w") as f:
        f.write(content)


def main(year: int) -> None:
    for month in range(1, 13):
        for friday in _get_fridays_in_month(year, month):
            dir_path = POSTS_BASE / f"{year}" / f"{month:02d}" / f"{friday:02d}"
            dir_path.mkdir(parents=True, exist_ok=True)

        _create_monthly_recap(year, month)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create MkDocs post folder structure for a given year."
    )
    parser.add_argument("--year", type=int, required=True, help="Year to generate structure for")
    args = parser.parse_args()

    main(args.year)
