"""Import the currently loaded book from a saved Kindle Notebook HTML page.

In Firefox, save read.amazon.com/notebook as Web Page, complete, after loading
the desired book. This command reads the local download only; no subscription,
browser credentials, or network access is required.

    python3 _extras/book_notes/import_notebook.py notebook.html 100m-offers

The output contains highlight text and references only. Keep the raw browser
download outside the repository because it can contain account/session data.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

from build_book_notes import NOTEBOOKS_DIR, OUTPUT_DIR, normalized_highlight, slugify


class Node:
    def __init__(self, tag="", attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def nodes(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.nodes()

    def text(self):
        return "".join(c.text() if isinstance(c, Node) else c for c in self.children)

    def by_id(self, value):
        return next((n for n in self.nodes() if n.attrs.get("id") == value), None)


class NotebookHTML(HTMLParser):
    VOID = set("area base br col embed hr img input link meta param source track wbr".split())

    def __init__(self):
        super().__init__()
        self.root = Node()
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag == "br":
            node.children.append("\n")
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def normalize_access_date(value):
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("Last accessed date must be a string")
    value = re.sub(r"^Last accessed on\s*", "", value.strip(), flags=re.I)
    for fmt in ("%Y-%m-%d", "%A, %B %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"Unrecognized last accessed date: {value!r}")


def book_metadata(book, previous=None):
    previous = previous or {}
    asin = book.get("asin") or previous.get("asin")
    if asin and (not isinstance(asin, str) or not re.fullmatch(r"[A-Z0-9]{10}", asin)):
        raise ValueError("Book ASIN must contain 10 uppercase letters or digits")
    cover = book.get("cover_url") or (previous.get("cover_url")
                                     if asin == previous.get("asin") else None)
    if cover:
        if not isinstance(cover, str):
            raise ValueError("Cover URL must be a string")
        url = urlsplit(cover)
        allowed = ("media-amazon.com", "ssl-images-amazon.com", "images-amazon.com")
        if (url.scheme != "https" or url.username or url.password or
                not any(url.hostname == host or (url.hostname or "").endswith("." + host)
                        for host in allowed) or any(c in cover for c in '<>\"\n\r')):
            raise ValueError("Expected an HTTPS Amazon cover image URL")
    return {"asin": asin, "cover_url": cover}


def extract(html):
    parser = NotebookHTML()
    parser.feed(html)
    annotations = parser.root.by_id("kp-notebook-annotations")
    pane = parser.root.by_id("annotation-scroller")
    if annotations is None or pane is None:
        raise ValueError("No loaded Kindle Notebook found. Save the page as Web Page, complete.")
    headings = [n for n in pane.nodes() if n.tag == "h3"]
    if not headings:
        raise ValueError("Cannot identify the selected book title.")
    title = " ".join(headings[0].text().split())
    access_label = next((" ".join(n.text().split()) for n in pane.nodes()
                         if n.tag == "span" and n.text().strip().startswith("Last accessed on")), None)
    highlights, unavailable = [], 0
    for row in annotations.children:
        if not isinstance(row, Node):
            continue
        header = row.by_id("annotationHighlightHeader")
        text = row.by_id("highlight")
        if header is None:
            continue
        if text is None or not text.text().strip():
            unavailable += 1
            continue
        highlights.append({
            "text": " ".join(text.text().split()),
            "reference": " ".join(header.text().split()),
        })
    if not highlights:
        raise ValueError("The saved notebook has no text highlights.")
    return {"title": title, "source": "https://read.amazon.com/notebook",
            "last_accessed": normalize_access_date(access_label),
            "imported_on": date.today().isoformat(),
            "unavailable_highlights": unavailable, "highlights": highlights}


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("html", type=Path)
    args.add_argument("slug", nargs="?", help="Existing book slug, required for HTML imports")
    opts = args.parse_args()
    if opts.html.suffix.lower() == ".json":
        payload = json.loads(opts.html.read_text(encoding="utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("books"), list):
            args.error("Expected JSON from export_notebooks.js")
        paths = import_books(payload["books"])
        print(f"Imported {len(paths)} books into {NOTEBOOKS_DIR}")
        if not payload.get("complete"):
            print("Warning: partial browser export; retry the reported failed books.")
        return
    if not opts.slug:
        args.error("HTML imports require an existing book slug")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", opts.slug):
        args.error("Use an existing book slug, e.g. 100m-offers.")
    book = OUTPUT_DIR / f"{opts.slug}.qmd"
    if not book.exists():
        args.error(f"Book page does not exist: {book}")
    expected = json.loads(re.search(r'^title: (.+)$', book.read_text(), re.M)[1])
    data = extract(opts.html.read_text(encoding="utf-8"))
    if not normalized_highlight(data["title"]).startswith(normalized_highlight(expected)):
        args.error(f"Selected book {data['title']!r} does not match {expected!r}.")
    NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTEBOOKS_DIR / f"{opts.slug}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(data['highlights'])} text highlights; "
          f"{data['unavailable_highlights']} unavailable as text. Output: {path}")


def import_books(books):
    """Validate the entire batch before writing; preserve prior captures on retry."""
    known = []
    for path in OUTPUT_DIR.glob("*.qmd"):
        text = path.read_text(encoding="utf-8")
        title = json.loads(re.search(r'^title: (.+)$', text, re.M)[1])
        author = json.loads(re.search(r'^subtitle: (.+)$', text, re.M)[1])
        known.append((path.stem, title, author))
    # Excluded pages still need their canonical titles when exports are retried.
    known_slugs = {entry[0] for entry in known}
    for path in NOTEBOOKS_DIR.glob("*.json"):
        if path.stem not in known_slugs:
            data = json.loads(path.read_text(encoding="utf-8"))
            known.append((path.stem, data["title"], data.get("author", "")))
    prepared = {}
    for book in books:
        title, author = book["title"], book.get("author", "")
        if not isinstance(title, str) or not title.strip() or not isinstance(author, str):
            raise ValueError("Each book requires a title and string author")
        key = normalized_highlight(title)
        matches = [k for k in known if key == normalized_highlight(k[1]) or
                   key.startswith(normalized_highlight(k[1]))]
        # Prefer the longest title: e.g. The Fall of Hyperion over a shorter prefix.
        matches.sort(key=lambda k: len(normalized_highlight(k[1])), reverse=True)
        slug, clean_title, clean_author = matches[0] if matches else (slugify(title), title, author)
        if not slug:
            raise ValueError(f"Cannot generate a filename for {title!r}")
        data = {"title":clean_title,"author":clean_author,"source_title":title,
                "source":"https://read.amazon.com/notebook", "imported_on":date.today().isoformat(),
                "unavailable_highlights":int(book.get("unavailable_highlights", 0)), "highlights":[]}
        seen = set()
        path = NOTEBOOKS_DIR / f"{slug}.json"
        previous = prepared.get(path)
        if previous is None and path.exists():
            previous = json.loads(path.read_text(encoding="utf-8"))
        access_dates = [normalize_access_date(source.get("last_accessed"))
                        for source in (book, previous or {})]
        data["last_accessed"] = max((d for d in access_dates if d), default=None)
        data.update(book_metadata(book, previous))
        for item in book["highlights"] + (previous or {}).get("highlights", []):
            value, ref = item["text"], item["reference"]
            if not isinstance(value, str) or not isinstance(ref, str):
                raise ValueError("Highlight text and reference must be strings")
            normalized = normalized_highlight(value)
            if normalized and normalized not in seen:
                data["highlights"].append({"text":value,"reference":ref})
                seen.add(normalized)
        prepared[path] = data
    NOTEBOOKS_DIR.mkdir(parents=True, exist_ok=True)
    for path, data in prepared.items():
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return list(prepared)


if __name__ == "__main__":
    main()
