"""Housekeeping check for The BI Workbench.

Checks three things that rot quietly on a site like this:

  1. every internal link and asset resolves to a real file
  2. every article in posts/ is listed on the home page
  3. no article has gone longer than STALE_DAYS without a review date

    python3 check.py

Exits 1 if anything is broken, 0 otherwise. Warnings (stale review dates) do
not fail the check, because they need a human decision, not a fix.
"""

import datetime
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.abspath(__file__))
STALE_DAYS = 270
SKIP = ("http://", "https://", "mailto:", "#", "//", "data:")
REVIEW_RE = re.compile(r"(?:Reviewed|Rewritten)\s+(\d{1,2} [A-Z][a-z]+ \d{4})")


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ("href", "src"):
            value = attrs.get(key)
            if value:
                self.links.append(value)


def pages():
    for dirpath, _dirnames, filenames in os.walk(ROOT):
        for name in sorted(filenames):
            if name.endswith(".html"):
                yield os.path.join(dirpath, name)


def resolves(page, target):
    """True if a link maps to a file.

    Handles /-rooted links, and the clean URLs Cloudflare Pages serves, where
    /posts/why-two-reports-disagree is posts/why-two-reports-disagree.html.
    """
    if target.startswith("/"):
        base = os.path.normpath(os.path.join(ROOT, target.lstrip("/")))
    else:
        base = os.path.normpath(os.path.join(os.path.dirname(page), target))
    candidates = (base, base + ".html", os.path.join(base, "index.html"))
    return any(os.path.isfile(candidate) for candidate in candidates)


def check_links(path, problems):
    with open(path, encoding="utf-8") as handle:
        parser = Links()
        parser.feed(handle.read())
    for link in parser.links:
        if link.startswith(SKIP):
            continue
        target = link.split("#")[0].split("?")[0]
        if not target:
            continue
        if not resolves(path, target):
            problems.append(f"{os.path.relpath(path, ROOT)}: broken link -> {link}")


def check_index(problems):
    index = os.path.join(ROOT, "index.html")
    if not os.path.exists(index):
        problems.append("index.html is missing")
        return
    with open(index, encoding="utf-8") as handle:
        markup = handle.read()
    posts = os.path.join(ROOT, "posts")
    for name in sorted(os.listdir(posts)):
        if name.endswith(".html") and f"posts/{name[:-5]}" not in markup:
            problems.append(f"posts/{name} is not linked from index.html")


def review_age(path, warnings, today):
    with open(path, encoding="utf-8") as handle:
        found = REVIEW_RE.search(handle.read())
    rel = os.path.relpath(path, ROOT)
    if not found:
        warnings.append(f"{rel}: no 'Reviewed <date>' line")
        return
    try:
        reviewed = datetime.datetime.strptime(found.group(1), "%d %B %Y").date()
    except ValueError:
        warnings.append(f"{rel}: review date '{found.group(1)}' is not readable")
        return
    age = (today - reviewed).days
    if age > STALE_DAYS:
        warnings.append(f"{rel}: last reviewed {found.group(1)} ({age} days ago)")


def main():
    today = datetime.date.today()
    problems, warnings = [], []

    for path in pages():
        check_links(path, problems)
        if os.path.dirname(path) == os.path.join(ROOT, "posts"):
            review_age(path, warnings, today)

    check_index(problems)

    print(f"checked {len(list(pages()))} pages, {today.isoformat()}")
    for line in problems:
        print(f"  BROKEN  {line}")
    for line in warnings:
        print(f"  CHECK   {line}")
    if not problems and not warnings:
        print("  all clear: links resolve, every post is listed, reviews are current")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
