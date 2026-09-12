"""Turn a Kindle "My Clippings.txt" file into one Quarto page per book.

Usage:
    uv run python _extras/book_notes/build_book_notes.py                 # reads data/kindle/My Clippings.txt
    uv run python _extras/book_notes/build_book_notes.py path/to/file.txt

Every run regenerates books/<slug>.qmd from scratch, so edit TITLE_OVERRIDES
or SKIP_TITLES below instead of editing the generated files by hand.

Each page has two parts: "Notes", read from books/_takes/<slug>.md (written
by hand; the script creates an empty stub for new books), and "Highlights",
built from the clippings and optional data/kindle/notebooks/<slug>.json imports.
Pages without a take skip that section. Use import_notebook.py for browser exports.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "kindle"
DEFAULT_INPUT = DATA_DIR / "My Clippings.txt"
OUTPUT_DIR = ROOT / "books"
TAKES_DIR = OUTPUT_DIR / "_takes"
NOTEBOOKS_DIR = DATA_DIR / "notebooks"
# Sorting placeholder for books whose highlight dates are unavailable.
DEFAULT_BOOK_DATE = "1970-01-01"

# Raw Kindle title -> cleaned (title, author). Author is optional; when it is
# omitted the author parsed from the raw title's trailing parenthesis is used.
TITLE_OVERRIDES: dict[str, tuple[str, str | None]] = {
    "$100M Leads: How to Get Strangers To Want To Buy Your Stuff (Acquisition.com $100M Series Book 2) (Hormozi, Alex)": (
        "$100M Leads",
        None,
    ),
    "$100M Offers: How To Make Offers So Good People Feel Stupid Saying No (Hormozi, Alex)": (
        "$100M Offers",
        None,
    ),
    "The Israel-Palestine Conflict (Contesting the Past) (Caplan, Neil)": (
        "The Israel-Palestine Conflict",
        None,
    ),
    "The Palestinian-Israeli Conflict: A Very Short Introduction (Very Short Introductions) (Bunton, Martin)": (
        "The Palestinian-Israeli Conflict: A Very Short Introduction",
        None,
    ),
    "Meditations: A New Translation (Aurelius, Marcus)": ("Meditations", None),
    "Build_a_Large_Language_Model_(From_Scrat_v5 (Sebastian Raschka)": (
        "Build a Large Language Model (From Scratch)",
        "Sebastian Raschka",
    ),
    "Sivers-Anything_You_Want (Derek Sivers)": ("Anything You Want", "Derek Sivers"),
    "Sivers-Useful_Not_True (Derek Sivers)": ("Useful Not True", "Derek Sivers"),
    "Lustrum (Cicero Trilogy)": ("Lustrum", "Robert Harris"),
    "Imperium (Cicero Trilogy)": ("Imperium", "Robert Harris"),
    "Beyond The Agency Box: The Phoneless, Meetingless Digital Marketing Agency That Creates Lifetime Happy Clients Without Facebook Ads, Webinars, Google, or SEO (Fihn, Frankie)": (
        "Beyond The Agency Box",
        None,
    ),
    "Comprender la vida (Psicología Hoy) (Spanish Edition) (Adler, Alfred)": (
        "Comprender la vida",
        None,
    ),
    "The Fall of Hyperion (Hyperion Cantos, Book 2) (Simmons, Dan)": (
        "The Fall of Hyperion",
        None,
    ),
    "Hyperion (Hyperion Cantos, Book 1) (Simmons, Dan)": ("Hyperion", None),
    "Dark Matter: Soon to be a major Television event from Apple (Crouch, Blake)": (
        "Dark Matter",
        None,
    ),
    "Zero (Seife, Charles)": ("Zero: The Biography of a Dangerous Idea", None),
}

# Raw titles to leave out entirely.
SKIP_TITLES: set[str] = set()

META_RE = re.compile(
    r"^- Your (?P<kind>Highlight|Note|Bookmark)"
    r"(?: on page (?P<page>[^|]+?))?"
    r"(?: \| | on )Location (?P<loc>\d+)(?:-(?P<loc_end>\d+))?"
    r" \| Added on (?P<date>.+)$"
)


@dataclass
class Clipping:
    raw_title: str
    kind: str
    page: str | None
    loc: int
    loc_end: int | None
    added: datetime
    text: str


def parse_clippings(path: Path) -> list[Clipping]:
    raw = path.read_text(encoding="utf-8-sig")
    entries = re.split(r"\r?\n==========\r?\n?", raw)
    clippings: list[Clipping] = []
    for entry in entries:
        lines = entry.replace("\r\n", "\n").strip("\n").split("\n")
        if len(lines) < 2:
            continue
        title = lines[0].lstrip("﻿").strip()
        meta = META_RE.match(lines[1].strip())
        if not meta:
            print(f"warning: could not parse metadata line: {lines[1]!r}", file=sys.stderr)
            continue
        text = "\n".join(lines[2:]).strip()
        clippings.append(
            Clipping(
                raw_title=title,
                kind=meta["kind"],
                page=(meta["page"] or "").strip() or None,
                loc=int(meta["loc"]),
                loc_end=int(meta["loc_end"]) if meta["loc_end"] else None,
                added=datetime.strptime(meta["date"].strip(), "%A, %B %d, %Y %I:%M:%S %p"),
                text=text,
            )
        )
    return clippings


def parse_author(name: str) -> str:
    """Kindle stores authors as 'Last, First' joined by ';'."""
    people = []
    for person in name.split(";"):
        person = person.strip()
        if "," in person:
            last, first = [p.strip() for p in person.split(",", 1)]
            person = f"{first} {last}"
        people.append(person)
    if len(people) <= 1:
        return people[0] if people else ""
    return ", ".join(people[:-1]) + " and " + people[-1]


def clean_title(raw: str) -> tuple[str, str]:
    raw = raw.strip()
    parsed_title, parsed_author = raw, ""
    match = re.match(r"^(.*)\s\(([^()]+)\)\s*$", raw)
    if match:
        parsed_title, parsed_author = match.group(1).strip(), parse_author(match.group(2))
    if raw in TITLE_OVERRIDES:
        title, author = TITLE_OVERRIDES[raw]
        return title, author or parsed_author
    return parsed_title, parsed_author


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text


def dedupe(items: list[Clipping]) -> list[Clipping]:
    """Kindle appends a new entry every time a highlight is adjusted.

    Keep the last version for each location range, then drop any highlight
    whose text is contained in another surviving highlight.
    """
    latest: dict[tuple[int, int | None], Clipping] = {}
    for item in sorted(items, key=lambda c: c.added):
        latest[(item.loc, item.loc_end)] = item
    survivors = list(latest.values())
    kept = []
    for item in survivors:
        contained = any(
            other is not item and item.text in other.text for other in survivors
        )
        if not contained:
            kept.append(item)
    return sorted(kept, key=lambda c: (c.loc, c.loc_end or c.loc))


def escape_markdown(text: str) -> str:
    text = text.replace("\\", "\\\\")
    for char in "$*_[]<>`#":
        text = text.replace(char, "\\" + char)
    return text


def yaml_str(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def month_span(first: datetime, last: datetime) -> str:
    if (first.year, first.month) == (last.year, last.month):
        return f"in {last:%B %Y}"
    if first.year == last.year:
        return f"between {first:%B} and {last:%B %Y}"
    return f"between {first:%B %Y} and {last:%B %Y}"


def load_take(slug: str, title: str) -> str:
    """Return the hand-written take for a book, creating a stub if missing."""
    path = TAKES_DIR / f"{slug}.md"
    if not path.exists():
        path.write_text(f"<!-- Your take on {title}. Delete this comment and write below. -->\n", encoding="utf-8")
        return ""
    text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.S)
    return text.strip()


def normalized_highlight(text: str) -> str:
    """Ignore typography and list labels that Kindle HTML omits from text."""
    text = re.sub(r"\b(?:\d+|[a-z]|[ivx]+)[.)]\s+", "", text)
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def notebook_additions(title: str, highlights: list[Clipping]) -> list[dict]:
    path = NOTEBOOKS_DIR / f"{slugify(title)}.json"
    if not path.exists():
        return []
    seen = {normalized_highlight(c.text) for c in highlights}
    additions = []
    for item in json.loads(path.read_text(encoding="utf-8"))["highlights"]:
        key = normalized_highlight(item["text"])
        if key and key not in seen:
            additions.append(item)
            seen.add(key)
    return additions


def render_book(title: str, author: str, items: list[Clipping], take: str) -> str:
    highlights = [c for c in items if c.kind == "Highlight"]
    notes = [c for c in items if c.kind == "Note"]
    first = min((c.added for c in items), default=None)
    last = max((c.added for c in items), default=None)
    additions = notebook_additions(title, highlights)
    notebook_path = NOTEBOOKS_DIR / f"{slugify(title)}.json"
    notebook = (json.loads(notebook_path.read_text(encoding="utf-8"))
                if notebook_path.exists() else {})
    accessed = notebook.get("last_accessed")
    reading_dates = [last.strftime("%Y-%m-%d") if last else None, accessed]
    last_read = max((value for value in reading_dates if value), default=DEFAULT_BOOK_DATE)
    count = len(highlights) + len(additions)
    noun = "highlight" if count == 1 else "highlights"
    summary = f"{count} {noun}."
    if items and not additions:
        summary = f"{count} {noun} added {month_span(first, last)}."

    asin, cover = notebook.get("asin"), notebook.get("cover_url")
    amazon_url = f"https://www.amazon.com/dp/{asin}" if asin else None
    out = [
        "---",
        f"title: {yaml_str(title)}",
        f"subtitle: {yaml_str(author)}",
        f"date: {last_read}",
        f"highlights: {count}",
        f"description-meta: {yaml_str(f'Kindle highlights from {title} by {author}.')}",
    ]
    if cover:
        out.append(f"book-cover: {yaml_str(cover)}")
    if amazon_url:
        out.append(f"amazon-url: {yaml_str(amazon_url)}")
    out += ["---", ""]
    if take:
        out += ["## Notes", "", take, ""]
    out += [
        "## Highlights",
        "",
        summary,
        "",
    ]

    notes_by_loc = defaultdict(list)
    for note in notes:
        notes_by_loc[note.loc].append(note)

    for item in highlights:
        paragraphs = [p.strip() for p in item.text.split("\n") if p.strip()]
        for i, paragraph in enumerate(paragraphs):
            if i:
                out.append(">")
            out.append(f"> {escape_markdown(paragraph)}")
        ref = f"Location {item.loc}"
        if item.page:
            ref = f"Page {item.page}, location {item.loc}"
        out.append(">")
        out.append(f"> [{ref}]{{.highlight-ref}}")
        out.append("")
        for note in notes_by_loc.pop(item.loc, []):
            out.append(f"*Note:* {escape_markdown(note.text)}")
            out.append("")

    for loc in sorted(notes_by_loc):
        for note in notes_by_loc[loc]:
            out.append(f"*Note (location {loc}):* {escape_markdown(note.text)}")
            out.append("")

    if additions:
        for item in additions:
            ref = item["reference"].split("|", 1)[-1].strip()
            out += [f"> {escape_markdown(item['text'])}", ">",
                    f"> [{escape_markdown(ref)}]{{.highlight-ref}}", ""]

    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    clippings = parse_clippings(input_path)

    by_title: dict[str, list[Clipping]] = defaultdict(list)
    for clipping in clippings:
        if clipping.kind == "Bookmark" or clipping.raw_title in SKIP_TITLES:
            continue
        by_title[clipping.raw_title].append(clipping)

    OUTPUT_DIR.mkdir(exist_ok=True)
    TAKES_DIR.mkdir(exist_ok=True)
    for old in OUTPUT_DIR.glob("*.qmd"):
        old.unlink()

    written = []
    processed = set()
    for raw_title, items in by_title.items():
        title, author = clean_title(raw_title)
        deduped = dedupe(items)
        slug = slugify(title)
        processed.add(slug)
        take = load_take(slug, title)
        highlights = [c for c in deduped if c.kind == "Highlight"]
        count = len(highlights) + len(notebook_additions(title, highlights))
        if count < 3 and not take:
            continue
        (OUTPUT_DIR / f"{slug}.qmd").write_text(render_book(title, author, deduped, take), encoding="utf-8")
        written.append((slug, title, author, count, len(items), bool(take)))

    for path in sorted(NOTEBOOKS_DIR.glob("*.json")):
        if path.stem in processed:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        title, author = data["title"], data.get("author", "")
        take = load_take(path.stem, title)
        count = len(notebook_additions(title, []))
        if count < 3 and not take:
            continue
        (OUTPUT_DIR / f"{path.stem}.qmd").write_text(render_book(title, author, [], take), encoding="utf-8")
        written.append((path.stem, title, author, count, 0, bool(take)))

    for slug, title, author, kept, total, has_take in sorted(written, key=lambda w: w[1].lower()):
        flag = "take" if has_take else "    "
        print(f"{kept:3d}/{total:<3d} {flag} {title} ({author}) -> books/{slug}.qmd")
    print(f"\n{len(written)} books written to {OUTPUT_DIR.relative_to(ROOT)}/")
    print(f"Write your takes in {TAKES_DIR.relative_to(ROOT)}/<slug>.md and re-run this script.")


if __name__ == "__main__":
    main()
